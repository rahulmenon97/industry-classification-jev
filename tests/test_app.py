import json
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.models import Run, RunRequest
from app.database import Database


class FakeClients:
    def ready(self):
        return True

    def redact(self, x):
        return x

    def post(self, provider, payload):
        if provider == "exa":
            return {
                "results": [
                    {
                        "title": "Example business",
                        "url": "https://example.com",
                        "text": "Supplies customer relationship software to businesses.",
                    }
                ],
                "costDollars": {"total": 0.007},
                "output": {
                    "content": {
                        "company_name": "Example",
                        "company_url": "https://example.com",
                        "description": "Supplies customer relationship software to businesses.",
                        "ambiguity": "",
                        "identity_resolved": True,
                    },
                    "grounding": [],
                },
            }
        answers = {}
        for k, q in payload["questions"].items():
            if q["type"] == "noul":
                answers[k] = {"type": "noul", "noul": 0.99}
            else:
                choice = "match" if k.startswith("identity") else "crm_software"
                answers[k] = {
                    "type": "choice",
                    "choice": choice,
                    "probabilities": {o: float(o == choice) for o in q["criteria"]},
                    "confidence": 1.0,
                }
        return {
            "model": "jev-1.13.0",
            "answers": answers,
            "usage": {"input_tokens": 100, "output_tokens": 10},
        }


def test_api_run_persists_and_exports(tmp_path):
    settings = Settings(database_path=tmp_path / "runs.db")
    with TestClient(create_app(settings, FakeClients())) as client:
        response = client.post("/api/runs", json={"company_name": "Example"})
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["status"] == "classified"
        assert result["classification"]["path_names"] == [
            "Technology",
            "Software",
            "Customer Relationship Software",
        ]
        assert len(result["stages"]) == 3
        assert abs(result["estimated_cost_usd"] - 0.0070084) < 1e-10
        rid = result["id"]
        assert client.get("/api/runs").json()[0]["id"] == rid
        assert client.get(f"/api/runs/{rid}/export").json()["id"] == rid
        assert client.post("/api/runs", json={"company_name": "  "}).status_code == 422
        assert (
            client.post(
                "/api/runs", json={"company_name": "Example", "taxonomy": "../../secret"}
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/runs",
                headers={"Origin": "https://evil.test"},
                json={"company_name": "Example"},
            ).status_code
            == 403
        )
    with TestClient(create_app(settings, FakeClients())) as client:
        assert client.get(f"/api/runs/{rid}").json()["status"] == "classified"


def test_failure_saved_without_raw_error(tmp_path):
    class Bad(FakeClients):
        def post(self, p, payload):
            return {"results": "invalid"}

    with TestClient(create_app(Settings(database_path=tmp_path / "runs.db"), Bad())) as client:
        r = client.post("/api/runs", json={"company_name": "Example"}).json()
        assert r["status"] == "error"
        assert "schema validation" in r["error"]
        assert r["estimated_cost_usd"] is None
        assert client.get("/api/runs").json()[0]["status"] == "error"


def test_startup_recovers_interrupted_run(tmp_path):
    path = tmp_path / "runs.db"
    database = Database(path)
    run = Run(
        request=RunRequest(company_name="Example"), taxonomy_version="test", taxonomy_snapshot={}
    )
    database.save(run)
    with TestClient(create_app(Settings(database_path=path), FakeClients())) as client:
        assert client.get("/api/runs/" + run.id).json()["status"] == "interrupted"


