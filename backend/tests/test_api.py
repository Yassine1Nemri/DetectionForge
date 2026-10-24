RULE = "2918a3bc-8ac1-4c37-8ec2-b7dd523a7e56"


def imported(client, content):
    response = client.post("/api/rules", json={"yaml_content": content})
    assert response.status_code == 201, response.text
    return response.json()


def test_empty_database_has_no_fabricated_results(client):
    overview = client.get("/api/overview").json()
    assert overview["total_rules"] == 0
    assert overview["recent_runs"] == []
    assert overview["test_pass_rate"] is None


def test_end_to_end_import_convert_test_and_download(client, content):
    assert client.post("/api/rules/validate", json={"yaml_content": content}).json()["valid"]
    imported(client, content)
    assert client.post("/api/rules", json={"yaml_content": content}).status_code == 409
    assert client.post("/api/rules/convert", json={"yaml_content": content}).status_code == 200
    for dataset_id in ["powershell-encoded-positive", "powershell-admin-negative"]:
        response = client.post("/api/tests/run", json={"rule_id": RULE, "dataset_id": dataset_id})
        assert response.status_code == 201, response.text
        run = response.json()
        assert run["passed"] and run["mode"] == "offline"
        report = client.get(f"/api/tests/{run['id']}/report")
        assert "attachment" in report.headers["content-disposition"]
        assert report.json()["yaml_content"] == content
        assert report.json()["dataset"]["id"] == dataset_id
    overview = client.get("/api/overview").json()
    assert overview["passing_tests"] == 2
    assert overview["tested_detections"] == 1
    assert len(client.get("/api/tests").json()) == 2
    assert len(client.get("/api/rules?q=T1059").json()) == 1
    assert client.get("/api/rules?q=absent").json() == []


def test_versions_retain_evidence_and_prevent_lost_updates(client, content):
    imported(client, content)
    run = client.post(
        "/api/tests/run", json={"rule_id": RULE, "dataset_id": "powershell-encoded-positive"}
    ).json()
    updated = content.replace("level: medium", "level: high")
    response = client.put(f"/api/rules/{RULE}", json={"yaml_content": updated, "expected_version": 1})
    assert response.status_code == 200
    assert response.json()["version"] == 2
    assert response.json()["latest_test"] is None
    assert (
        client.put(f"/api/rules/{RULE}", json={"yaml_content": content, "expected_version": 1}).status_code
        == 409
    )
    versions = client.get(f"/api/rules/{RULE}/versions").json()
    assert len(versions) == 2
    assert versions[1]["yaml_content"] == content
    assert client.get(f"/api/tests/{run['id']}/report").json()["yaml_content"] == content


def test_disabled_rule_cannot_run_and_missing_never_falls_back(client, content):
    imported(client, content)
    assert client.post("/api/tests/run", json={"rule_id": RULE, "dataset_id": "absent"}).status_code == 404
    assert (
        client.post("/api/tests/run", json={"rule_id": RULE, "dataset_id": "../../etc/passwd"}).status_code
        == 422
    )
    assert (
        client.patch(f"/api/rules/{RULE}/enabled", json={"enabled": False, "expected_version": 1}).status_code
        == 200
    )
    assert (
        client.post(
            "/api/tests/run", json={"rule_id": RULE, "dataset_id": "powershell-encoded-positive"}
        ).status_code
        == 409
    )
    assert client.get("/api/tests").json() == []


def test_invalid_inputs_and_unknown_ids(client, content):
    assert client.post("/api/rules", json={"yaml_content": "title: invalid"}).status_code == 422
    assert client.get("/api/rules/not-a-uuid").status_code == 422
    assert client.get("/api/rules/11111111-1111-4111-8111-111111111111").status_code == 404
    assert client.post("/api/tests/run", json={"rule_id": RULE}).status_code == 422
    response = client.post(
        "/api/rules/validate", content=b"x" * 2_000_001, headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 413


def test_failed_test_is_saved_as_failure(client, content):
    imported(client, content.replace("selection_image and selection_command", "selection_image"))
    report = client.post(
        "/api/tests/run", json={"rule_id": RULE, "dataset_id": "powershell-admin-negative"}
    ).json()
    assert report["passed"] is False
    assert client.get("/api/overview").json()["failing_tests"] == 1
