"""lynvara_signals.py — Lynvara-specific signal detectors for AgencyOS.

Monitors business operations and emits signals when anomalies are detected.
Extends the existing signals.py framework with telehealth-specific checks.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from .signals import SeverityLevel

log = logging.getLogger(__name__)


class ContractRenewalSignal:
    """Detects contracts approaching expiration or renewal dates."""

    def __init__(self, warning_days: int = 30, critical_days: int = 7) -> None:
        self.warning_days = warning_days
        self.critical_days = critical_days

    def check(self, contracts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Check contracts for upcoming expiration."""
        signals: list[dict[str, Any]] = []
        now = datetime.now(timezone.utc)

        for contract in contracts:
            expires = contract.get("expires_at") or contract.get("renewal_date")
            if not expires:
                continue

            if isinstance(expires, str):
                expires = datetime.fromisoformat(expires.replace("Z", "+00:00"))

            days_until = (expires - now).days

            if days_until <= self.critical_days:
                signals.append({
                    "type": "contract.expiration.critical",
                    "severity": "critical",
                    "contract_id": contract.get("id"),
                    "contract_title": contract.get("title"),
                    "vendor_name": contract.get("vendor_name"),
                    "days_until_expiry": days_until,
                    "action_required": "Renew immediately",
                })
            elif days_until <= self.warning_days:
                signals.append({
                    "type": "contract.expiration.warning",
                    "severity": "warning",
                    "contract_id": contract.get("id"),
                    "contract_title": contract.get("title"),
                    "vendor_name": contract.get("vendor_name"),
                    "days_until_expiry": days_until,
                    "action_required": "Initiate renewal discussion",
                })

        return signals


class VendorSLASignal:
    """Detects vendor SLA violations or health degradations."""

    def __init__(self, uptime_threshold: float = 99.0) -> None:
        self.uptime_threshold = uptime_threshold

    def check(self, infrastructure: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Check infrastructure for SLA violations."""
        signals: list[dict[str, Any]] = []

        for infra in infrastructure:
            status = infra.get("status", "unknown")
            if status == "down":
                signals.append({
                    "type": "infrastructure.down",
                    "severity": "critical",
                    "infra_id": infra.get("id"),
                    "infra_name": infra.get("service_name"),
                    "provider": infra.get("provider"),
                    "action_required": "Investigate outage immediately",
                })
            elif status == "degraded":
                signals.append({
                    "type": "infrastructure.degraded",
                    "severity": "warning",
                    "infra_id": infra.get("id"),
                    "infra_name": infra.get("service_name"),
                    "provider": infra.get("provider"),
                    "action_required": "Monitor and investigate",
                })

        return signals


class InvoiceReconciliationSignal:
    """Detects invoice reconciliation anomalies."""

    def __init__(self, tolerance_pct: float = 5.0) -> None:
        self.tolerance_pct = tolerance_pct

    def check(self, invoices: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Check for invoice discrepancies."""
        signals: list[dict[str, Any]] = []

        for invoice in invoices:
            expected = invoice.get("expected_amount")
            actual = invoice.get("paid_amount")
            if expected is None or actual is None:
                continue

            if expected == 0:
                continue

            discrepancy_pct = abs(actual - expected) / expected * 100
            if discrepancy_pct > self.tolerance_pct:
                signals.append({
                    "type": "invoice.discrepancy",
                    "severity": "warning",
                    "invoice_id": invoice.get("id"),
                    "expected_amount": expected,
                    "paid_amount": actual,
                    "discrepancy_pct": round(discrepancy_pct, 2),
                    "action_required": "Review invoice reconciliation",
                })

        return signals


class OnboardingStallSignal:
    """Detects stalled vendor onboarding processes."""

    def __init__(self, stall_days: int = 14) -> None:
        self.stall_days = stall_days

    def check(self, vendors: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Check for stalled onboarding."""
        signals: list[dict[str, Any]] = []
        now = datetime.now(timezone.utc)

        for vendor in vendors:
            status = vendor.get("status")
            if status != "onboarding":
                continue

            updated = vendor.get("updated_at")
            if isinstance(updated, str):
                updated = datetime.fromisoformat(updated.replace("Z", "+00:00"))

            days_stalled = (now - updated).days if updated else 0
            if days_stalled >= self.stall_days:
                signals.append({
                    "type": "onboarding.stalled",
                    "severity": "warning",
                    "vendor_id": vendor.get("id"),
                    "vendor_name": vendor.get("name"),
                    "days_stalled": days_stalled,
                    "action_required": "Check onboarding progress",
                })

        return signals
