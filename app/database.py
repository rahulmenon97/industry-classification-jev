import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from app.migrations import load_run
from app.models import Run


class Database:
    """Connection per operation; atomic parameterized writes, WAL, versioned schema."""

    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version > 4:
                raise RuntimeError("Database schema newer than application")
            db.execute(SCHEMA)
            db.execute(
                "CREATE INDEX IF NOT EXISTS classification_created ON industy_classification(created_at DESC)"
            )
            if db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='runs'"
            ).fetchone():
                for (payload,) in db.execute("SELECT payload FROM runs").fetchall():
                    self._save(db, load_run(payload))
                db.execute("DROP TABLE runs")
            if version < 4:
                columns = {r[1] for r in db.execute("PRAGMA table_info(industy_classification)")}
                if "dummy_naics_code" in columns:
                    db.execute(
                        "ALTER TABLE industy_classification RENAME COLUMN dummy_naics_code TO industry_code"
                    )
                for (payload,) in db.execute(
                    "SELECT payload FROM industy_classification"
                ).fetchall():
                    self._save(db, load_run(payload))
            db.execute("PRAGMA user_version=4")
        path.chmod(0o600)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            with db:
                yield db
        finally:
            db.close()

    def _save(self, db, run):
        row = project(run)
        columns = ",".join(row)
        placeholders = ",".join("?" for _ in row)
        updates = ",".join(f"{key}=excluded.{key}" for key in row if key != "id")
        db.execute(
            f"INSERT INTO industy_classification ({columns}) VALUES ({placeholders}) "
            f"ON CONFLICT(id) DO UPDATE SET {updates}",
            tuple(row.values()),
        )

    def save(self, run: Run):
        with self.connect() as db:
            self._save(db, run)

    def get(self, run_id):
        with self.connect() as db:
            row = db.execute(
                "SELECT payload FROM industy_classification WHERE id=?", (run_id,)
            ).fetchone()
        return load_run(row[0]) if row else None

    def list(self, limit=50, offset=0):
        with self.connect() as db:
            rows = db.execute(
                "SELECT id,created_at,company_name,status FROM industy_classification ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [dict(zip(("id", "created_at", "company_name", "status"), r)) for r in rows]

    def recover(self):
        with self.connect() as db:
            rows = db.execute(
                "SELECT payload FROM industy_classification WHERE status='running'"
            ).fetchall()
        for row in rows:
            run = load_run(row[0])
            run.status = "interrupted"
            run.error = "Server stopped before the run completed."
            self.save(run)


SCHEMA = """CREATE TABLE IF NOT EXISTS industy_classification (
    id TEXT PRIMARY KEY, created_at TEXT NOT NULL, company_name TEXT NOT NULL,
    status TEXT NOT NULL, taxonomy_version TEXT NOT NULL,
    description TEXT, tier1_id TEXT, tier1_name TEXT, tier2_id TEXT, tier2_name TEXT,
    tier3_id TEXT, tier3_name TEXT, industry_code TEXT,
    classification_choice TEXT, classification_type TEXT,
    classification_score REAL, classification_confidence REAL,
    identity_score REAL, identity_confidence REAL, description_sufficiency_score REAL,
    identity_threshold REAL NOT NULL, description_rejected INTEGER,
    rejection_reason TEXT, error TEXT,
    elapsed_ms REAL NOT NULL, exa_elapsed_ms REAL, identity_elapsed_ms REAL,
    classification_elapsed_ms REAL, estimated_cost_usd REAL,
    known_cost_subtotal_usd REAL NOT NULL, exa_cost_usd REAL, jev_cost_usd REAL,
    jev_model TEXT, input_tokens INTEGER, output_tokens INTEGER, total_tokens INTEGER,
    exa_query TEXT, exa_search_type TEXT, exa_result_count INTEGER,
    selected_source_index INTEGER, exa_url TEXT, exa_title TEXT,
    sources_json TEXT NOT NULL, assessments_json TEXT NOT NULL,
    accuracy REAL, expected_tier3_id TEXT, accuracy_note TEXT NOT NULL,
    payload TEXT NOT NULL
)"""


def project(run: Run) -> dict:
    """Queryable columns are derived from the same validated run as the JSON export."""
    c = run.classification
    selected = run.selected_source_index
    source = run.sources[selected] if selected is not None else None
    assessment = next((a for a in run.assessments if a.source_index == selected), None)
    if assessment is None:
        # Retain rejection scores too. Legacy multi-source runs use the strongest
        # assessed description; the full per-source assessments remain in JSON.
        assessment = max(run.assessments, key=lambda a: a.sufficiency.noul, default=None)
    stages = {s.name: s for s in run.stages}
    exa = stages.get("retrieval")
    jev = [s for s in run.stages if s.provider == "typesafe"]

    def total(attribute):
        values = [getattr(s.usage, attribute) for s in jev]
        return sum(values) if values and all(v is not None for v in values) else None

    inputs, outputs = total("input_tokens"), total("output_tokens")
    rejected = (
        1 if run.status in ("no_evidence", "needs_review") else 0 if selected is not None else None
    )
    reason = {
        "no_evidence": "No usable company description was retrieved.",
        "needs_review": run.review_reason
        or "No source passed the identity and sufficiency thresholds.",
        "abstained": c.answer.choice if c else None,
    }.get(run.status)
    row = dict(
        id=run.id,
        created_at=run.created_at.isoformat(),
        company_name=run.request.company_name,
        status=run.status,
        taxonomy_version=run.taxonomy_version,
        description=run.company_profile.description
        if run.company_profile
        else source.text
        if source
        else None,
    )
    for i in range(3):
        row[f"tier{i + 1}_id"] = c.path_ids[i] if c and c.path_ids else None
        row[f"tier{i + 1}_name"] = c.path_names[i] if c and c.path_names else None
    row.update(
        industry_code=c.industry_code if c else None,
        classification_choice=c.answer.choice if c else None,
        classification_type=c.answer.type if c else None,
        classification_score=c.answer.probabilities[c.answer.choice] if c else None,
        classification_confidence=c.answer.confidence if c else None,
        identity_score=assessment.identity.probabilities.get("match") if assessment else None,
        identity_confidence=assessment.identity.confidence if assessment else None,
        description_sufficiency_score=assessment.sufficiency.noul if assessment else None,
        identity_threshold=run.identity_threshold,
        description_rejected=rejected,
        rejection_reason=reason,
        error=run.error,
        elapsed_ms=run.elapsed_ms,
        estimated_cost_usd=run.estimated_cost_usd,
        known_cost_subtotal_usd=run.known_cost_subtotal_usd,
        exa_cost_usd=exa.estimated_cost_usd if exa else None,
        jev_cost_usd=sum(s.estimated_cost_usd for s in jev)
        if jev and all(s.estimated_cost_usd is not None for s in jev)
        else None,
        jev_model=next((s.model for s in reversed(jev) if s.model), None),
        input_tokens=inputs,
        output_tokens=outputs,
        total_tokens=inputs + outputs if inputs is not None and outputs is not None else None,
        exa_query=exa.request.get("query") if exa else None,
        exa_search_type=exa.request.get("type") if exa else None,
        exa_result_count=len(exa.response["results"])
        if exa and exa.response and isinstance(exa.response.get("results"), list)
        else None,
        selected_source_index=selected,
        exa_url=str(run.company_profile.company_url)
        if run.company_profile and run.company_profile.company_url
        else str(source.url)
        if source
        else None,
        exa_title=source.title if source else None,
        sources_json=json.dumps([s.model_dump(mode="json") for s in run.sources]),
        assessments_json=json.dumps([a.model_dump(mode="json") for a in run.assessments]),
        accuracy=float(bool(c and c.path_ids and c.path_ids[-1] == run.expected_tier3_id))
        if run.expected_tier3_id and run.status in ("classified", "abstained")
        else None,
        expected_tier3_id=run.expected_tier3_id,
        accuracy_note=run.accuracy_note,
        payload=run.model_dump_json(),
    )
    for column, stage_name in [
        ("exa_elapsed_ms", "retrieval"),
        ("identity_elapsed_ms", "identity_and_sufficiency"),
        ("classification_elapsed_ms", "classification"),
    ]:
        row[column] = stages[stage_name].elapsed_ms if stage_name in stages else None
    return row
