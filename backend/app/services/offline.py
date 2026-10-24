"""Bounded canonical-event evaluation; never executes SPL or event commands."""

import re
from time import perf_counter

from sigma.conditions import ConditionAND, ConditionFieldEqualsValueExpression, ConditionNOT, ConditionOR
from sigma.types import SigmaBool, SigmaNumber, SigmaString, SpecialChars

from app.schemas.inputs import Dataset
from app.services.sigma_service import DomainError, Parsed


def compile_expression(node):
    if isinstance(node, (ConditionAND, ConditionOR)):
        children = [compile_expression(arg) for arg in node.args]
        combine = all if isinstance(node, ConditionAND) else any
        return lambda fields: combine(child(fields) for child in children)
    if isinstance(node, ConditionNOT):
        child = compile_expression(node.args[0])
        return lambda fields: not child(fields)
    if not isinstance(node, ConditionFieldEqualsValueExpression):
        raise DomainError("Offline evaluator supports field comparisons only")
    field, value = node.field, node.value
    if isinstance(value, SigmaString):
        parts = []
        for part in value.s:
            if isinstance(part, str):
                parts.append(re.escape(part))
            elif part == SpecialChars.WILDCARD_MULTI:
                parts.append(".*")
            else:
                raise DomainError("Unsupported offline string construct")
        pattern = re.compile("".join(parts), re.IGNORECASE | re.DOTALL)
        return lambda fields: (
            isinstance(fields.get(field), str) and pattern.fullmatch(fields[field]) is not None
        )
    if isinstance(value, SigmaNumber):
        return lambda fields: type(fields.get(field)) is int and fields[field] == value.number
    if isinstance(value, SigmaBool):
        return lambda fields: type(fields.get(field)) is bool and fields[field] == value.boolean
    raise DomainError(f"Unsupported offline value type: {type(value).__name__}")


def preflight(parsed: Parsed):
    # Validate every selection, even branches a condition never evaluates.
    for name, selection in parsed.raw["detection"].items():
        if name == "condition":
            continue
        if not isinstance(selection, dict) or not selection:
            raise DomainError("Offline selections must be nonempty field mappings")
        for key, values in selection.items():
            field, *modifiers = key.split("|")
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.]{0,127}", field):
                raise DomainError("Offline fields must be simple identifiers")
            if (
                set(modifiers) - {"contains", "startswith", "endswith", "all"}
                or len(set(modifiers)) != len(modifiers)
                or len(set(modifiers) & {"contains", "startswith", "endswith"}) > 1
            ):
                raise DomainError(f"Unsupported offline modifiers: {key}")
            items = values if isinstance(values, list) else [values]
            if not items or len(items) > 100:
                raise DomainError("Offline value lists must contain 1–100 items")
            for value in items:
                if type(value) not in (str, int, bool):
                    raise DomainError("Offline values must be strings, integers, or booleans")
                if isinstance(value, str) and ("*" in value or "?" in value):
                    raise DomainError("Explicit wildcard values are unsupported offline")
                if modifiers and type(value) is not str:
                    raise DomainError("Offline modifiers require string values")
    return [compile_expression(c.parsed) for c in parsed.rule.detection.parsed_condition]


def evaluate(parsed: Parsed, dataset: Dataset) -> dict:
    start = perf_counter()
    if str(dataset.rule_id) != str(parsed.rule.id):
        raise DomainError("Dataset rule identifier does not match the selected rule")
    if dataset.logsource != parsed.raw["logsource"]:
        raise DomainError("Dataset logsource does not match the rule")
    if dataset.technique not in parsed.metadata["techniques"]:
        raise DomainError("Dataset technique is not mapped by the rule")
    if (
        dataset.logsource.get("product") != "windows"
        or dataset.logsource.get("category") != "process_creation"
        or dataset.logsource.get("service") not in (None, "sysmon")
        or set(dataset.logsource) - {"product", "category", "service"}
    ):
        raise DomainError("Offline Phase 1 supports Windows process_creation fixtures only")
    if any(type(e.fields.get("EventID")) is not int or e.fields["EventID"] != 1 for e in dataset.events):
        raise DomainError("Process creation fixtures require canonical Sysmon EventID 1")
    conditions = preflight(parsed)
    actual = {event.id for event in dataset.events if any(c(event.fields) for c in conditions)}
    expected = set(dataset.expected_event_ids)
    all_ids = {event.id for event in dataset.events}
    tp, fp, fn, tn = (
        len(actual & expected),
        len(actual - expected),
        len(expected - actual),
        len(all_ids - (actual | expected)),
    )
    return {
        "mode": "offline",
        "scope": "synthetic fixture evaluation; no Splunk search was performed",
        "dataset_id": dataset.id,
        "category": dataset.category,
        "passed": actual == expected and bool(actual) == dataset.expected_detection,
        "expected_detection": dataset.expected_detection,
        "actual_detection": bool(actual),
        "expected_event_ids": sorted(expected),
        "actual_event_ids": sorted(actual),
        "missing_event_ids": sorted(expected - actual),
        "unexpected_event_ids": sorted(actual - expected),
        "matched_events": [e.model_dump(mode="json") for e in dataset.events if e.id in actual],
        "metrics": {
            "true_positives": tp,
            "false_positives": fp,
            "true_negatives": tn,
            "false_negatives": fn,
            "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None,
        },
        "duration_ms": round((perf_counter() - start) * 1000, 3),
    }
