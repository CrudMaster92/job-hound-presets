# Job Hound Presets

This repository is the public, machine-readable catalog for portable Job Hound company presets. Presets must remain compatible with the official `jobhound-preset` version 1 contract: each manifest contains one or more companies and a complete, deterministic scraper recipe. The catalog may be consumed by the Job Hound website and, in the future, by the Job Hound app.

Agents may edit only this repository when working on presets. Never edit the Job Hound application, the Job Claw application directory, or the Job Hound website from a preset task. Preserve strict JSON, update `catalog.json` when adding or removing a preset, run `python scripts/validate_presets.py`, and never include credentials, cookies, authorization headers, personal search criteria, schedules, or local user data.
