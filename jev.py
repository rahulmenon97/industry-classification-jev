#!/usr/bin/env python3
"""Small, dependency-free TypeSafe playground. Python 3.9+."""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
API = "https://api.typesafe.ai/v1/systemone"


def load_env():
    """Read simple KEY=value settings without executing shell commands."""
    path = ROOT / ".env.local"
    if path.is_file():
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            name, sep, value = line.partition("=")
            if sep and name.strip() in (
                "TYPESAFE_API_KEY",
                "JEV_MODEL",
                "EXA_API_KEY",
            ):
                os.environ.setdefault(name.strip(), value.strip().strip("\"'"))


def validate(payload):
    if not isinstance(payload, dict):
        raise ValueError("The request must be a JSON object.")
    if not isinstance(payload.get("state"), (str, dict, list)):
        raise ValueError("state must be text, an object, or an array.")
    questions = payload.get("questions")
    if not isinstance(questions, dict) or not questions:
        raise ValueError("questions must be a nonempty object.")
    for name, q in questions.items():
        if not isinstance(q, dict) or not q.get("instructions"):
            raise ValueError("Question %s needs instructions." % name)
        kind, criteria = q.get("type"), q.get("criteria")
        if kind not in ("choice", "score", "noul"):
            raise ValueError("Question %s has an unknown type." % name)
        if kind == "choice" and (not isinstance(criteria, dict) or not 1 <= len(criteria) <= 255):
            raise ValueError("Choice %s needs 1–255 named criteria." % name)
        if kind == "score" and (not isinstance(criteria, list) or not 2 <= len(criteria) <= 10):
            raise ValueError("Score %s needs 2–10 ordered descriptions." % name)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward the API key to a redirected endpoint.


def call_api(payload, key):
    request = urllib.request.Request(
        API,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
    )
    opener = urllib.request.build_opener(NoRedirect())
    try:
        with opener.open(request, timeout=45) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        hints = {
            401: "Check your API key in .env.local.",
            403: "Check your account's access to this model.",
            422: "Check the state and question definitions against the API docs.",
            429: "Rate limited. Wait before running again.",
            529: "Service overloaded. Wait before running again.",
        }
        raise ValueError(
            "HTTP %s: %s"
            % (error.code, hints.get(error.code, "API request failed. Try again later."))
        ) from None
    except (urllib.error.URLError, TimeoutError):
        raise ValueError(
            "Connection failed or timed out. Check internet access and try again. No automatic retry was made."
        ) from None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "example", nargs="?", default="support", help="Example name or path to a request JSON file"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and print the request; no network or key needed",
    )
    parser.add_argument("--model", help="Override model, e.g. a pinned version")
    args = parser.parse_args(argv)
    load_env()
    path = Path(args.example)
    if not path.is_file():
        path = ROOT / "examples" / (args.example + ".json")
    try:
        payload = json.loads(path.read_text())
        validate(payload)
        payload["model"] = (
            args.model or os.getenv("JEV_MODEL") or payload.get("model", "jev-latest")
        )
        if args.dry_run:
            print("DRY RUN — no API call made")
            print(json.dumps(payload, indent=2))
            return 0
        key = os.getenv("TYPESAFE_API_KEY", "").strip()
        if not key or key == "paste_your_key_here":
            raise ValueError(
                "Add TYPESAFE_API_KEY to the project's .env.local file, then run again. Do not paste your key into chat."
            )
        print("Calling Jev with %d questions…" % len(payload["questions"]))
        started = time.perf_counter()
        response = call_api(payload, key)
        elapsed = round((time.perf_counter() - started) * 1000, 1)
        if not isinstance(response, dict) or not isinstance(response.get("answers"), dict):
            raise ValueError("Unexpected API response: missing answers object.")
        # Defense in depth: redact a key if it ever appears in response content.
        response = json.loads(json.dumps(response).replace(key, "[REDACTED]"))
        print("Model: %s | Round-trip: %s ms" % (response.get("model", "unknown"), elapsed))
        for name, answer in response["answers"].items():
            print("\n%s:\n%s" % (name, json.dumps(answer, indent=2)))
        print("\nToken usage:", response.get("usage", {}))
        directory = ROOT / "results"
        directory.mkdir(exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        output = directory / (stamp + ".json")
        record = {
            "example": path.name,
            "requested_model": payload["model"],
            "round_trip_ms": elapsed,
            "response": response,
        }
        output.write_text(json.dumps(record, indent=2) + "\n")
        print("Saved:", output)
        return 0
    except (OSError, ValueError) as error:
        print("Error: %s" % error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
