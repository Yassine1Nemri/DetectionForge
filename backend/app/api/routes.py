from datetime import timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import ROOT, get_settings
from app.core.database import get_db
from app.models.entities import Rule, RuleVersion, TestRun, utcnow
from app.schemas.inputs import RuleInput, RuleUpdate, RunInput, ToggleInput
from app.services.fixtures import datasets
from app.services.offline import evaluate
from app.services.sigma_service import DomainError, convert_rule, parse_rule

router = APIRouter(prefix="/api")
DB = Annotated[Session, Depends(get_db)]


def rule_or_404(db, rule_id):
    row = db.get(Rule, str(rule_id))
    if row is None:
        raise DomainError("Rule not found", 404)
    return row


def snapshot(db, row):
    return db.scalar(
        select(RuleVersion).where(RuleVersion.rule_id == row.id, RuleVersion.version == row.current_version)
    )


def iso(value):
    return value.replace(tzinfo=value.tzinfo or timezone.utc).isoformat()


def summary(db, row):
    runs = list(
        db.scalars(
            select(TestRun)
            .where(TestRun.rule_id == row.id, TestRun.rule_version == row.current_version)
            .order_by(TestRun.created_at.desc())
        )
    )
    latest = runs[0] if runs else None
    return {
        "id": row.id,
        "title": row.title,
        "level": row.level,
        "logsource": row.logsource,
        "techniques": row.techniques,
        "enabled": row.enabled,
        "version": row.current_version,
        "updated_at": iso(row.updated_at),
        "validation_status": "valid",
        "latest_test": (
            {
                "id": latest.id,
                "passed": latest.report["passed"],
                "mode": "offline",
                "dataset_id": latest.dataset_id,
            }
            if latest
            else None
        ),
    }


@router.get("/health")
def health(db: DB):
    db.execute(select(1))
    return {"status": "ok", "phase": 1, "splunk": "not implemented"}


@router.get("/overview")
def overview(db: DB):
    rows = list(db.scalars(select(Rule)))
    rules = [summary(db, row) for row in rows]
    runs = list(db.scalars(select(TestRun).order_by(TestRun.created_at.desc())))
    tested = sum(r["latest_test"] is not None for r in rules)
    passed = sum(r.report["passed"] for r in runs)
    return {
        "total_rules": len(rules),
        "valid_rules": len(rules),
        "invalid_rules": 0,
        "tested_detections": tested,
        "untested_detections": len(rules) - tested,
        "passing_tests": passed,
        "failing_tests": len(runs) - passed,
        "test_pass_rate": passed / len(runs) if runs else None,
        "mode": "offline",
        "note": "Only validated imports are stored. Tested detection counts refer to the current version; run totals include history.",
        "recent_runs": [run_dict(r) for r in runs[:8]],
    }


@router.post("/rules/validate")
def validate(payload: RuleInput):
    return {
        "valid": True,
        **parse_rule(payload.yaml_content).metadata,
        "warning": "ATT&CK tags are extracted; catalog reference validation is planned for Phase 3.",
    }


@router.post("/rules/convert")
def convert(payload: RuleInput):
    return convert_rule(payload.yaml_content, get_settings().splunk_field_mappings)


@router.get("/example-rule")
def example_rule():
    return {"yaml_content": (ROOT / "detections/windows/powershell/suspicious_powershell.yml").read_text()}


@router.get("/rules")
def list_rules(db: DB, q: str = Query(default="", max_length=100), level: str | None = None):
    rows = db.scalars(select(Rule).order_by(Rule.updated_at.desc()))
    return [
        summary(db, r)
        for r in rows
        if (not q or q.casefold() in (r.title + " " + " ".join(r.techniques)).casefold())
        and (not level or r.level == level)
    ]


@router.post("/rules", status_code=201)
def import_rule(payload: RuleInput, db: DB):
    parsed = parse_rule(payload.yaml_content)
    metadata = parsed.metadata
    if db.get(Rule, metadata["id"]):
        raise DomainError("Rule already exists; edit it to create a new version", 409)
    row = Rule(**metadata, current_version=1)
    db.add(row)
    try:
        db.flush()
        db.add(RuleVersion(rule_id=row.id, version=1, yaml_content=payload.yaml_content))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DomainError("Conflicting rule import; reload and try again", 409) from exc
    return {**summary(db, row), "yaml_content": payload.yaml_content}


