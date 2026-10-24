import re
from dataclasses import dataclass
from uuid import UUID

import yaml
from sigma.backends.splunk import SplunkBackend
from sigma.collection import SigmaCollection
from sigma.processing.pipeline import ProcessingItem, ProcessingPipeline
from sigma.processing.transformations import AddConditionTransformation, FieldMappingTransformation
from sigma.rule import SigmaRule


class DomainError(Exception):
    def __init__(self, message: str, status: int = 422):
        self.message, self.status = message, status
        super().__init__(message)


class BoundedLoader(yaml.SafeLoader):
    def __init__(self, stream):
        super().__init__(stream)
        self.depth = 0
        self.nodes = 0

    def compose_node(self, parent, index):
        if self.check_event(yaml.AliasEvent):
            raise DomainError("YAML aliases are not allowed")
        self.depth += 1
        self.nodes += 1
        if self.depth > 30 or self.nodes > 5000:
            raise DomainError("YAML exceeds nesting or node limit")
        try:
            return super().compose_node(parent, index)
        finally:
            self.depth -= 1

    def construct_mapping(self, node, deep=False):
        keys = set()
        for key, _ in node.value:
            name = self.construct_object(key, deep=deep)
            if not isinstance(name, str):
                raise DomainError("YAML mapping keys must be strings")
            if name in keys:
                raise DomainError(f"Duplicate YAML key: {name}")
            keys.add(name)
        return super().construct_mapping(node, deep)


@dataclass
class Parsed:
    raw: dict
    rule: SigmaRule

    @property
    def metadata(self):
        return {
            "id": str(self.rule.id),
            "title": self.rule.title,
            "level": self.rule.level.name.lower(),
            "logsource": self.raw["logsource"],
            "techniques": sorted(
                {
                    tag[7:].upper()
                    for tag in self.raw.get("tags", [])
                    if re.fullmatch(r"attack\.t\d{4}(\.\d{3})?", tag)
                }
            ),
        }


def parse_rule(content: str) -> Parsed:
    if len(content.encode("utf-8")) > 65536:
        raise DomainError("Rule exceeds 64 KiB")
    try:
        raw = yaml.load(content, Loader=BoundedLoader)
        if not isinstance(raw, dict):
            raise DomainError("Provide one Sigma rule as a YAML mapping")
        if any(k in raw for k in ("correlation", "action")):
            raise DomainError("Correlation and collection documents are not supported in Phase 1")
        if not isinstance(raw.get("title"), str) or not 1 <= len(raw["title"].strip()) <= 256:
            raise DomainError("Rule title must contain 1–256 characters")
        UUID(str(raw.get("id")))
        if raw.get("level") not in {"informational", "low", "medium", "high", "critical"}:
            raise DomainError("A valid Sigma level is required")
        if not isinstance(raw.get("tags", []), list) or not all(
            isinstance(t, str) for t in raw.get("tags", [])
        ):
            raise DomainError("Tags must be a list of strings")
        if not isinstance(raw.get("logsource"), dict) or not all(
            isinstance(v, str) for v in raw["logsource"].values()
        ):
            raise DomainError("Logsource must be a mapping of string values")
        rule = SigmaRule.from_dict(raw)
        for condition in rule.detection.parsed_condition:
            _ = condition.parsed  # pySigma conditions are lazy: force parsing before accepting.
        return Parsed(raw, rule)
    except DomainError:
        raise
    except (yaml.YAMLError, ValueError, TypeError, KeyError, AttributeError, RecursionError) as exc:
        raise DomainError(f"Invalid Sigma rule: {str(exc)[:500]}") from exc


def convert_rule(content: str, mappings: dict[str, str]) -> dict:
    parsed = parse_rule(content)
    source = parsed.raw["logsource"]
    if (
        source.get("product") != "windows"
        or source.get("category") != "process_creation"
        or source.get("service") not in (None, "sysmon")
        or set(source) - {"product", "category", "service"}
    ):
        raise DomainError("Conversion profile supports Windows Sysmon process_creation only")
    pipeline = ProcessingPipeline(
        name="DetectionForge Sysmon raw events",
        items=[
            ProcessingItem(
                identifier="sysmon_scope",
                transformation=AddConditionTransformation(
                    {"EventID": 1, "source": "WinEventLog:Microsoft-Windows-Sysmon/Operational"}
                ),
            ),
            ProcessingItem(
                identifier="deployment_fields", transformation=FieldMappingTransformation(mappings)
            ),
        ],
    )
    try:
        queries = SplunkBackend(processing_pipeline=pipeline).convert(SigmaCollection([parsed.rule]))
    except Exception as exc:
        raise DomainError(f"Splunk conversion unsupported: {str(exc)[:500]}") from exc
    return {
        "queries": queries,
        "profile": "sysmon-raw",
        "field_mappings": mappings,
        "executed": False,
        "warning": "Preview only. Verify source and field extraction against your Splunk deployment.",
    }
