"""Privileged fixed-path receipt writer; never runs or imports candidate code."""
import base64
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.request

REPO = "CrudMaster92/job-hound-presets"
BRANCH = "review-receipts"


def api(path, method="GET", payload=None):
    request = urllib.request.Request(f"https://api.github.com/repos/{REPO}/{path}",
        method=method, data=None if payload is None else json.dumps(payload).encode(),
        headers={"Authorization": "Bearer " + os.environ["GITHUB_TOKEN"],
                 "Accept": "application/vnd.github+json", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise RuntimeError(f"Receipt publication failed (HTTP {exc.code})") from None


def main():
    number, head = os.environ["PR_NUMBER"], os.environ["HEAD_SHA"]
    if not re.fullmatch(r"[1-9][0-9]{0,8}", number) or not re.fullmatch(r"[a-f0-9]{40}", head):
        raise ValueError("Invalid receipt identity")
    body = Path("receipt.json").read_bytes()
    if len(body) > 512_000:
        raise ValueError("Oversized report")
    report = json.loads(body)
    if report.get("format") not in {"jobhound-scraper-validation", "jobhound-contribution-error"} or report.get("verdict") not in {"pass", "blocked", "needs_repair"}:
        raise ValueError("Invalid validator report")
    if report["verdict"] == "pass" and (report.get("head_commit") != head or str(report.get("pr_number")) != number):
        raise ValueError("Passing report is for another PR")
    pull = api(f"pulls/{number}")
    if pull["head"]["sha"] != head or pull["base"]["ref"] != "main":
        raise ValueError("PR changed; stale report will not be published")
    if api(f"git/ref/heads/{BRANCH}") is None:
        main = api("git/ref/heads/main")["object"]["sha"]
        api("git/refs", "POST", {"ref": f"refs/heads/{BRANCH}", "sha": main})
    path = f"contents/receipts/{number}/{head}.json"
    existing = api(path + f"?ref={BRANCH}")
    payload = {"message": f"Trusted scraper report PR {number} {head}", "branch": BRANCH,
               "content": base64.b64encode(body).decode()}
    if existing:
        payload["sha"] = existing["sha"]
    api(path, "PUT", payload)
    print(f"Stored {report['verdict']} report for PR {number}. No main-branch change or merge.")


if __name__ == "__main__":
    main()
