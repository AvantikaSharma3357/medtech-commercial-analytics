import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "data"))

from mca.access import User, load_users  # noqa: E402
from mca.semantic import SemanticModel  # noqa: E402
from mca.warehouse import connect  # noqa: E402


@pytest.fixture()
def con():
    return connect()


@pytest.fixture()
def model(con):
    return SemanticModel(con)


@pytest.fixture()
def users(con):
    return load_users(con)


@pytest.fixture()
def admin(users) -> User:
    return next(u for u in users.values() if u.role == "admin")
