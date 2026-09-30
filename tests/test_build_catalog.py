from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import build_catalog

from scripts.build_catalog import build, digest, validate_company_hierarchy


class CatalogBuildTests(unittest.TestCase):
    def test_marketing_and_fortune_share_real_company_identity_without_mosaic_collision(self):
        root = Path(__file__).resolve().parents[1]
        fortune = json.loads((root / "collections/fortune-50-2026.json").read_text(encoding="utf-8"))
        marketing = json.loads((root / "collections/marketing-agencies-canada.json").read_text(encoding="utf-8"))
        fortune_ids = {member["company_id"] for member in fortune["companies"]}
        marketing_ids = {member["company_id"] for member in marketing["companies"]}
        self.assertEqual(fortune_ids & marketing_ids, {"omnicom"})
        self.assertIn("mosaic", fortune_ids)
        self.assertIn("mosaic-canada", marketing_ids)
        self.assertEqual(len(marketing["companies"]), 52)
        self.assertEqual(sum(bool(member.get("monitor_ids")) for member in marketing["companies"]), 51)
        self.assertEqual(
            json.loads((root / "companies/omnicom/company.json").read_text(encoding="utf-8"))["id"],
            "omnicom",
        )

    def test_recruitment_collection_preserves_blocked_companies_without_installable_placeholders(self):
        with tempfile.TemporaryDirectory() as directory:
            catalog = build(output=Path(directory), source_commit="test-commit")
            collection = next(item for item in catalog["collections"] if item["id"] == "recruitment-agencies-north-america")
            self.assertEqual(collection["company_count"], 34)
            self.assertEqual(collection["monitor_count"], 27)
            api = Path(directory) / "api" / "v1"
            members = json.loads((api / "collections/recruitment-agencies-north-america/members-0001.json").read_text())["companies"]
            unavailable = {"insight-global", "aston-carter", "mlag", "korn-ferry", "pagegroup", "robert-walters", "manpowergroup"}
            for member in members:
                if member["company_id"] in unavailable:
                    self.assertEqual(member["monitors"], [])
                    self.assertEqual(member["availability"]["status"], "unavailable")
                    self.assertTrue(member["availability"]["message"])
                else:
                    self.assertTrue(member["monitors"])
                    for monitor in member["monitors"]:
                        self.assertEqual(monitor["verification"]["status"], "verified")
                        self.assertGreater(monitor["verification"]["job_count"], 0)

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
            fortune = next(value for value in catalog["collections"] if value["id"] == "fortune-50-2026")
            self.assertEqual(fortune["company_count"], 500)
            self.assertEqual(fortune["monitor_count"], 438)
            detail = json.loads((api / fortune["path"]).read_text(encoding="utf-8"))
            self.assertTrue(all(page["count"] <= 100 for page in detail["member_pages"]))
            self.assertEqual([page["count"] for page in detail["member_pages"]], [100, 100, 100, 100, 100])
            members = {"companies": [
                member for page in detail["member_pages"]
                for member in json.loads((api / page["path"]).read_text(encoding="utf-8"))["companies"]
            ]}
            self.assertTrue(all(member["logo_url"] for member in members["companies"]))
            self.assertEqual(len({member["company_id"] for member in members["companies"]}), 500)
            bundle = json.loads((api / fortune["bundle_path"]).read_text(encoding="utf-8"))
            self.assertEqual(len(bundle["companies"]), 438)
            self.assertEqual(len(members["companies"]), 500)
            self.assertEqual(members["companies"][0]["rank"], 1)
            self.assertEqual(members["companies"][-1]["rank"], 500)
            self.assertEqual([m["rank"] for m in members["companies"]], [160 if rank == 161 else 350 if rank == 351 else rank for rank in range(1, 501)])
            unavailable = [m for m in members["companies"] if not m["monitors"]]
            self.assertEqual({m["company_id"] for m in unavailable}, {
                "progressive", "hca-healthcare", "delta-air-lines", "publix",
                "american-airlines", "enterprise-products", "cbre", "lithia", "ross-stores",
                "cdw", "bjs-wholesale", "cognizant", "adp", "parker-hannifin", "american-family", "manpowergroup", "general-mills",
                "mgm-resorts", "universal-health-services", "pultegroup", "omnicom", "leidos",
                "targa-resources", "murphy-usa", "kinder-morgan", "consolidated-edison", "farmers-insurance",
                "caseys", "raymond-james", "principal-financial", "fluor", "gap", "builders-firstsource", "stanley-black-decker", "sempra", "wayfair",
                "equitable-holdings", "caesars-entertainment", "thrivent-financial", "westlake", "lululemon-athletica", "fm",
                "jefferies-financial-group", "intuitive-surgical", "ace-hardware", "seaboard", "icahn-enterprises", "thor-industries",
                "apa", "old-republic-international", "comfort-systems-usa", "ppl", "transdigm-group", "sprouts-farmers-market",
                "franklin-resources", "caci-international", "sirius-xm-holdings", "monster-beverage", "yum-brands", "post-holdings",
                "api-group", "roper-technologies", "coterra-energy", "somnigroup-international", "equinix",
            })
            for member in unavailable:
                self.assertEqual(member["availability"]["status"], "unavailable")
                self.assertTrue(member["availability"]["message"])
                self.assertTrue(member["logo_url"])
            berkshire = next(value for value in members["companies"] if value["company_id"] == "berkshire-hathaway")
            self.assertEqual(len(berkshire["monitors"]), 2)

    def test_empty_collection_member_requires_explicit_unavailable_status(self):
        validate = build_catalog.validate

        def without_availability(path, schema):
            value = validate(path, schema)
            if schema == "jobhound-company-v1.schema.json" and value["id"] == "progressive":
                value.pop("availability", None)
            return value

        with tempfile.TemporaryDirectory() as directory, patch.object(
            build_catalog, "validate", side_effect=without_availability
        ):
            with self.assertRaisesRegex(ValueError, "progressive.*has no installable monitor"):
                build(output=Path(directory), source_commit="test-commit")

    def test_search_records_are_compact_and_install_ready(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            catalog = build(output=output, source_commit="test-commit")
            api = output / "api" / "v1"
            pages = [json.loads((api / ref["path"]).read_text(encoding="utf-8"))
                     for ref in catalog["search_pages"]]
            companies = [company for page in pages for company in page["companies"]]
            amazon = next(value for value in companies if value["id"] == "amazon")
            self.assertEqual(amazon["monitor_count"], 2)
            self.assertEqual(amazon["adapters"], ["generic_json"])
            self.assertEqual(amazon["verification_statuses"], ["degraded", "verified"])
            self.assertEqual(amazon["website_url"], "https://www.amazon.com/")
            self.assertNotIn("monitors", amazon)
            self.assertNotIn("recipe", json.dumps(amazon))

    def test_parent_summary_is_emitted_and_hierarchy_is_validated(self):
        validate_company_hierarchy({"parent": {}, "child": {"parent_company_id": "parent"}})
        with self.assertRaisesRegex(ValueError, "unknown parent"):
            validate_company_hierarchy({"child": {"parent_company_id": "missing"}})
        with self.assertRaisesRegex(ValueError, "cycle"):
            validate_company_hierarchy({
                "one": {"parent_company_id": "two"},
                "two": {"parent_company_id": "one"},
            })

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            catalog = build(output=output, source_commit="test-commit")
            api = output / "api" / "v1"
            pages = [json.loads((api / ref["path"]).read_text(encoding="utf-8"))
                     for ref in catalog["search_pages"]]
            self.assertTrue(all("parent" in company for page in pages for company in page["companies"]))

    def test_unavailable_company_is_searchable_without_a_broken_monitor(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            catalog = build(output=output, source_commit="test-commit")
            api = output / "api" / "v1"
            pages = [json.loads((api / ref["path"]).read_text(encoding="utf-8"))
                     for ref in catalog["search_pages"]]
            companies = [company for page in pages for company in page["companies"]]
            delta = next(value for value in companies if value["id"] == "delta-air-lines")
            self.assertEqual(delta["monitor_count"], 0)
            self.assertEqual(delta["adapters"], [])
            self.assertEqual(delta["availability"]["status"], "unavailable")
            self.assertEqual(delta["availability"]["reason"], "maintenance")

            detail = json.loads((api / delta["path"]).read_text(encoding="utf-8"))
            self.assertEqual(detail["monitors"], [])
            self.assertEqual(detail["availability"], delta["availability"])


if __name__ == "__main__":
    unittest.main()
