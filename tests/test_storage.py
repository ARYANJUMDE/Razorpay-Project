"""Tests for SQLite persistence storage layer."""

import tempfile
from datetime import datetime, timezone
from pathlib import Path

from ghost_payment_resolver.schemas import AuditRecord
from ghost_payment_resolver.states import Action, CaseState
from ghost_payment_resolver.storage import AuditDatabase


def test_audit_db_save_and_retrieve():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_audit.db"
        db = AuditDatabase(db_path)

        record = AuditRecord(
            audit_id="aud_test_123",
            case_id="case_test_001",
            timestamp=datetime.now(timezone.utc),
            observed_state=CaseState.GHOST_SUCCESS,
            proposed_action=Action.CONFIRM_ORDER,
            policy_allowed=True,
            action_taken=Action.CONFIRM_ORDER,
            reason="Webhook delayed; captured on rail",
            amount_recovered_paise=149900,
            inputs={"order_id": "order_123"},
            outcome={"recovered_paise": 149900},
        )

        db.save_audit(record)
        assert db.count_audits() == 1

        audits = db.get_audits(case_id="case_test_001")
        assert len(audits) == 1
        assert audits[0].audit_id == "aud_test_123"
        assert audits[0].amount_recovered_paise == 149900
        assert audits[0].action_taken == Action.CONFIRM_ORDER


def test_audit_db_export_csv():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_export.db"
        db = AuditDatabase(db_path)

        record = AuditRecord(
            audit_id="aud_export_001",
            case_id="case_exp_001",
            timestamp=datetime.now(timezone.utc),
            observed_state=CaseState.ALIGNED,
            proposed_action=Action.NO_OP,
            policy_allowed=True,
            action_taken=Action.NO_OP,
            reason="Aligned",
            amount_recovered_paise=0,
            inputs={},
            outcome={},
        )
        db.save_audit(record)

        csv_text = db.export_csv()
        assert "aud_export_001" in csv_text
        assert "case_exp_001" in csv_text
        assert "amount_recovered_inr" in csv_text


def test_audit_db_clear_all():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_clear.db"
        db = AuditDatabase(db_path)

        record = AuditRecord(
            audit_id="aud_c1",
            case_id="case_c1",
            timestamp=datetime.now(timezone.utc),
            observed_state=CaseState.HARD_FAIL,
            proposed_action=Action.MARK_LOST,
            policy_allowed=True,
            action_taken=Action.MARK_LOST,
            reason="Card declined",
            amount_recovered_paise=0,
            inputs={},
            outcome={},
        )
        db.save_audit(record)
        assert db.count_audits() == 1

        db.clear_all()
        assert db.count_audits() == 0
