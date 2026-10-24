from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RuleInput(StrictModel):
    yaml_content: str = Field(min_length=1, max_length=65536)


class RuleUpdate(RuleInput):
    expected_version: int = Field(ge=1)


class ToggleInput(StrictModel):
    enabled: bool
    expected_version: int = Field(ge=1)


Scalar = StrictStr | StrictInt | StrictBool


class Event(StrictModel):
    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")
    timestamp: datetime
    fields: dict[str, Scalar] = Field(min_length=1, max_length=100)

    @field_validator("timestamp")
    @classmethod
    def aware(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Event timestamps require a timezone")
        return value

    @field_validator("fields")
    @classmethod
    def bounded_fields(cls, value):
        if any(len(k) > 128 or (isinstance(v, str) and len(v) > 8192) for k, v in value.items()):
            raise ValueError("Event fields exceed size limits")
        return value


class Dataset(StrictModel):
    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,100}$")
    rule_id: UUID
    category: Literal["malicious", "benign"]
    technique: str = Field(pattern=r"^T\d{4}(\.\d{3})?$")
    logsource: dict[str, str] = Field(min_length=1, max_length=5)
    events: Annotated[list[Event], Field(min_length=1, max_length=1000)]
    expected_event_ids: Annotated[list[str], Field(max_length=1000)]
    expected_detection: StrictBool

    @model_validator(mode="after")
    def consistent(self):
        ids = [e.id for e in self.events]
        expected = self.expected_event_ids
        if len(set(ids)) != len(ids) or len(set(expected)) != len(expected):
            raise ValueError("Event IDs and expected IDs must each be unique")
        if not set(expected).issubset(ids):
            raise ValueError("Expected IDs must reference dataset events")
        if bool(expected) != self.expected_detection:
            raise ValueError("Expected detection must agree with expected event IDs")
        if (self.category == "malicious") != self.expected_detection:
            raise ValueError("Malicious fixtures require matches; benign fixtures require no matches")
        return self


class RunInput(StrictModel):
    rule_id: UUID
    dataset_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{1,100}$")
    dataset: Dataset | None = None

    @model_validator(mode="after")
    def exactly_one(self):
        if (self.dataset_id is None) == (self.dataset is None):
            raise ValueError("Provide exactly one of dataset_id or dataset")
        return self
