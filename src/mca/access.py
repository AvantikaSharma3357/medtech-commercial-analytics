"""Role-based access control and row-level security (RLS)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import duckdb
import yaml

ACCESS_FILE = Path(__file__).resolve().parents[2] / "semantic" / "access.yml"


@dataclass(frozen=True)
class User:
    id: str
    name: str
    region: str
    role: str


@dataclass(frozen=True)
class RowFilter:
    dimension: str
    value: str


class AccessPolicy:
    """Maps a user's role to the row filter applied to every query."""

    def __init__(self, path: Path = ACCESS_FILE):
        self.roles = yaml.safe_load(path.read_text())["roles"]

    def required_dimensions(self) -> set[str]:
        return {r["row_filter"]["dimension"] for r in self.roles.values() if r["row_filter"]}

    def row_filter(self, user: User) -> RowFilter | None:
        if user.role not in self.roles:
            raise PermissionError(f"Unknown role '{user.role}' for user {user.id}")
        rule = self.roles[user.role]["row_filter"]
        if rule is None:
            return None
        value = {"Id": user.id, "Region": user.region}[rule["user_field"]]
        return RowFilter(rule["dimension"], value)


def load_users(con: duckdb.DuckDBPyConnection) -> dict[str, User]:
    rows = con.execute("SELECT Id, Name, Region, Role FROM users ORDER BY Id").fetchall()
    return {r[0]: User(*r) for r in rows}
