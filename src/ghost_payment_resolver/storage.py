"""SQLite persistence layer for Ghost Payment Resolver audit logs."""

from __future__ import annotations

import csv
import io
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ghost_payment_resolver.schemas import AuditRecord
from ghost_payment_resolver.states import Action, CaseState

DEFAULT_DB_PATH = Path("data/audit.db")


class AuditDatabase:
    """Thread-safe SQLite storage for immutable resolution audit records."""

    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_logs (
                    audit_id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    observed_state TEXT NOT NULL,
                    proposed_action TEXT NOT NULL,
                    policy_allowed INTEGER NOT NULL,
                    action_taken TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    amount_recovered_paise INTEGER NOT NULL,
                    inputs_json TEXT NOT NULL,
                    outcome_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_audit_case_id ON audit_logs(case_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp)"
            )
            conn.commit()

    def save_audit(self, record: AuditRecord) -> None:
        """Persist an audit record to SQLite."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO audit_logs (
                    audit_id,
                    case_id,
                    timestamp,
                    observed_state,
                    proposed_action,
                    policy_allowed,
                    action_taken,
                    reason,
                    amount_recovered_paise,
                    inputs_json,
                    outcome_json,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.audit_id,
                    record.case_id,
                    record.timestamp.isoformat(),
                    record.observed_state.value,
                    record.proposed_action.value,
                    1 if record.policy_allowed else 0,
                    record.action_taken.value,
                    record.reason,
                    record.amount_recovered_paise,
                    json.dumps(record.inputs),
                    json.dumps(record.outcome),
                    now_iso,
                ),
            )
            conn.commit()

    def get_audits(
        self,
        case_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditRecord]:
        """Fetch audit records with optional case_id filtering and pagination."""
        query = "SELECT * FROM audit_logs"
        params: list[Any] = []

        if case_id:
            query += " WHERE case_id = ?"
            params.append(case_id)

        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()

        records: list[AuditRecord] = []
        for r in rows:
            record = AuditRecord(
                audit_id=r["audit_id"],
                case_id=r["case_id"],
                timestamp=datetime.fromisoformat(r["timestamp"]),
                observed_state=CaseState(r["observed_state"]),
                proposed_action=Action(r["proposed_action"]),
                policy_allowed=bool(r["policy_allowed"]),
                action_taken=Action(r["action_taken"]),
                reason=r["reason"],
                amount_recovered_paise=r["amount_recovered_paise"],
                inputs=json.loads(r["inputs_json"]),
                outcome=json.loads(r["outcome_json"]),
            )
            records.append(record)
        return records

    def count_audits(self, case_id: str | None = None) -> int:
        """Count total audit logs in the database."""
        query = "SELECT COUNT(*) FROM audit_logs"
        params: list[Any] = []
        if case_id:
            query += " WHERE case_id = ?"
            params.append(case_id)

        with self._get_connection() as conn:
            cursor = conn.execute(query, params)
            return int(cursor.fetchone()[0])

    def export_csv(self) -> str:
        """Export all audit records as a CSV string for merchant accounting reconciliation."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM audit_logs ORDER BY timestamp DESC"
            ).fetchall()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "audit_id",
                "case_id",
                "timestamp",
                "observed_state",
                "proposed_action",
                "policy_allowed",
                "action_taken",
                "reason",
                "amount_recovered_paise",
                "amount_recovered_inr",
                "inputs_json",
                "outcome_json",
            ]
        )

        for r in rows:
            writer.writerow(
                [
                    r["audit_id"],
                    r["case_id"],
                    r["timestamp"],
                    r["observed_state"],
                    r["proposed_action"],
                    r["policy_allowed"],
                    r["action_taken"],
                    r["reason"],
                    r["amount_recovered_paise"],
                    r["amount_recovered_paise"] / 100,
                    r["inputs_json"],
                    r["outcome_json"],
                ]
            )

        return output.getvalue()

    def clear_all(self) -> None:
        """Clear all audit logs from the database."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM audit_logs")
            conn.commit()
