def test_health_and_empty_stats(client):
    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    stats = client.get("/api/v1/stats")
    assert stats.status_code == 200
    body = stats.json()
    assert body["total_documents"] == 0
    assert body["pass_rate"] == 0.0


def test_sample_scenarios_routing_and_manual_review_workflow(client):
    samples_resp = client.get("/api/v1/samples")
    assert samples_resp.status_code == 200
    assert len(samples_resp.json()) == 4

    # 1. Valid passport -> PASS
    pass_resp = client.post("/api/v1/samples/valid-passport/run")
    assert pass_resp.status_code == 201
    pass_doc = pass_resp.json()
    assert pass_doc["status"] == "PASS"
    assert pass_doc["outcome"]["final_decision"] == "PASS"
    assert pass_doc["extracted_fields"]["document_number"] == "Z8492014"
    assert len(pass_doc["audit_logs"]) >= 5

    # 2. Bank statement with name discrepancy -> MANUAL_REVIEW
    review_resp = client.post("/api/v1/samples/bank-statement-review/run")
    assert review_resp.status_code == 201
    review_doc = review_resp.json()
    assert review_doc["status"] == "MANUAL_REVIEW"
    assert any(
        f["rule_code"] == "APPLICANT_NAME_DISCREPANCY"
        for f in review_doc["outcome"]["validation_flags"]
    )

    # Analyst resolves manual review -> PASS + audit log recorded
    resolve_resp = client.post(
        f"/api/v1/documents/{review_doc['id']}/review",
        json={
            "decision": "PASS",
            "reviewer_name": "Shriyansh Gupta",
            "notes": "Verified middle name matches supporting KYC profile.",
        },
    )
    assert resolve_resp.status_code == 200
    resolved = resolve_resp.json()
    assert resolved["status"] == "PASS"
    assert resolved["outcome"]["initial_decision"] == "MANUAL_REVIEW"
    assert resolved["outcome"]["final_decision"] == "PASS"
    assert resolved["outcome"]["reviewed_by"] == "Shriyansh Gupta"
    assert any(log["event_type"] == "MANUAL_REVIEW_SUBMITTED" for log in resolved["audit_logs"])

    # 3. Expired driver's license + DOB conflict -> FAIL
    fail_resp = client.post("/api/v1/samples/expired-license-fail/run")
    assert fail_resp.status_code == 201
    fail_doc = fail_resp.json()
    assert fail_doc["status"] == "FAIL"
    flag_codes = {f["rule_code"] for f in fail_doc["outcome"]["validation_flags"]}
    assert "DOCUMENT_EXPIRED" in flag_codes
    assert "APPLICANT_DOB_MISMATCH" in flag_codes

    # 4. Stats reflect all processed records
    stats = client.get("/api/v1/stats").json()
    assert stats["total_documents"] == 3
    assert stats["passed"] == 2
    assert stats["failed"] == 1
    assert stats["manual_review"] == 0

    # 5. Global audit logs populated
    logs = client.get("/api/v1/audit-logs").json()
    assert len(logs) >= 15


def test_file_upload_txt_document(client):
    content = (
        "FORM W-2 WAGE AND TAX STATEMENT\n"
        "Taxpayer Name: Kabir Singh\n"
        "Tax ID: TIN-44120-IN\n"
        "Employer Name: FinCore Analytics Ltd\n"
        "Statement Period: Tax Year 2025\n"
        "Issue Date: 2026-01-15\n"
        "Currency: USD\n"
        "Total Wages: $98,500.00\n"
    ).encode("utf-8")

    resp = client.post(
        "/api/v1/documents/verify",
        files={"file": ("w2_kabir.txt", content, "text/plain")},
        data={"doc_type": "tax_document", "applicant_name": "Kabir Singh"},
    )
    assert resp.status_code == 201
    doc = resp.json()
    assert doc["status"] == "PASS"
    assert doc["extracted_fields"]["full_name"] == "Kabir Singh"
    assert doc["extracted_fields"]["total_amount"] == 98500.0
