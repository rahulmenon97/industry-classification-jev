import json

from pydantic import Field

from app.config import ROOT
from app.models import Model
from scripts.build_industry_definitions import build


class Node(Model):
    id: str
    tier: int = Field(ge=1, le=3)
    parent_id: str | None
    name: str
    description: str = Field(min_length=1)
    exclusions: str = ""
    industry_code: str | None = None
    industry_code_status: str | None = None


class TaxonomyError(ValueError):
    """The local taxonomy cannot be used to make classification requests."""


class Taxonomy:
    def __init__(self, name):
        try:
            self._load(name)
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
            raise TaxonomyError(
                "Industry taxonomy is unavailable or invalid. Check data/taxonomy.json, "
                "its parent relationships, reserved IDs, and the 253-leaf limit."
            ) from error

    def _load(self, name):
        if name != "industry_v2":
            raise ValueError("Unknown taxonomy")
        self.snapshot = json.loads((ROOT / "data" / "taxonomy.json").read_text())
        self.nodes = {n.id: n for n in (Node.model_validate(x) for x in self.snapshot["nodes"])}
        self.paths = build(self.snapshot)["paths"]
        self.by_leaf = {p["leaf_id"]: p for p in self.paths}
        if len(self.paths) > 253:
            raise ValueError("Too many leaves for flat Choice")
        self.criteria = {p["leaf_id"]: p["combined_definition"] for p in self.paths}
        self.criteria.update(
            insufficient_evidence="Evidence is vague, incomplete, or cannot resolve competing activities.",
            outside_taxonomy="Activity is clear but no complete industry path fits.",
        )
