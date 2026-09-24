"""Compatibility shim — prefer app.services.dashboard."""

from app.services.dashboard import get_dashboard_overview

__all__ = ["get_dashboard_overview"]