def test_sqlite_columns_and_migration(tmp_path):
    import sqlite3

    path = tmp_path / "old.db"
    run = Run(
        request=RunRequest(company_name="Legacy"), taxonomy_version="test", taxonomy_snapshot={}
    )
    with sqlite3.connect(path) as db:
        db.execute(
            "CREATE TABLE runs (id TEXT PRIMARY KEY, created_at TEXT, company_name TEXT, status TEXT, payload TEXT)"
        )
        db.execute(
            "INSERT INTO runs VALUES (?,?,?,?,?)",
            (run.id, run.created_at.isoformat(), "Legacy", "running", run.model_dump_json()),
        )
        db.execute("PRAGMA user_version=1")
    repo = Database(path)
    assert repo.get(run.id).request.company_name == "Legacy"
    with TestClient(create_app(Settings(database_path=path), FakeClients())) as client:
        result = client.post("/api/runs", json={"company_name": "Example"}).json()
    with sqlite3.connect(path) as db:
        db.row_factory = sqlite3.Row
        row = db.execute(
            "SELECT * FROM industy_classification WHERE id=?", (result["id"],)
        ).fetchone()
        assert row["tier3_id"] == "crm_software"
        assert row["description"].startswith("Supplies")
        assert row["exa_url"] == "https://example.com/"
        assert row["classification_score"] == 1
        assert row["description_rejected"] == 0
        assert row["total_tokens"] == 220
        assert row["accuracy"] is None
        assert db.execute("PRAGMA user_version").fetchone()[0] == 4
        assert not db.execute("SELECT 1 FROM sqlite_master WHERE name='runs'").fetchone()
    labeled = repo.get(result["id"])
    labeled.expected_tier3_id = "crm_software"
    repo.save(labeled)
    with sqlite3.connect(path) as db:
        assert (
            db.execute(
                "SELECT accuracy FROM industy_classification WHERE id=?", (labeled.id,)
            ).fetchone()[0]
            == 1
        )
    assert len(Database(path).list()) == 2


def test_synthesis_is_used_and_ambiguity_stops_classification(tmp_path):
    class Ambiguous(FakeClients):
        def post(self, provider, payload):
            r = super().post(provider, payload)
            if provider == "exa":
                r["output"]["content"]["ambiguity"] = "Multiple companies share this name."
                r["output"]["content"]["identity_resolved"] = False
            return r

    with TestClient(create_app(Settings(database_path=tmp_path / "a.db"), Ambiguous())) as client:
        r = client.post("/api/runs", json={"company_name": "Example"}).json()
        assert r["status"] == "needs_review"
        assert len(r["stages"]) == 1
    with TestClient(create_app(Settings(database_path=tmp_path / "b.db"), FakeClients())) as client:
        r = client.post("/api/runs", json={"company_name": "Example"}).json()
        assert r["description_kind"] == "exa_synthesis"
        assert (
            r["stages"][-1]["request"]["state"]["description"]
            == r["company_profile"]["description"]
        )
        assert r["exa_results"][0]["url"] == "https://example.com/"


def test_diversified_taxonomy_paths():
    from app.taxonomy import Taxonomy

    t = Taxonomy("industry_v2")
    assert t.snapshot["version"] == "industry-demo-2.1"
    assert len(t.paths) == 77
    for leaf in ["diversified_internet_platforms", "diversified_enterprise_technology"]:
        assert t.by_leaf[leaf]["path_ids"] == ["technology", "diversified_technology", leaf]
    assert "matching division alone" in t.criteria["cloud_compute"]


def test_v2_database_code_migration(tmp_path):
    import sqlite3
    from app.database import SCHEMA

    path = tmp_path / "v2.db"
    run = Run(
        request=RunRequest(company_name="Legacy"),
        taxonomy_version="test",
        taxonomy_snapshot={"nodes": [{"naics_code": "000007"}]},
    )
    payload = run.model_dump()
    payload["classification"] = {
        "answer": {
            "type": "choice",
            "choice": "payments",
            "probabilities": {"payments": 1},
            "confidence": 1,
        },
        "path_ids": ["a", "b", "payments"],
        "path_names": ["A", "B", "Payments"],
        "dummy_naics": "000007",
    }
    with sqlite3.connect(path) as db:
        db.execute(SCHEMA.replace("industry_code TEXT", "dummy_naics_code TEXT"))
        db.execute(
            "INSERT INTO industy_classification (id,created_at,company_name,status,taxonomy_version,identity_threshold,elapsed_ms,known_cost_subtotal_usd,sources_json,assessments_json,accuracy_note,payload) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                run.id,
                run.created_at.isoformat(),
                "Legacy",
                "running",
                "test",
                0.8,
                0,
                0,
                "[]",
                "[]",
                "test",
                json.dumps(payload, default=str),
            ),
        )
        db.execute("PRAGMA user_version=2")
    repo = Database(path)
    assert repo.get(run.id).classification.industry_code == "000007"
    with sqlite3.connect(path) as db:
        assert (
            db.execute("SELECT industry_code FROM industy_classification").fetchone()[0] == "000007"
        )
        assert "naics" not in db.execute("SELECT payload FROM industy_classification").fetchone()[0]
    assert Database(path).get(run.id).classification.industry_code == "000007"


