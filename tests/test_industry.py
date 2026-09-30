import json
import unittest

import evaluate_industry as runner
from scripts.build_industry_definitions import build


class IndustryTests(unittest.TestCase):
    def setUp(self):
        self.paths = build(json.loads((runner.DATA / "taxonomy.json").read_text()))["paths"]

    def test_request_does_not_leak_labels_or_identity(self):
        payload = runner.make_payload(
            {
                "description": "Sample activity",
                "company_name": "SECRET_NAME",
                "expected_choice": "SECRET_LABEL",
            },
            self.paths,
            "test",
        )
        serialized = json.dumps(payload)
        self.assertNotIn("SECRET_NAME", serialized)
        self.assertNotIn("SECRET_LABEL", serialized)
        self.assertNotIn("000001", serialized)
        self.assertEqual(payload["state"], {"description": "Sample activity"})

    def answer(self, choice):
        allowed = [p["leaf_id"] for p in self.paths] + list(runner.ABSTAIN)
        return {
            "answers": {
                "industry": {
                    "type": "choice",
                    "choice": choice,
                    "probabilities": {k: float(k == choice) for k in allowed},
                    "confidence": 1.0,
                }
            }
        }

    def test_fixed_mapping(self):
        for p in self.paths:
            result = runner.decode(self.answer(p["leaf_id"]), self.paths)
            self.assertEqual(result["path_ids"], p["path_ids"])
            self.assertEqual(result["industry_code"], p["industry_code"])

    def test_abstentions_have_no_code_or_path(self):
        for choice in runner.ABSTAIN:
            result = runner.decode(self.answer(choice), self.paths)
            self.assertIsNone(result["industry_code"])
            self.assertIsNone(result["path_ids"])

    def test_invalid_model_choice_rejected(self):
        with self.assertRaises(ValueError):
            runner.decode(self.answer("invented_category"), self.paths)


def test_reserved_ids_rejected_by_builder_and_web_loader(tmp_path, monkeypatch):
    import pytest
    import app.taxonomy as web_taxonomy

    original = json.loads((runner.DATA / "taxonomy.json").read_text())
    (tmp_path / "data").mkdir()
    monkeypatch.setattr(web_taxonomy, "ROOT", tmp_path)
    for reserved in runner.ABSTAIN:
        taxonomy = json.loads(json.dumps(original))
        next(n for n in taxonomy["nodes"] if n["tier"] == 3)["id"] = reserved
        with pytest.raises(ValueError, match="reserved"):
            build(taxonomy)
        (tmp_path / "data/taxonomy.json").write_text(json.dumps(taxonomy))
        with pytest.raises(web_taxonomy.TaxonomyError):
            web_taxonomy.Taxonomy("industry_v2")
