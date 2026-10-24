"""Validate repository rules, convert queries, and generate actual offline evidence."""

import json
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_settings
from app.services.fixtures import datasets
from app.services.offline import evaluate
from app.services.sigma_service import convert_rule, parse_rule


def main():
    rules = {}
    for path in sorted((ROOT / "detections").rglob("*.yml")):
        content = path.read_text()
        parsed = parse_rule(content)
        if str(parsed.rule.id) in rules:
            raise ValueError("Duplicate Sigma rule ID")
        conversion = convert_rule(content, get_settings().splunk_field_mappings)
        rules[str(parsed.rule.id)] = parsed
        print(
            f"VALID + CONVERTED {path.relative_to(ROOT)} ({len(conversion['queries'])} query)"
        )
    reports = []
    for dataset in datasets().values():
        report = evaluate(rules[str(dataset.rule_id)], dataset)
        report.update(id=str(uuid4()), rule_id=str(dataset.rule_id))
        reports.append(report)
        print(
            f"{'PASS' if report['passed'] else 'FAIL'} {dataset.id}: {report['actual_event_ids']}"
        )
    if not rules or not reports:
        raise ValueError("No rules or datasets found")
    target = ROOT / "reports"
    target.mkdir(exist_ok=True)
    (target / "offline-report.json").write_text(
        json.dumps({"mode": "offline", "reports": reports}, indent=2) + "\n"
    )
    return 0 if all(report["passed"] for report in reports) else 1


if __name__ == "__main__":
    sys.exit(main())
