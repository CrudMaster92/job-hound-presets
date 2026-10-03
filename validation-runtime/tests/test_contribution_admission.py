"""Portable trust-boundary tests, also exported into the public runtime."""
import copy
from datetime import datetime, timezone
import json
import subprocess

import pytest

from server.contributions.contracts import Proposal, content_hash, validate_documents, safe_public_url
from server.contributions.validation import ValidationReceipt, effective_verification, parse_fixture
from server.contributions.admission import admitted
from server.contributions.cli import validate_change
from server.public_jobs.admission import advance_lock
from server.public_jobs.catalog import load_monitors


def proposal(base="a" * 40):
    value = Proposal.model_validate({"base_commit": base,
        "company": {"format": "jobhound-company", "schema_version": 1, "id": "acme", "name": "Acme",
                    "aliases": [], "website_url": "https://acme.example/", "logo_url": None, "facets": {"industries": [], "specialties": [], "tags": []}},
        "monitor": {"format": "jobhound-monitor", "schema_version": 1, "id": "acme", "company_id": "acme", "revision": 1,
                    "label": "Acme careers", "careers_url": "https://acme.example/careers",
                    "compatibility": {"min_jobhound_version": "0.1.0", "recipe_schema_version": 1},
                    "verification": {"status": "verified", "checked_at": None, "job_count": 999, "warnings": []},
                    "recipe": {"version": 1, "company": "Acme", "careers_url": "https://acme.example/careers", "strategy": "generic_json",
                               "allowed_hosts": ["acme.example"], "request": {"url": "https://acme.example/jobs"},
                               "mapping": {"items": "jobs", "source_id": "id", "title": "title", "url": "url", "location": "location"}}},
        "fixture": {"source_url": "https://acme.example/jobs", "fetched_at": datetime.now(timezone.utc).isoformat(),
                    "payload": {"jobs": [{"id": "1", "title": "Engineer", "url": "https://acme.example/jobs/1", "location": "Toronto"}]}},
        "ownership": {"company_url": "https://acme.example/", "explanation": "Official employer careers site links to this public endpoint.",
                      "representative_urls": ["https://acme.example/jobs/1"]}})
    from server.scrapers.models import ScraperRecipe
    value.monitor["recipe"] = ScraperRecipe.model_validate(value.monitor["recipe"]).model_dump(mode="json")
    return value


def receipt(value):
    normalized = validate_documents(value)
    return ValidationReceipt(pr_number=12, head_commit="b" * 40, base_commit=value.base_commit,
        monitor_id="acme", company_id="acme", revision=value.monitor["revision"], artifact_hash=content_hash(normalized["monitor"]),
        proposal_hash=normalized["proposal_hash"], runtime_revision="c" * 64, checked_at=datetime.now(timezone.utc),
        verdict="pass", job_count=1, pages=1, complete=True, warnings=[], representative_urls=["https://acme.example/jobs/1"],
        public_collection_eligible=True, errors=[]).model_dump(mode="json")


def test_author_claim_fixture_and_wrong_runtime_never_prove_live_validation():
    value = proposal()
    normalized = validate_documents(value)
    assert normalized["monitor"]["verification"]["status"] == "unverified"
    assert not normalized["runtime_verified"]
    assert parse_fixture(value)["job_count"] == 1
    assert not parse_fixture(value)["runtime_verified"]
    proof = receipt(value)
    assert effective_verification(normalized["monitor"], proof, runtime_revision="c" * 64)["status"] == "verified"
    with pytest.raises(ValueError):
        effective_verification(normalized["monitor"], proof, runtime_revision="d" * 64)
    changed = copy.deepcopy(normalized["monitor"])
    changed["recipe"]["mapping"]["title"] = "wrong"
    with pytest.raises(ValueError):
        effective_verification(changed, proof)
    with pytest.raises(ValueError):
        effective_verification(normalized["monitor"], {**proof, "job_count": 0})


@pytest.mark.parametrize("url", ["http://acme.example/jobs", "https://127.0.0.1/jobs", "https://[::1]/", "https://user:secret@acme.example/", "https://acme.example/?token=secret"])
def test_private_or_credential_sources_rejected(url):
    with pytest.raises(ValueError):
        safe_public_url(url)


def test_only_exact_validated_pr_merged_by_jo_authorizes_admission():
    value = proposal(); monitor = validate_documents(value)["monitor"]; proof = receipt(value)
    pull = {"number": 12, "merged": True, "merged_by": {"login": "CrudMaster92"},
            "head": {"sha": "b" * 40}, "base": {"ref": "main", "repo": {"full_name": "CrudMaster92/job-hound-presets"}}}
    assert admitted(monitor, proof, pull, "c" * 64)["status"] == "verified"
    for changed in ({"merged": False}, {"merged_by": {"login": "github-actions[bot]"}}, {"head": {"sha": "d" * 40}}):
        with pytest.raises(ValueError):
            admitted(monitor, proof, {**pull, **changed}, "c" * 64)


def commit(root):
    subprocess.run(["git", "-C", str(root), "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(root), "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "test"], check=True)
    return subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()


def write(root, files):
    for relative, value in files.items():
        path = root / relative; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(value), encoding="utf-8")


def test_git_validator_rejects_candidate_code_and_offline_only_never_passes(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "README.md").write_text("trusted base")
    base = commit(tmp_path)
    value = proposal(base); write(tmp_path, validate_documents(value)["files"]); head = commit(tmp_path)
    report = validate_change(tmp_path, base=base, head=head, pr_number=12, runtime_revision="c" * 64, live=False)
    assert report["verdict"] == "blocked" and not report["runtime_verified"]
    (tmp_path / "attack.py").write_text("raise RuntimeError('must never execute')")
    head = commit(tmp_path)
    with pytest.raises(ValueError, match="JSON"):
        validate_change(tmp_path, base=base, head=head, pr_number=12, runtime_revision="c" * 64)


def test_unverified_update_retains_working_individual_pin(tmp_path):
    from server.public_jobs.catalog import build_lock
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    value = proposal(); files = validate_documents(value)["files"]
    monitor_path = "companies/acme/monitors/acme.json"
    files[monitor_path]["verification"] = {"status": "verified", "checked_at": None, "job_count": 1, "warnings": []}
    write(tmp_path, {path: content for path, content in files.items() if not path.startswith("contributions/")})
    first = commit(tmp_path); old = build_lock(tmp_path)
    updated = copy.deepcopy(files[monitor_path]); updated["revision"] = 2; updated["verification"]["status"] = "unverified"
    write(tmp_path, {monitor_path: updated}); commit(tmp_path)
    lock = advance_lock(tmp_path, old, {})
    assert lock["monitors"][0]["catalog_commit"] == first
    assert load_monitors(tmp_path, lock)[0][0]["revision"] == 1