def test_invalid_grounding_is_saved_as_error(tmp_path):
    class BadGrounding(FakeClients):
        def post(self, provider, payload):
            result = super().post(provider, payload)
            if provider == "exa":
                result["output"]["grounding"] = {"invalid": "object"}
            return result

    with TestClient(
        create_app(Settings(database_path=tmp_path / "bad.db"), BadGrounding())
    ) as client:
        result = client.post("/api/runs", json={"company_name": "Example"}).json()
        assert result["status"] == "error"
        assert "grounding" in result["error"]


def test_rejected_scores_persist_and_backfill_v3(tmp_path):
    import sqlite3

    class Rejected(FakeClients):
        def post(self, provider, payload):
            response = super().post(provider, payload)
            if provider == "typesafe":
                response["answers"]["sufficient_0"]["noul"] = 0.2
            return response

    path = tmp_path / "rejected.db"
    with TestClient(create_app(Settings(database_path=path), Rejected())) as client:
        result = client.post("/api/runs", json={"company_name": "Example"}).json()
    assert result["status"] == "needs_review"
    assert result["selected_source_index"] is None
    assert len(result["stages"]) == 2
    sql = "SELECT identity_score,identity_confidence,description_sufficiency_score FROM industy_classification"
    with sqlite3.connect(path) as db:
        assert db.execute(sql).fetchone() == (1.0, 1.0, 0.2)
        db.execute("UPDATE industy_classification SET identity_score=NULL, identity_confidence=NULL, description_sufficiency_score=NULL")
        db.execute("PRAGMA user_version=3")
    Database(path)
    with sqlite3.connect(path) as db:
        assert db.execute(sql).fetchone() == (1.0, 1.0, 0.2)
        assert db.execute("PRAGMA user_version").fetchone()[0] == 4
    assert Database(path).get(result["id"]).selected_source_index is None


def test_bad_taxonomy_returns_json_and_recovers_without_provider_calls(tmp_path, monkeypatch):
    import app.taxonomy as taxonomy_module
    from app.config import ROOT

    class Counting(FakeClients):
        def __init__(self):
            self.calls = 0

        def post(self, provider, payload):
            self.calls += 1
            return super().post(provider, payload)

    canonical = (ROOT / "data/taxonomy.json").read_text()
    data = tmp_path / "data"
    data.mkdir()
    target = data / "taxonomy.json"
    monkeypatch.setattr(taxonomy_module, "ROOT", tmp_path)
    providers = Counting()
    invalid_parent = json.loads(canonical)
    next(n for n in invalid_parent["nodes"] if n["tier"] == 3)["parent_id"] = "missing"
    with TestClient(create_app(Settings(database_path=tmp_path / "runs.db"), providers)) as client:
        # Missing file, invalid JSON, and invalid relationships all fail safely.
        for content in (None, "{broken", json.dumps(invalid_parent)):
            if content is not None:
                target.write_text(content)
            assert client.get("/api/health").json()["ready"] is False
            response = client.post("/api/runs", json={"company_name": "Example"})
            assert response.status_code == 503
            assert "taxonomy" in response.json()["detail"].lower()
        assert providers.calls == 0
        assert client.get("/api/runs").json() == []
        target.write_text(canonical)
        assert client.get("/api/health").json()["ready"] is True
        assert client.post("/api/runs", json={"company_name": "Example"}).json()["status"] == "classified"
        assert providers.calls == 3
