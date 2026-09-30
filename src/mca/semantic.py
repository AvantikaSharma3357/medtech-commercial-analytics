"""A small semantic layer: compiles metric requests into SQL from metrics.yml.

Callers ask for measures and dimensions by name. Only names defined in the
model are allowed, filter values are always bound as parameters, and the
viewing user's row-level security filter is applied to every query.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import duckdb
import pandas as pd
import yaml

from mca.access import AccessPolicy, User

METRICS_FILE = Path(__file__).resolve().parents[2] / "semantic" / "metrics.yml"
AGGREGATIONS = {"sum": "SUM({})", "count": "COUNT({})", "count_distinct": "COUNT(DISTINCT {})"}


class SemanticError(ValueError):
    """Raised when a request references something the model does not define."""


@dataclass(frozen=True)
class TimeRange:
    dimension: str
    start: str  # inclusive, ISO date
    end: str    # inclusive, ISO date


class Cube:
    def __init__(self, name: str, spec: dict):
        self.name = name
        self.description = spec.get("description", "")
        self.table = spec["sql_table"]
        self.joins: dict[str, str] = spec.get("joins", {})
        self.measures: dict[str, dict] = spec["measures"]
        self.dimensions: dict[str, dict] = spec["dimensions"]

    def dimension_sql(self, name: str) -> str:
        if name not in self.dimensions:
            raise SemanticError(f"Cube '{self.name}' has no dimension '{name}'")
        return self.dimensions[name]["sql"]

    def measure_sql(self, name: str) -> str:
        if name not in self.measures:
            raise SemanticError(f"Cube '{self.name}' has no measure '{name}'")
        m = self.measures[name]
        if m["type"] == "ratio":
            num, den = self.measure_sql(m["numerator"]), self.measure_sql(m["denominator"])
            return f"CAST({num} AS DOUBLE) / NULLIF({den}, 0)"
        if m["type"] not in AGGREGATIONS:
            raise SemanticError(f"Unsupported measure type '{m['type']}' on {self.name}.{name}")
        expr = AGGREGATIONS[m["type"]].format(m["sql"])
        if m.get("filter"):
            expr += f" FILTER (WHERE {m['filter']})"
        return expr

    def from_clause(self) -> str:
        sql = self.table
        for table, condition in self.joins.items():
            sql += f" LEFT JOIN {table} ON {condition}"
        return sql


class SemanticModel:
    def __init__(self, con: duckdb.DuckDBPyConnection, path: Path = METRICS_FILE,
                 policy: AccessPolicy | None = None):
        self.con = con
        self.policy = policy or AccessPolicy()
        spec = yaml.safe_load(path.read_text())
        self.cubes = {name: Cube(name, c) for name, c in spec["cubes"].items()}
        self._validate()

    def _validate(self) -> None:
        """Every cube must expose the dimensions RLS depends on."""
        needed = self.policy.required_dimensions()
        for cube in self.cubes.values():
            missing = needed - cube.dimensions.keys()
            if missing:
                raise SemanticError(f"Cube '{cube.name}' is missing RLS dimensions {missing}")

    def cube(self, name: str) -> Cube:
        if name not in self.cubes:
            raise SemanticError(f"Unknown cube '{name}'")
        return self.cubes[name]

    def compile(self, cube: str, measures: list[str], user: User,
                dimensions: list[str] | None = None,
                filters: dict[str, str | list[str]] | None = None,
                time_range: TimeRange | None = None) -> tuple[str, list]:
        """Return (sql, params) for a metric request."""
        c = self.cube(cube)
        dimensions = dimensions or []
        if not measures:
            raise SemanticError("Request at least one measure")

        select = [f"{c.dimension_sql(d)} AS {d}" for d in dimensions]
        select += [f"{c.measure_sql(m)} AS {m}" for m in measures]

        where, params = [], []
        for dim, value in (filters or {}).items():
            values = value if isinstance(value, list) else [value]
            if not values:
                continue
            where.append(f"{c.dimension_sql(dim)} IN ({', '.join('?' * len(values))})")
            params += values
        if time_range:
            where.append(f"{c.dimension_sql(time_range.dimension)} BETWEEN ? AND ?")
            params += [time_range.start, time_range.end]

        rls = self.policy.row_filter(user)  # applied last; callers cannot remove it
        if rls:
            where.append(f"{c.dimension_sql(rls.dimension)} = ?")
            params.append(rls.value)

        sql = f"SELECT {', '.join(select)} FROM {c.from_clause()}"
        if where:
            sql += " WHERE " + " AND ".join(where)
        if dimensions:
            sql += " GROUP BY ALL ORDER BY ALL"
        return sql, params

    def query(self, cube: str, measures: list[str], user: User, **kwargs) -> pd.DataFrame:
        sql, params = self.compile(cube, measures, user, **kwargs)
        return self.con.execute(sql, params).df()

    def catalog(self) -> pd.DataFrame:
        """Metric definitions for display, straight from the model."""
        rows = [{"cube": c.name, "measure": m, "type": spec["type"],
                 "description": spec.get("description", "")}
                for c in self.cubes.values() for m, spec in c.measures.items()]
        return pd.DataFrame(rows)