@router.get("/rules/{rule_id}")
def get_rule(rule_id: UUID, db: DB):
    row = rule_or_404(db, rule_id)
    return {**summary(db, row), "yaml_content": snapshot(db, row).yaml_content}


@router.put("/rules/{rule_id}")
def edit_rule(rule_id: UUID, payload: RuleUpdate, db: DB):
    row = rule_or_404(db, rule_id)
    parsed = parse_rule(payload.yaml_content)
    if str(parsed.rule.id) != str(rule_id):
        raise DomainError("Rule ID cannot be changed")
    metadata = parsed.metadata
    metadata.pop("id")
    result = db.execute(
        update(Rule)
        .where(Rule.id == row.id, Rule.current_version == payload.expected_version)
        .values(**metadata, current_version=payload.expected_version + 1, updated_at=utcnow())
    )
    if result.rowcount != 1:
        db.rollback()
        raise DomainError("Rule version changed; reload before saving", 409)
    db.add(
        RuleVersion(rule_id=row.id, version=payload.expected_version + 1, yaml_content=payload.yaml_content)
    )
    db.commit()
    db.refresh(row)
    return {**summary(db, row), "yaml_content": payload.yaml_content}


@router.patch("/rules/{rule_id}/enabled")
def toggle(rule_id: UUID, payload: ToggleInput, db: DB):
    row = rule_or_404(db, rule_id)
    # State changes also advance the version, protecting concurrent writers.
    content = snapshot(db, row).yaml_content
    result = db.execute(
        update(Rule)
        .where(Rule.id == row.id, Rule.current_version == payload.expected_version)
        .values(enabled=payload.enabled, current_version=payload.expected_version + 1, updated_at=utcnow())
    )
    if result.rowcount != 1:
        db.rollback()
        raise DomainError("Rule version changed; reload before saving", 409)
    db.add(RuleVersion(rule_id=row.id, version=payload.expected_version + 1, yaml_content=content))
    db.commit()
    db.refresh(row)
    return summary(db, row)


@router.get("/rules/{rule_id}/versions")
def versions(rule_id: UUID, db: DB):
    rule_or_404(db, rule_id)
    return [
        {"version": v.version, "yaml_content": v.yaml_content, "created_at": iso(v.created_at)}
        for v in db.scalars(
            select(RuleVersion)
            .where(RuleVersion.rule_id == str(rule_id))
            .order_by(RuleVersion.version.desc())
        )
    ]


@router.get("/datasets")
def list_datasets():
    return [
        {**d.model_dump(mode="json", exclude={"events"}), "event_count": len(d.events)}
        for d in datasets().values()
    ]


@router.post("/tests/run", status_code=201)
def run_test(payload: RunInput, db: DB):
    row = rule_or_404(db, payload.rule_id)
    if not row.enabled:
        raise DomainError("Enable the rule before running tests", 409)
    dataset = payload.dataset or datasets().get(payload.dataset_id)
    if dataset is None:
        raise DomainError("Dataset not found", 404)
    version = row.current_version
    report = evaluate(parse_rule(snapshot(db, row).yaml_content), dataset)
    run = TestRun(
        rule_id=row.id,
        rule_version=version,
        dataset_id=dataset.id,
        dataset_snapshot=dataset.model_dump(mode="json"),
        report=report,
    )
    db.add(run)
    db.commit()
    return run_dict(run)


def run_dict(run):
    return {
        **run.report,
        "id": run.id,
        "rule_id": run.rule_id,
        "rule_version": run.rule_version,
        "created_at": iso(run.created_at),
    }


@router.get("/tests")
def history(db: DB, rule_id: UUID | None = None):
    query = select(TestRun).order_by(TestRun.created_at.desc()).limit(100)
    if rule_id:
        query = query.where(TestRun.rule_id == str(rule_id))
    return [run_dict(r) for r in db.scalars(query)]


@router.get("/tests/{run_id}/report")
def download_report(run_id: UUID, db: DB):
    run = db.get(TestRun, str(run_id))
    if run is None:
        raise DomainError("Test run not found", 404)
    version = db.scalar(
        select(RuleVersion).where(RuleVersion.rule_id == run.rule_id, RuleVersion.version == run.rule_version)
    )
    return JSONResponse(
        {**run_dict(run), "dataset": run.dataset_snapshot, "yaml_content": version.yaml_content},
        headers={"Content-Disposition": f'attachment; filename="detectionforge-{run.id}.json"'},
    )
