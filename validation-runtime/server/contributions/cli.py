"""Trusted recipe-PR validator. Reads git objects; never checks out candidate code."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

from .contracts import Proposal, canonical_bytes, validate_documents, content_hash
from .validation import validate_live

ALLOWED_PATH = re.compile(r"^(?:companies/[a-z0-9-]+/(?:company\.json|monitors/[a-z0-9-]+\.json)|collections/[a-z0-9-]+\.json|contributions/[a-z0-9-]+/proposal\.json)$")


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True, encoding="utf-8").strip()


def read_blob(root: Path, ref: str, path: str) -> dict:
    if not re.fullmatch(r"[a-f0-9]{40}", ref) or not ALLOWED_PATH.fullmatch(path):
        raise ValueError("Invalid candidate object reference")
    entry = git(root, "ls-tree", ref, "--", path).split()
    if len(entry) < 4 or entry[0] != "100644" or entry[1] != "blob":
        raise ValueError("Candidate must be a normal JSON blob, never a link or submodule")
    if int(git(root, "cat-file", "-s", entry[2])) > 512_000:
        raise ValueError("Candidate JSON exceeds its byte budget")
    value = json.loads(git(root, "cat-file", "blob", entry[2]))
    if not isinstance(value, dict):
        raise ValueError("Candidate must be a JSON object")
    return value


def source_documents(root: Path, ref: str):
    """Bounded batch object reads avoid one subprocess per catalog document."""
    entries = []
    total = 0
    for line in git(root, "ls-tree", "-r", "-l", ref).splitlines():
        mode, kind, sha, size, path = line.split(None, 4)
        if not re.fullmatch(r"companies/[a-z0-9-]+/(?:company\.json|monitors/[a-z0-9-]+\.json)", path):
            continue
        if mode != "100644" or kind != "blob" or int(size) > 512_000:
            raise ValueError("Catalog identity documents must be bounded normal JSON blobs")
        total += int(size)
        entries.append((path, sha, int(size)))
    if len(entries) > 10_000 or total > 50_000_000:
        raise ValueError("Catalog identity index exceeds validation budget")
    if not entries:
        return []
    output = subprocess.check_output(["git", "-C", str(root), "cat-file", "--batch"],
                                     input=("\n".join(sha for _, sha, _ in entries) + "\n").encode())
    offset, documents = 0, []
    for path, sha, size in entries:
        end = output.index(b"\n", offset)
        if output[offset:end].decode() != f"{sha} blob {size}":
            raise ValueError("Git object identity changed")
        value = json.loads(output[end + 1:end + 1 + size])
        if not isinstance(value, dict):
            raise ValueError("Identity source must be a JSON object")
        documents.append((path, value))
        offset = end + 2 + size
    return documents


def validate_change(root: Path, *, base: str, head: str, pr_number: int,
                    runtime_revision: str, live=True) -> dict:
    if not all(re.fullmatch(r"[a-f0-9]{40}", value) for value in (base, head)):
        raise ValueError("Base and head must be exact commit SHAs")
    ancestor = git(root, "merge-base", base, head)
    if ancestor != base:
        raise ValueError("PR is behind current main; refresh its base and rerun validation")
    changes = git(root, "diff", "--name-status", base, head).splitlines()
    changed = []
    for line in changes:
        status, path = line.split("\t", 1)
        if status not in {"A", "M"} or not ALLOWED_PATH.fullmatch(path):
            raise ValueError("Recipe PRs may only add/update normalized public JSON sources and their proposal evidence")
        changed.append(path)
    proposal_paths = [path for path in changed if path.startswith("contributions/")]
    if len(proposal_paths) != 1:
        raise ValueError("One company/monitor proposal is required per PR")
    proposal = Proposal.model_validate(read_blob(root, head, proposal_paths[0]))
    if proposal.base_commit != base:
        raise ValueError("Proposal records a different reviewed base")
    normalized = validate_documents(proposal)
    if set(changed) - set(normalized["files"]):
        raise ValueError("PR mixes unrelated sources into the proposal")
    for path, expected in normalized["files"].items():
        if read_blob(root, head, path) != expected:
            raise ValueError("Authored source differs from the normalized proposal; author verification must stay unverified")
    company_id, monitor_id = proposal.company["id"], proposal.monitor["id"]
    # Review all source identities using data only. A recipe's company label
    # cannot manufacture a new identity for an existing employer.
    candidate_names = {proposal.company["name"].casefold(), *[name.casefold() for name in proposal.company.get("aliases", [])]}
    careers = {}
    for path, document in source_documents(root, head):
        if re.fullmatch(r"companies/[a-z0-9-]+/company\.json", path):
            company = document
            if company["id"] != path.split("/")[1]:
                raise ValueError("Company identity does not own its source directory")
            names = {company["name"].casefold(), *[item.casefold() for item in company.get("aliases", [])]}
            if company["id"] != company_id and names & candidate_names:
                raise ValueError("Company name or alias duplicates an existing identity")
        elif re.fullmatch(r"companies/[a-z0-9-]+/monitors/[a-z0-9-]+\.json", path):
            if document["id"] != Path(path).stem or document["company_id"] != path.split("/")[1]:
                raise ValueError("Monitor identity does not own its source path")
            if document["id"] == monitor_id and document["company_id"] != company_id:
                raise ValueError("Monitor ID belongs to another company")
            url = document["careers_url"].rstrip("/")
            previous = careers.get(url)
            if previous and previous["company_id"] != document["company_id"] and not (previous["recipe"].get("source_filter") and document["recipe"].get("source_filter")):
                if document["id"] == monitor_id or previous["id"] == monitor_id:
                    raise ValueError("Shared careers feed duplicates another employer without explicit ownership boundaries")
            careers[url] = document
    monitor_path = f"companies/{company_id}/monitors/{monitor_id}.json"
    if git(root, "ls-tree", base, "--", monitor_path):
        before = read_blob(root, base, monitor_path)
        if proposal.monitor["revision"] <= before["revision"]:
            raise ValueError("Changed monitor revision was not incremented")
    elif proposal.monitor["revision"] != 1:
        raise ValueError("New monitor must start at revision 1")
    company_path = f"companies/{company_id}/company.json"
    if git(root, "ls-tree", base, "--", company_path) and read_blob(root, base, company_path) != proposal.company:
        raise ValueError("Existing identity must be reused unchanged")
    for collection in proposal.collections:
        path = f"collections/{collection['id']}.json"
        if git(root, "ls-tree", base, "--", path):
            before = read_blob(root, base, path)
            if collection["revision"] != before["revision"] + 1:
                raise ValueError("Collection revision must increment once")
            unchanged = {**before, "revision": collection["revision"], "companies": collection["companies"]}
            if unchanged != collection or [item for item in before["companies"] if item["company_id"] != company_id] != [item for item in collection["companies"] if item["company_id"] != company_id]:
                raise ValueError("Proposal edits unrelated collection data")
    if not live:
        from .validation import parse_fixture
        return {"verdict": "blocked", "runtime_verified": False, "offline_parsing": parse_fixture(proposal),
                "errors": ["Offline-only validation never passes the live contribution gate."]}
    return validate_live(proposal, pr_number=pr_number, head_commit=head,
                         runtime_revision=runtime_revision).model_dump(mode="json")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--pr", type=int, required=True)
    parser.add_argument("--runtime-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    try:
        manifest = json.loads(args.runtime_manifest.read_text())
        report = validate_change(args.repo, base=args.base, head=args.head, pr_number=args.pr,
                                 runtime_revision=manifest["runtime_revision"], live=not args.offline)
    except Exception as exc:
        report = {"format": "jobhound-contribution-error", "version": 1, "verdict": "needs_repair",
                  "pr_number": args.pr, "head_commit": args.head,
                  "errors": [str(exc)[:1000]]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical_bytes(report))
    print(json.dumps({"verdict": report["verdict"], "errors": report.get("errors", [])}))
    return 0 if report["verdict"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
