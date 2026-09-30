from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

Probability = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
Nonnegative = Annotated[float, Field(ge=0, allow_inf_nan=False)]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, validate_assignment=True)


class RunRequest(Model):
    company_name: str = Field(min_length=2, max_length=160)
    taxonomy: Literal["industry_v2"] = "industry_v2"


class Source(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title: str = ""
    url: HttpUrl
    text: str = ""
    highlights: list[str] = Field(default_factory=list)


class CompanyProfile(Model):
    company_name: str = Field(min_length=1)
    company_url: HttpUrl | None
    description: str = Field(min_length=1)
    ambiguity: str
    identity_resolved: bool = False


class SearchResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    results: list[Source]
    costDollars: dict = Field(default_factory=dict)
    output: dict | None = None


class Choice(Model):
    type: Literal["choice"]
    choice: str
    probabilities: dict[str, Probability]
    confidence: Probability

    @model_validator(mode="after")
    def consistent(self):
        if (
            self.choice not in self.probabilities
            or abs(sum(self.probabilities.values()) - 1) > 0.01
        ):
            raise ValueError("Invalid choice distribution")
        if self.probabilities[self.choice] + 0.0001 < max(self.probabilities.values()):
            raise ValueError("Choice must have maximal probability")
        return self


class Noul(Model):
    type: Literal["noul"]
    noul: Probability


class Usage(BaseModel):
    model_config = ConfigDict(extra="ignore")
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)


class JevResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    model: str
    answers: dict[str, Annotated[Choice | Noul, Field(discriminator="type")]]
    usage: Usage = Field(default_factory=Usage)


class Assessment(Model):
    source_index: int
    identity: Choice
    sufficiency: Noul
    accepted: bool


class Classification(Model):
    answer: Choice
    path_ids: list[str] | None = None
    path_names: list[str] | None = None
    industry_code: str | None = None


class Stage(Model):
    name: str
    provider: Literal["exa", "typesafe"]
    elapsed_ms: Nonnegative = 0
    estimated_cost_usd: Nonnegative | None = None
    usage: Usage = Field(default_factory=Usage)
    model: str | None = None
    request: dict = Field(default_factory=dict)
    response: dict | None = None
    error: str | None = None


class Run(Model):
    id: str = Field(default_factory=lambda: str(uuid4()))
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    request: RunRequest
    status: Literal[
        "running", "classified", "needs_review", "no_evidence", "abstained", "error", "interrupted"
    ] = "running"
    taxonomy_version: str
    taxonomy_snapshot: dict
    sources: list[Source] = Field(default_factory=list)
    assessments: list[Assessment] = Field(default_factory=list)
    selected_source_index: int | None = None
    classification: Classification | None = None
    stages: list[Stage] = Field(default_factory=list)
    elapsed_ms: Nonnegative = 0
    error: str | None = None
    review_reason: str | None = None
    estimated_cost_usd: Nonnegative | None = None
    known_cost_subtotal_usd: Nonnegative = 0
    identity_threshold: Probability = 0.8
    pricing_note: str = "Exa returned estimate; Jev 1.13 input $0.042/M, output free (2026-09-27). Unknown usage/model cost remains null. Not invoice totals."
    timing_note: str = "Client wall time including network; stage time includes response validation and excludes DB writes. Run time excludes final save."
    company_profile: CompanyProfile | None = None
    exa_results: list[Source] = Field(default_factory=list)
    exa_grounding: list[dict] = Field(default_factory=list)
    description_kind: str = "source_excerpt"
    expected_tier3_id: str | None = None
    accuracy_note: str = "Unlabeled interactive input: accuracy is not measured. Confidence is not a correctness guarantee."
