## Industry Classification using Jev

```sh
cd /Users/rahulmenon/Projects/Jev-Test
source .venv/bin/activate
python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8765
```

Visit http://127.0.0.1:8765. Enter a company name; the app retrieves Exa evidence, checks identity and sufficiency with Jev, and classifies against the 77-leaf taxonomy. Results include the tier hierarchy, industry code, probabilities, model, tokens, timings, and estimated costs. Saved runs can be reopened or exported as JSON.

For a fresh checkout, copy `.env.example` to `.env.local` and set both `EXA_API_KEY` and `TYPESAFE_API_KEY`.

SQLite is created automatically at `storage/runs.sqlite3`. Keys stay in `.env.local`; only Exa and TypeSafe are required. The existing environment has dependencies installed. For a fresh Python 3.12 environment, run `uv sync --locked` (including test dependencies).

### Demo recording

[Watch the industry-classification demo](docs/videos/industry-classification-live-demo.mp4). This screen recording shows live company lookups and saved-result exploration, including tier details, raw JSON, timings, and estimated costs. Browser tabs and the address bar are cropped out. The recording has no audio.

## Original playground: start here on your Mac

1. Open VS Code. Choose **File → Open Folder…** and select this `jev-playground` folder.
2. Open `.env.local` in the file explorer. Replace `paste_your_key_here` with your TypeSafe API key and save. Keep the key private; do not paste it into chat. `.env.local` is ignored by Git.
3. Choose **Terminal → New Terminal**. Run:

```sh
source .venv/bin/activate
python --version
python jev.py support --dry-run
```

The version should be Python 3.12. The dry run validates and prints the request without contacting TypeSafe.

4. Make your first live request:

```sh
python jev.py support
```

This sends the example's state and questions to TypeSafe and uses your API account. The program prints the response and saves it in `results/`. It performs one request, without automatic retries.

## Try more examples

```sh
python jev.py ambiguous
python jev.py search
python jev.py examples/support.json --model jev-latest
```

- `support`: Choice, Noul, and Score in one request.
- `ambiguous`: A message with no explicit requested resolution. Look at `other` and the probabilities; ambiguity need not always mean low confidence.
- `search`: Whether a passage answers a search query.

Change the `state` in an example, save it, and rerun. Compare clear messages with unclear ones. Keep questions fixed when comparing inputs.

## Files

| File | Purpose |
| --- | --- |
| `jev.py` | HTTP client and command-line runner |
| `examples/*.json` | Editable state and questions |
| `.env.local` | Local API key and default model |
| `.env.example` | Shareable settings template without a real key |
| `docs/LEARNING_GUIDE.md` | Teammate guide: Jev concepts, primitives, payloads, diagrams, limits, costs, and evaluation |
| `docs/SETUP.md` | Python and VS Code setup, troubleshooting |
| `tests/test_jev.py` | Offline checks using mocked API calls |
| `results/` | Timestamped responses; excluded from Git |
| `.python/`, `.venv/` | Local Python installation and virtual environment |

No third-party Python packages are needed. This project calls the documented HTTP API directly. Python 3.12 is installed locally for this project; macOS Python remains unchanged.

## Verification

```sh
python -m pytest
```

For the frontend navigation regression test, run `node --test tests/test_ui.cjs` when Node.js is available.

These checks validate application behavior, not Jev's accuracy. Live model behavior can only be verified with your key and an actual API response. No successful live call is claimed by this starter.

## Sources

API shapes checked September 27, 2026:

- [TypeSafe API reference](https://docs.typesafe.ai/api)
- [Quick start](https://docs.typesafe.ai/introduction/quickstart)
- [Confidence](https://docs.typesafe.ai/confidence)
- [Models and pricing](https://docs.typesafe.ai/models)
- [Known limitations](https://docs.typesafe.ai/model-jaggedness/jev-1.13)

## Industry classification experiment

See [the current taxonomy and company cases](data/README.md).

## End-to-end company classification

See [Exa → Jev setup, reporting, cost, and accuracy](docs/END_TO_END.md). Run `python pipeline_e2e.py --dry-run` first.

## Expanded taxonomy v2

See [the 77-leaf taxonomy](data/README.md). Select it with `--data-dir data` in either evaluation runner. V2 is the default for the app and both evaluation runners.
