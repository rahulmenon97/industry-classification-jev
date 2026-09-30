import unittest

import pipeline_e2e as p


class EndToEndTests(unittest.TestCase):
    def test_search_uses_name_only(self):
        r = p.exa_request("Example")
        self.assertNotIn("includeDomains", r)
        self.assertEqual(r["numResults"], 3)

    def test_identity_gate_blocks_mismatch(self):
        response = {
            "answers": {
                "identity_0": {
                    "type": "choice",
                    "choice": "different_company",
                    "probabilities": {
                        "match": 0.01,
                        "different_company": 0.98,
                        "insufficient_evidence": 0.01,
                    },
                    "confidence": 0.95,
                },
                "sufficient_0": {"type": "noul", "noul": 0.99},
            }
        }
        selected, checks = p.select_source(response, [{}], 0.8)
        self.assertIsNone(selected)
        response["answers"]["identity_0"].update(
            choice="match",
            probabilities={"match": 0.99, "different_company": 0.01, "insufficient_evidence": 0.0},
        )
        self.assertEqual(p.select_source(response, [{}], 0.8)[0], 0)
        response["answers"]["sufficient_0"]["noul"] = 0.4
        self.assertIsNone(p.select_source(response, [{}], 0.8)[0])

    def test_domain_boundary(self):
        self.assertTrue(p.same_domain("https://www.example.com/about", "example.com"))
        self.assertFalse(p.same_domain("https://example.com.evil.test", "example.com"))

    def test_unknown_cost_not_zero(self):
        report = {
            "planned_cases": 1,
            "cases": [
                {
                    "status": "error",
                    "elapsed_ms": 12,
                    "stages": [{"provider": "exa", "name": "retrieval", "elapsed_ms": 10}],
                }
            ],
        }
        p.summarize(report)
        self.assertIsNone(report["summary"]["estimated_cost_usd"])
        self.assertEqual(report["summary"]["stages_with_unknown_cost"], 1)


def test_abstentions_excluded_from_accepted_accuracy():
    report = {
        "planned_cases": 3,
        "cases": [
            {"status": status, "actual": actual, "classification_correct": correct,
             "elapsed_ms": 10, "stages": []}
            for status, actual, correct in [
                ("classified", {"path_ids": ["a", "b", "c"]}, True),
                ("abstained", {"choice": "outside_taxonomy", "path_ids": None}, False),
                ("abstained", {"choice": "insufficient_evidence", "path_ids": None}, False),
            ]
        ],
    }
    p.summarize(report)
    assert report["summary"]["classified_cases"] == 1
    assert report["summary"]["abstained_cases"] == 2
    assert report["summary"]["classification_accuracy_on_classified"] == 1
    assert report["summary"]["classification_success_on_attempted"] == 1 / 3


def test_cli_saves_abstained_status(tmp_path, monkeypatch):
    import json

    data = p.ROOT / "data"
    monkeypatch.setattr(p, "ROOT", tmp_path)
    monkeypatch.setattr(p.jev, "load_env", lambda: None)
    monkeypatch.setenv("EXA_API_KEY", "fake-exa")
    monkeypatch.setenv("TYPESAFE_API_KEY", "fake-jev")
    monkeypatch.setattr(p, "exa_call", lambda *args: {
        "results": [{"title": "Example", "url": "https://example.com", "text": "Business evidence"}]
    })

    def answer(payload, key):
        answers = {}
        for name, q in payload["questions"].items():
            if q["type"] == "noul":
                answers[name] = {"type": "noul", "noul": 1}
            else:
                choice = "outside_taxonomy" if name == "industry" else "match"
                answers[name] = {"type": "choice", "choice": choice, "confidence": 1,
                                 "probabilities": {k: float(k == choice) for k in q["criteria"]}}
        return {"model": "test-model", "answers": answers, "usage": {}}

    monkeypatch.setattr(p.jev, "call_api", answer)
    assert p.main(["--data-dir", str(data), "--limit", "1"]) == 0
    report = json.loads(next((tmp_path / "results").glob("*/report.json")).read_text())
    assert report["cases"][0]["status"] == "abstained"
    assert report["summary"]["classified_cases"] == 0
    assert report["summary"]["abstained_cases"] == 1
    assert report["summary"]["classification_accuracy_on_classified"] is None
