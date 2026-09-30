"""Data quality checks on the raw CRM extracts.

Each check is a SQL query returning the offending rows. Severity 'error'
fails CI; severity 'warning' is reported but does not block.
Run:  python -m mca.quality
"""
from __future__ import annotations

import sys
from dataclasses import dataclass

import duckdb


@dataclass(frozen=True)
class Check:
    name: str
    severity: str  # "error" | "warning"
    description: str
    sql: str


@dataclass(frozen=True)
class CheckResult:
    check: Check
    failed_rows: int

    @property
    def passed(self) -> bool:
        return self.failed_rows == 0


CHECKS = [
    Check("accounts_unique_id", "error", "Account Ids are unique",
          "SELECT Id FROM accounts GROUP BY Id HAVING COUNT(*) > 1"),
    Check("opportunities_unique_id", "error", "Opportunity Ids are unique",
          "SELECT Id FROM opportunities GROUP BY Id HAVING COUNT(*) > 1"),
    Check("opportunity_orphans", "error", "Every opportunity links to an existing account",
          "SELECT o.Id FROM opportunities o LEFT JOIN accounts a ON o.AccountId = a.Id "
          "WHERE a.Id IS NULL"),
    Check("account_owner_valid", "error", "Every account owner is a known user",
          "SELECT a.Id FROM accounts a LEFT JOIN users u ON a.OwnerId = u.Id WHERE u.Id IS NULL"),
    Check("won_amount_positive", "error", "Closed Won opportunities have a positive amount",
          "SELECT Id FROM opportunities WHERE IsWon AND (Amount IS NULL OR Amount <= 0)"),
    Check("close_after_create", "error", "CloseDate is on or after CreatedDate",
          "SELECT Id FROM opportunities WHERE CloseDate < CreatedDate"),
    Check("stage_matches_flags", "error", "StageName agrees with IsClosed / IsWon",
          "SELECT Id FROM opportunities WHERE "
          "(StageName = 'Closed Won') <> IsWon OR "
          "(StageName IN ('Closed Won', 'Closed Lost')) <> IsClosed"),
    Check("orders_non_negative", "error", "Analysis volumes are not negative",
          "SELECT AccountId FROM orders WHERE AnalysesOrdered < 0"),
    Check("account_billing_state", "warning", "Accounts have a BillingState",
          "SELECT Id FROM accounts WHERE BillingState IS NULL"),
]


def run_checks(con: duckdb.DuckDBPyConnection) -> list[CheckResult]:
    return [CheckResult(c, len(con.execute(c.sql).fetchall())) for c in CHECKS]


def main() -> int:
    from mca.warehouse import connect

    results = run_checks(connect())
    for r in results:
        status = "PASS" if r.passed else r.check.severity.upper()
        print(f"[{status:7}] {r.check.name}: {r.check.description} ({r.failed_rows} rows)")
    errors = [r for r in results if not r.passed and r.check.severity == "error"]
    print(f"\n{len(errors)} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
