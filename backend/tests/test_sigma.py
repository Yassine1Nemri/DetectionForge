import pytest

from app.core.config import Settings
from app.services.sigma_service import DomainError, convert_rule, parse_rule


def test_real_splunk_conversion_scopes_source_and_maps_fields(content):
    output = convert_rule(content, {"EventID": "EventCode", "CommandLine": "process_command_line"})
    (query,) = output["queries"]
    assert "EventCode=1" in query
    assert 'source="WinEventLog:Microsoft-Windows-Sysmon/Operational"' in query
    assert "process_command_line IN" in query
    assert "EncodedCommand" in query
    assert output["executed"] is False


@pytest.mark.parametrize(
    "change",
    [
        lambda c: c + "\ntitle: duplicate",
        lambda c: c.replace(
            "condition: selection_image and selection_command", "condition: unknown_selection"
        ),
        lambda c: c.replace(
            "condition: selection_image and selection_command", "condition: selection_image and ("
        ),
        lambda c: c.replace("level: medium", "level: invented"),
        lambda c: c.replace("id: 2918a3bc-8ac1-4c37-8ec2-b7dd523a7e56", "id: not-a-uuid"),
        lambda c: c.replace("Image|endswith:", "Image|invented:"),
        lambda c: c + "\nextra: !!python/object/apply:os.system [echo bad]",
        lambda c: c + "\nextra: &a [one]\nother: *a",
        lambda c: c + "\n---\ntitle: another document",
        lambda c: c + "\nextra: " + "[" * 35 + "a" + "]" * 35,
    ],
)
def test_reject_invalid_or_unsafe_yaml(content, change):
    with pytest.raises(DomainError):
        parse_rule(change(content))


def test_conversion_rejects_unknown_profile(content):
    with pytest.raises(DomainError, match="profile"):
        convert_rule(content.replace("product: windows", "product: linux"), {})


def test_mapping_rejects_spl_injection():
    with pytest.raises(ValueError):
        Settings(splunk_field_mappings={"Image": "Image | delete"})


def test_size_limit():
    with pytest.raises(DomainError, match="64 KiB"):
        parse_rule("x" * 65537)
