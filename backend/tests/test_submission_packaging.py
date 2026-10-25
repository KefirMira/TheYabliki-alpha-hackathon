"""Submission fixtures/config only; no network, DB writes or LLM."""
import asyncio
import csv
import hashlib
import io
import json
from pathlib import Path
import pytest
from company_import.validation import HEADERS, audit_file
from services.dataset_analysis import DatasetManifest, canonical, sha

ROOT=Path(__file__).resolve().parents[2]

def test_synthetic_csv_matches_release(tmp_path):
    fixture=json.loads((ROOT/"backend/fixtures/submission_profiles.json").read_text(encoding="utf-8"))
    assert fixture["synthetic"] is True
    rows=fixture["profiles"]
    assert len(rows)==2
    buf=io.StringIO(newline="")
    writer=csv.DictWriter(buf,HEADERS,delimiter=";",lineterminator="\n")
    writer.writeheader();writer.writerows(rows)
    payload=buf.getvalue().encode()
    path=tmp_path/"synthetic.csv";path.write_bytes(payload)
    audit=audit_file(path)
    assert audit.report()["eligible_profiles"]==2
    raw=(ROOT/"backend/fixtures/submission_release.json").read_bytes()
    release=DatasetManifest.model_validate_json(raw)
    assert hashlib.sha256(payload).hexdigest()==release.profile_file_sha256
    assert set(release.profile_rows)=={sha(canonical(row)) for row in rows}
    assert hashlib.sha256(raw).hexdigest() in (ROOT/"compose.submission.yml").read_text()
    assert release.combination_approved and not release.payment_aggregates_approved

@pytest.mark.parametrize("password",["", "short", "REPLACE_LONG_PLACEHOLDER"])
def test_seed_rejects_unconfigured_password_before_database(monkeypatch,password):
    from submission_demo import seed
    monkeypatch.setenv("SUBMISSION_DEMO_PASSWORD",password)
    monkeypatch.delenv("SUBMISSION_SEED_DATABASE_URL",raising=False)
    with pytest.raises(ValueError,match="PASSWORD_REQUIRED"):
        asyncio.run(seed())

def test_default_compose_cannot_enable_paid_model_from_env():
    source=(ROOT/"compose.submission.yml").read_text()
    assert "DATASET_AI_TRANSPORT: fake" in source
    assert 'LLM_API_KEY: ""' in source
    assert "AI_MODE: demo" in source
    assert "test_submission_demo" in source
    assert "network_mode: service:postgres" in source
    assert "integration_demo" not in source
    image=(ROOT/"backend/Dockerfile.submission").read_text()
    assert "COPY data" not in image
    assert "requirements-runtime.txt" in image
