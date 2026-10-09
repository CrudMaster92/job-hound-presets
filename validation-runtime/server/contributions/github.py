"""Read-only, bounded access to the fixed public contribution repository."""
from __future__ import annotations

import json
import re
import os
from typing import Any
from urllib.parse import urlsplit

import httpx
from ..external_http import external_client_kwargs
from .contracts import REPOSITORY, canonical_bytes, content_hash

MAX_GITHUB_BYTES = 2_000_000


class RepositoryUnavailable(RuntimeError):
    pass


class PublicRepository:
    def __init__(self, transport=None):
        self.transport = transport

    def read(self, path: str) -> Any:
        if not re.fullmatch(r"[A-Za-z0-9_./?=&-]+", path) or ".." in path:
            raise ValueError("Invalid fixed repository read")
        url = f"https://api.github.com/repos/{REPOSITORY}/{path}"
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "JobHound-contributions"}
        # The trusted Actions read job may use its own short-lived CI token to
        # avoid anonymous API limits. No user credential is accepted or stored.
        if os.getenv("GITHUB_ACTIONS") == "true" and os.getenv("GITHUB_TOKEN"):
            headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
        try:
            with httpx.Client(timeout=12, follow_redirects=False,
                              **external_client_kwargs(transport=self.transport)) as client:
                with client.stream("GET", url, headers=headers) as response:
                    response.raise_for_status()
                    body = bytearray()
                    for chunk in response.iter_bytes():
                        body.extend(chunk)
                        if len(body) > MAX_GITHUB_BYTES:
                            raise RepositoryUnavailable("Public repository response exceeded its limit")
            return json.loads(body)
        except (httpx.HTTPError, ValueError) as exc:
            raise RepositoryUnavailable("Public repository unavailable; keep the draft and retry inspection. Nothing was submitted.") from exc

    def document(self, commit: str, path: str) -> dict | None:
        import base64
        if not re.fullmatch(r"[a-f0-9]{40}", commit) or not re.fullmatch(r"(?:companies/[a-z0-9-]+/(?:company\.json|monitors/[a-z0-9-]+\.json)|collections/[a-z0-9-]+\.json|contributions/[a-z0-9-]+/proposal\.json)", path):
            raise ValueError("Only normalized public contribution documents can be read")
        try:
            value = self.read(f"contents/{path}?ref={commit}")
        except RepositoryUnavailable as exc:
            # Missing files are distinguishable from offline/network failures.
            if isinstance(exc.__cause__, httpx.HTTPStatusError) and exc.__cause__.response.status_code == 404:
                return None
            raise
        if value.get("type") != "file" or value.get("encoding") != "base64" or value.get("size", 0) > 512_000:
            raise ValueError("Expected a bounded JSON file, not a link or directory")
        raw = base64.b64decode(value["content"], validate=False)
        if len(raw) > 512_000:
            raise ValueError("Repository document exceeds limit")
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError("Expected a JSON object")
        return parsed

    def inspect(self, proposal, files: dict[str, dict]) -> dict:
        main = self.read("commits/main")["sha"]
        if proposal.base_commit != main:
            raise ValueError("Contribution base is outdated; inspect current main and refresh the proposal")
        company_id, monitor_id = proposal.company["id"], proposal.monitor["id"]
        old_company = self.document(main, f"companies/{company_id}/company.json")
        old_monitor = self.document(main, f"companies/{company_id}/monitors/{monitor_id}.json")
        if old_company and old_company != proposal.company:
            raise ValueError("Reuse the existing company identity unchanged; identity edits need a separate review")
        if old_monitor and proposal.monitor["revision"] <= old_monitor["revision"]:
            raise ValueError("An existing monitor needs a higher revision")
        if not old_monitor and proposal.monitor["revision"] != 1:
            raise ValueError("A new monitor starts at revision 1")
        # Full tree is bounded and non-recursive metadata only; no PR code runs.
        tree = self.read(f"git/trees/{main}?recursive=1")
        if tree.get("truncated"):
            raise RepositoryUnavailable("Repository identity index is truncated; cannot safely check duplicates")
        paths = [item["path"] for item in tree["tree"] if item.get("type") == "blob"]
        duplicate = next((path for path in paths if path.endswith(f"/monitors/{monitor_id}.json") and path != f"companies/{company_id}/monitors/{monitor_id}.json"), None)
        if duplicate:
            raise ValueError("Monitor ID already belongs to another company")
        # Catalog contains company aliases/careers identity. Candidate live URLs
        # are still rechecked by trusted validation and the human reviewer.
        for collection in proposal.collections:
            old = self.document(main, f"collections/{collection['id']}.json")
            if old:
                if collection["revision"] != old["revision"] + 1:
                    raise ValueError("Collection revision must increment exactly once")
                before = {**old, "revision": collection["revision"], "companies": collection["companies"]}
                if before != collection:
                    raise ValueError("A scraper proposal cannot change collection identity, facets or suggestions")
                others_before = [item for item in old["companies"] if item["company_id"] != company_id]
                others_after = [item for item in collection["companies"] if item["company_id"] != company_id]
                if others_before != others_after:
                    raise ValueError("A scraper proposal cannot edit unrelated collection members")
        pending = []
        for page in range(1, 6):
            pulls = self.read(f"pulls?state=open&per_page=100&page={page}")
            pending.extend(item for item in pulls if item.get("body") and f"JobHound-Monitor: {monitor_id}" in item["body"])
            if len(pulls) < 100:
                break
        else:
            raise RepositoryUnavailable("Open proposal index exceeds inspection budget")
        return {"source_commit": main, "existing_company": old_company is not None,
                "existing_monitor": old_monitor is not None,
                "pending_prs": [{"number": item["number"], "url": item["html_url"]} for item in pending]}

    def verify_submission(self, submission, files: dict[str, dict]) -> dict:
        pr = self.read(f"pulls/{submission.pr_number}")
        if pr["base"]["repo"]["full_name"].casefold() != REPOSITORY.casefold() or pr["base"]["ref"] != "main":
            raise ValueError("PR must target the canonical preset repository's main branch")
        if pr["head"]["sha"] != submission.head_commit:
            raise ValueError("PR head changed; inspect it before recording submission")
        changed = self.read(f"pulls/{submission.pr_number}/files?per_page=100")
        if len(changed) >= 100 or any(item["filename"] not in files or item["status"] not in {"added", "modified"} for item in changed):
            raise ValueError("PR contains unrelated changes; recipe proposals may only change their authored public JSON package")
        for path, expected in files.items():
            actual = self.document(submission.head_commit, path)
            if actual is None or content_hash(actual) != content_hash(expected):
                raise ValueError("PR content does not match this prepared proposal")
        url = pr["html_url"]
        if urlsplit(url).hostname != "github.com":
            raise ValueError("Unexpected PR URL")
        return {"repository": REPOSITORY, "pr_number": submission.pr_number,
                "head_commit": submission.head_commit, "url": url,
                "review_state": "merged" if pr.get("merged") else "closed" if pr["state"] == "closed" else "awaiting_review"}

    def contribution_status(self, submission, monitor):
        import base64
        from .validation import ValidationReceipt, effective_verification
        from .admission import admitted
        pull = self.read(f"pulls/{submission['pr_number']}")
        result = {"review_state": "merged" if pull.get("merged") else "closed" if pull["state"] == "closed" else "awaiting_review",
                  "validation_state": "not_checked", "publication_state": "not_published", "runtime_verified": False}
        if pull["head"]["sha"] != submission["head_commit"]:
            result.update(validation_state="head_changed", publication_state="blocked")
            return result
        path = f"contents/receipts/{submission['pr_number']}/{submission['head_commit']}.json?ref=review-receipts"
        try:
            value = self.read(path)
        except RepositoryUnavailable as exc:
            if isinstance(exc.__cause__, httpx.HTTPStatusError) and exc.__cause__.response.status_code == 404:
                return result
            raise
        if value.get("type") != "file" or value.get("size", 0) > 512_000 or value.get("encoding") != "base64":
            raise ValueError("Invalid trusted receipt object")
        document = json.loads(base64.b64decode(value["content"]))
        if document.get("format") == "jobhound-contribution-error":
            if (document.get("version") != 1 or document.get("verdict") != "needs_repair"
                    or document.get("pr_number") != submission["pr_number"]
                    or document.get("head_commit") != submission["head_commit"]):
                raise ValueError("Error receipt identifies a different PR")
            result.update(validation_state="needs_repair", publication_state="blocked",
                          validation=document)
            return result
        proof = ValidationReceipt.model_validate(document)
        if proof.pr_number != submission["pr_number"] or proof.head_commit != submission["head_commit"]:
            raise ValueError("Receipt identifies a different PR")
        result.update(validation_state=proof.verdict, validation=proof.model_dump(mode="json"))
        if proof.verdict != "pass":
            result["publication_state"] = "blocked"
            return result
        effective_verification(monitor, proof.model_dump(mode="json"))
        result["runtime_verified"] = True
        if result["review_state"] != "merged":
            return result
        admitted(monitor, proof.model_dump(mode="json"), pull, proof.runtime_revision)
        result["publication_state"] = "awaiting_collection"
        # Fixed anonymous public feed, bounded manifest only; no personal data.
        with httpx.Client(timeout=12, follow_redirects=False, **external_client_kwargs(transport=self.transport)) as client:
            with client.stream("GET", "https://crudmaster92.github.io/job-hound-jobs/api/v1/manifest.json") as response:
                response.raise_for_status()
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_GITHUB_BYTES:
                        raise RepositoryUnavailable("Public manifest exceeds inspection budget")
        manifest = json.loads(body)
        source = next((item for item in manifest.get("sources", []) if item["id"] == monitor["id"]), None)
        if source and source.get("artifact_hash") == proof.artifact_hash and source.get("status") in {"complete", "partial"}:
            result.update(publication_state="published", generation=manifest["generation"], source=source)
        return result
