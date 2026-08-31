from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_catalog import build, digest


class CatalogBuildTests(unittest.TestCase):
    def test_catalog_v3_keeps_recipes_only_in_monitors_and_bundles(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            catalog = build(output=output, source_commit="test-commit")
            self.assertEqual(catalog["catalog_version"], 3)
            self.assertNotIn("companies", catalog)
            self.assertTrue(catalog["search_pages"])
            for path in output.rglob("*.json"):
                value = json.loads(path.read_text(encoding="utf-8"))
                relative = path.relative_to(output / "api" / "v1") if output / "api" / "v1" in path.parents else path.name
                text = json.dumps(value)
                if str(relative).startswith("monitors") or str(relative).startswith("bundles"):
                    continue
                self.assertNotIn('"recipe"', text, str(relative))

    def test_every_reference_hash_matches_its_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            catalog = build(output=output, source_commit="test-commit")
            api = output / "api" / "v1"
            references = list(catalog["search_pages"]) + list(catalog["collections"])
            for item in references:
                value = json.loads((api / item["path"]).read_text(encoding="utf-8"))
                self.assertEqual(item["sha256"], digest(value))
            for collection in catalog["collections"]:
                detail = json.loads((api / collection["path"]).read_text(encoding="utf-8"))
                for page in detail["member_pages"]:
                    value = json.loads((api / page["path"]).read_text(encoding="utf-8"))
                    self.assertEqual(page["sha256"], digest(value))

    def test_page_limits_and_multi_monitor_membership(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            catalog = build(output=output, source_commit="test-commit")
            api = output / "api" / "v1"
            self.assertTrue(all(page["count"] <= 250 for page in catalog["search_pages"]))
            fortune = next(value for value in catalog["collections"] if value["id"] == "fortune-10-2026")
            detail = json.loads((api / fortune["path"]).read_text(encoding="utf-8"))
            self.assertTrue(all(page["count"] <= 100 for page in detail["member_pages"]))
            members = json.loads((api / detail["member_pages"][0]["path"]).read_text(encoding="utf-8"))
            berkshire = next(value for value in members["companies"] if value["company_id"] == "berkshire-hathaway")
            self.assertEqual(len(berkshire["monitors"]), 2)


if __name__ == "__main__":
    unittest.main()
