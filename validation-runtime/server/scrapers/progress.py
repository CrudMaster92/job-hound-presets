"""Optional context-local telemetry; worker threads inherit the current run context."""
from contextvars import ContextVar
progress_callback = ContextVar("scraper_progress", default=None)

def report_progress(stage, message, **detail):
    callback = progress_callback.get()
    if callback:
        callback({"stage": stage, "message": message, **detail})
