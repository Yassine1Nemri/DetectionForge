import pytest
from pydantic import ValidationError

from app.schemas.inputs import Dataset
from app.services.offline import evaluate
from app.services.sigma_service import DomainError, parse_rule

POS = "powershell-encoded-positive"
NEG = "powershell-admin-negative"


def test_positive_and_negative_fixtures(content, fixtures):
    positive = evaluate(parse_rule(content), fixtures[POS])
    assert positive["passed"]
    assert positive["actual_event_ids"] == ["ps-encoded", "ps-short-switch"]
    assert positive["metrics"] == {
        "true_positives": 2,
        "false_positives": 0,
        "true_negatives": 1,
        "false_negatives": 0,
        "precision": 1.0,
        "recall": 1.0,
    }
    negative = evaluate(parse_rule(content), fixtures[NEG])
    assert negative["passed"]
    assert negative["metrics"]["true_negatives"] == 2
    assert negative["metrics"]["precision"] is None
    assert negative["metrics"]["recall"] is None


def test_false_negatives_are_failures(content, fixtures):
    report = evaluate(
        parse_rule(content.replace(" -enc ", " -no-match ").replace(" -EncodedCommand ", " -no-match-too ")),
        fixtures[POS],
    )
    assert report["passed"] is False
    assert report["metrics"]["false_negatives"] == 2
    assert report["missing_event_ids"] == ["ps-encoded", "ps-short-switch"]
    assert report["metrics"]["recall"] == 0


def test_false_positives_are_failures(content, fixtures):
    broad = content.replace("selection_image and selection_command", "selection_image")
    report = evaluate(parse_rule(broad), fixtures[NEG])
    assert report["passed"] is False
    assert report["metrics"]["false_positives"] == 2
    assert report["metrics"]["precision"] == 0


def test_unsupported_branch_rejected_even_when_short_circuited(content, fixtures):
    unsupported = content.replace("CommandLine|contains:", "CommandLine|re:")
    with pytest.raises(DomainError, match="modifiers"):
        evaluate(parse_rule(unsupported), fixtures[NEG])


@pytest.mark.parametrize(
    "condition",
    [
        "selection_image and selection_command",
        "all of selection_*",
        "selection_image and not (not selection_command)",
    ],
)
def test_ast_boolean_conditions(content, fixtures, condition):
    assert evaluate(
        parse_rule(content.replace("selection_image and selection_command", condition)), fixtures[POS]
    )["passed"]


def test_case_insensitivity(content, fixtures):
    data = fixtures[POS].model_copy(deep=True)
    for event in data.events:
        event.fields = {
            key: value.upper() if isinstance(value, str) else value for key, value in event.fields.items()
        }
    assert evaluate(parse_rule(content), data)["passed"]


@pytest.mark.parametrize(
    "mutation",
    [
        lambda d: d["events"].append(d["events"][0]),
        lambda d: d.update(expected_event_ids=["absent"]),
        lambda d: d.update(expected_detection=False),
        lambda d: d["events"][0].update(timestamp="2026-10-24T00:00:00"),
        lambda d: d["events"][0].update(fields={"EventID": [1]}),
        lambda d: d.update(category="benign"),
    ],
)
def test_dataset_schema_rejects_inconsistency(fixtures, mutation):
    data = fixtures[POS].model_dump(mode="json")
    mutation(data)
    with pytest.raises(ValidationError):
        Dataset.model_validate(data)


@pytest.mark.parametrize(
    "field,value",
    [
        ("rule_id", "11111111-1111-4111-8111-111111111111"),
        ("technique", "T1110"),
        ("logsource", {"product": "linux"}),
    ],
)
def test_dataset_compatibility(content, fixtures, field, value):
    data = fixtures[POS].model_dump(mode="json")
    data[field] = value
    with pytest.raises(DomainError):
        evaluate(parse_rule(content), Dataset.model_validate(data))


def test_no_wildcard_fallback(content, fixtures):
    with pytest.raises(DomainError, match="wildcard"):
        evaluate(parse_rule(content.replace(" -enc ", "*enc*")), fixtures[POS])
