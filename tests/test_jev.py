import contextlib
import io
import os
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

import jev


class PlaygroundTests(unittest.TestCase):
    def test_all_examples_validate_without_network(self):
        for path in (jev.ROOT / "examples").glob("*.json"):
            with patch.object(jev, "call_api") as api, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(jev.main([str(path), "--dry-run"]), 0)
                api.assert_not_called()

    def test_missing_key_does_not_call_api(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(jev, "load_env"),
            patch.object(jev, "call_api") as api,
            contextlib.redirect_stderr(io.StringIO()),
        ):
            self.assertEqual(jev.main(["support"]), 1)
            api.assert_not_called()

    def test_invalid_question_rejected(self):
        with self.assertRaises(ValueError):
            jev.validate(
                {
                    "state": "hello",
                    "questions": {
                        "x": {"type": "score", "instructions": "Rate", "criteria": ["one"]}
                    },
                }
            )

    def test_success_saves_response_without_key(self):
        example = str(jev.ROOT / "examples" / "support.json")
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(jev, "ROOT", Path(directory)),
            patch.dict(os.environ, {"TYPESAFE_API_KEY": "test-secret"}),
            patch.object(
                jev,
                "call_api",
                return_value={
                    "model": "test",
                    "answers": {"x": {"noul": 0.8}},
                    "usage": {"input_tokens": 10},
                },
            ),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(jev.main([example]), 0)
            files = list((Path(directory) / "results").glob("*.json"))
            self.assertEqual(len(files), 1)
            self.assertNotIn("test-secret", files[0].read_text())

    def test_http_error_hides_response_body(self):
        with patch("urllib.request.build_opener") as factory:
            factory.return_value.open.side_effect = urllib.error.HTTPError(
                jev.API, 401, "Unauthorized", {}, None
            )
            with self.assertRaisesRegex(ValueError, "Check your API key"):
                jev.call_api({}, "test-secret")


if __name__ == "__main__":
    unittest.main()
