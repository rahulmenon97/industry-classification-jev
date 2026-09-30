"""Compatibility conversion for saved runs written before industry-code naming."""

import json

KEYS = {
    "dummy_naics": "industry_code",
    "dummy_naics_code": "industry_code",
    "naics_code": "industry_code",
    "naics_status": "industry_code_status",
    "naics_policy": "industry_code_policy",
}


def upgrade_payload(value):
    if isinstance(value, dict):
        return {KEYS.get(k, k): upgrade_payload(v) for k, v in value.items()}
    if isinstance(value, list):
        return [upgrade_payload(v) for v in value]
    return value


def load_run(payload):
    from app.models import Run

    return Run.model_validate(upgrade_payload(json.loads(payload)))
