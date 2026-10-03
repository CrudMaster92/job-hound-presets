"""Trusted receipt admission shared by catalog publication and collection.

Receipts MUST come from the canonical repository's review-receipts branch.
Candidate trees are never a receipt source. The maintainer's actual merge is the authority.
"""
from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path

from .contracts import REPOSITORY, canonical_bytes, content_hash
from .github import PublicRepository
from .validation import ValidationReceipt, effective_verification


def admitted(monitor, receipt, pull, runtime_revision):
    proof = ValidationReceipt.model_validate(receipt)
    if (pull.get("number") != proof.pr_number or not pull.get("merged")
            or pull.get("merged_by", {}).get("login") != "CrudMaster92"
            or pull.get("base", {}).get("ref") != "main"
            or pull.get("base", {}).get("repo", {}).get("full_name") != REPOSITORY
            or pull.get("head", {}).get("sha") != proof.head_commit):
        raise ValueError("Exact validated PR must be merged into canonical main by the maintainer")
    return effective_verification(monitor, receipt, runtime_revision=runtime_revision)


def approved_receipts(root: Path, receipts: Path, runtime_revision: str, repository=None):
    """Fail closed per source. Offline/API failures never activate a new pin."""
    repository = repository or PublicRepository()
    monitors = {content_hash(json.loads(path.read_text(encoding="utf-8"))): path
                for path in (root / "companies").glob("*/monitors/*.json")}
    accepted, excluded, pulls = {}, {}, {}
    paths = sorted(receipts.glob("receipts/*/*.json"))
    if len(paths) > 5000:
        raise ValueError("Receipt index exceeds inspection budget")
    for path in paths:
        if path.is_symlink() or path.stat().st_size > 512_000:
            raise ValueError("Receipt must be a bounded normal JSON file")
        receipt = json.loads(path.read_text(encoding="utf-8"))
        if receipt.get("artifact_hash") not in monitors:
            continue
        monitor_path = monitors[receipt["artifact_hash"]]
        monitor = json.loads(monitor_path.read_text(encoding="utf-8"))
        try:
            proof = ValidationReceipt.model_validate(receipt)
            if path.relative_to(receipts).as_posix() != f"receipts/{proof.pr_number}/{proof.head_commit}.json":
                raise ValueError("Receipt path identity mismatch")
            if proof.pr_number not in pulls:
                pulls[proof.pr_number] = repository.read(f"pulls/{proof.pr_number}")
            verification = admitted(monitor, receipt, pulls[proof.pr_number], runtime_revision)
            accepted[monitor["id"]] = {"verification": verification, "receipt": receipt}
        except (ValueError, RuntimeError) as exc:
            excluded[monitor["id"]] = f"Trusted admission unavailable ({type(exc).__name__}); existing pins retained."
    return accepted, excluded


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--receipts", required=True, type=Path)
    parser.add_argument("--runtime-manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    runtime = json.loads(args.runtime_manifest.read_text())["runtime_revision"]
    accepted, excluded = approved_receipts(args.catalog, args.receipts, runtime)
    args.output.write_bytes(canonical_bytes({"accepted": accepted, "excluded": excluded}))
    print(json.dumps({"admitted": len(accepted), "pending": len(excluded)}))


if __name__ == "__main__":
    main()
