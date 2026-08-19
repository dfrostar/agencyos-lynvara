"""tests/test_lynvara_signals.py — Tests for Lynvara signal detectors."""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta, timezone

from agent_os.lynvara_signals import (
    ContractRenewalSignal,
    InvoiceReconciliationSignal,
    OnboardingStallSignal,
    VendorSLASignal,
)


@pytest.fixture
def contract_renewal() -> ContractRenewalSignal:
    return ContractRenewalSignal(warning_days=30, critical_days=7)


@pytest.fixture
def vendor_sla() -> VendorSLASignal:
    return VendorSLASignal(uptime_threshold=99.0)


@pytest.fixture
def invoice_recon() -> InvoiceReconciliationSignal:
    return InvoiceReconciliationSignal(tolerance_pct=5.0)


@pytest.fixture
def onboarding_stall() -> OnboardingStallSignal:
    return OnboardingStallSignal(stall_days=14)


class TestContractRenewalSignal:
    def test_no_expiration_no_signal(self, contract_renewal: ContractRenewalSignal) -> None:
        contracts = [{"id": "1", "title": "Test"}]
        signals = contract_renewal.check(contracts)
        assert len(signals) == 0

    def test_critical_expiration(self, contract_renewal: ContractRenewalSignal) -> None:
        expires = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
        contracts = [{"id": "1", "title": "Cerbo MSA", "expires_at": expires, "vendor_name": "Cerbo"}]
        signals = contract_renewal.check(contracts)
        assert len(signals) == 1
        assert signals[0]["severity"] == "critical"

    def test_warning_expiration(self, contract_renewal: ContractRenewalSignal) -> None:
        expires = (datetime.now(timezone.utc) + timedelta(days=20)).isoformat()
        contracts = [{"id": "1", "title": "Cerbo MSA", "expires_at": expires, "vendor_name": "Cerbo"}]
        signals = contract_renewal.check(contracts)
        assert len(signals) == 1
        assert signals[0]["severity"] == "warning"

    def test_far_expiration_no_signal(self, contract_renewal: ContractRenewalSignal) -> None:
        expires = (datetime.now(timezone.utc) + timedelta(days=365)).isoformat()
        contracts = [{"id": "1", "title": "Cerbo MSA", "expires_at": expires, "vendor_name": "Cerbo"}]
        signals = contract_renewal.check(contracts)
        assert len(signals) == 0


class TestVendorSLASignal:
    def test_infrastructure_down(self, vendor_sla: VendorSLASignal) -> None:
        infra = [{"id": "1", "service_name": "API", "provider": "Render", "status": "down"}]
        signals = vendor_sla.check(infra)
        assert len(signals) == 1
        assert signals[0]["severity"] == "critical"

    def test_infrastructure_healthy_no_signal(self, vendor_sla: VendorSLASignal) -> None:
        infra = [{"id": "1", "service_name": "API", "provider": "Render", "status": "live"}]
        signals = vendor_sla.check(infra)
        assert len(signals) == 0


class TestInvoiceReconciliationSignal:
    def test_discrepancy_detected(self, invoice_recon: InvoiceReconciliationSignal) -> None:
        invoices = [{"id": "1", "expected_amount": 1000, "paid_amount": 900}]
        signals = invoice_recon.check(invoices)
        assert len(signals) == 1
        assert signals[0]["discrepancy_pct"] == 10.0

    def test_within_tolerance(self, invoice_recon: InvoiceReconciliationSignal) -> None:
        invoices = [{"id": "1", "expected_amount": 1000, "paid_amount": 980}]
        signals = invoice_recon.check(invoices)
        assert len(signals) == 0


class TestOnboardingStallSignal:
    def test_stalled_onboarding(self, onboarding_stall: OnboardingStallSignal) -> None:
        updated = (datetime.now(timezone.utc) - timedelta(days=20)).isoformat()
        vendors = [{"id": "1", "name": "Cerbo", "status": "onboarding", "updated_at": updated}]
        signals = onboarding_stall.check(vendors)
        assert len(signals) == 1
        assert signals[0]["days_stalled"] == 20

    def test_active_vendor_no_signal(self, onboarding_stall: OnboardingStallSignal) -> None:
        updated = (datetime.now(timezone.utc) - timedelta(days=20)).isoformat()
        vendors = [{"id": "1", "name": "Cerbo", "status": "active", "updated_at": updated}]
        signals = onboarding_stall.check(vendors)
        assert len(signals) == 0
