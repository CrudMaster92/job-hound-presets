"""JobHound's bounded, deterministic scraper runtime."""

from .detection import build_recipe, build_recipe_from_url, detect_platform
from .facade import build_scraper, repair_scraper
from .models import (
    DetectionResult,
    JobRecord,
    PaginationConfig,
    RemoteMode,
    SalaryPeriod,
    RequestConfig,
    ScrapeResult,
    ScraperRecipe,
    ScraperStrategy,
    ValidationReport,
)
from .runtime import ScraperExecutionError, run_scraper, validate_recipe

__all__ = [
    "DetectionResult", "JobRecord", "PaginationConfig", "RemoteMode", "SalaryPeriod", "RequestConfig",
    "ScrapeResult", "ScraperExecutionError", "ScraperRecipe", "ScraperStrategy",
    "ValidationReport", "build_recipe", "build_recipe_from_url", "build_scraper",
    "detect_platform", "repair_scraper", "run_scraper", "validate_recipe",
]
