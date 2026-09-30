import pytest

from mca.access import User


def owned_accounts(con, user_id):
    return {r[0] for r in con.execute("SELECT Name FROM accounts WHERE OwnerId = ?",
                                      [user_id]).fetchall()}


def test_rep_sees_only_own_accounts(model, users, con):
    rep = next(u for u in users.values() if u.role == "rep")
    df = model.query("opportunities", ["opportunity_count"], rep, dimensions=["account_name"])
    assert set(df.account_name) <= owned_accounts(con, rep.id)


def test_manager_sees_only_own_region(model, users):
    mgr = next(u for u in users.values() if u.role == "regional_manager")
    df = model.query("opportunities", ["opportunity_count"], mgr, dimensions=["region"])
    assert list(df.region) == [mgr.region]


def test_managers_add_up_to_admin_total(model, users, admin):
    total = model.query("opportunities", ["closed_won_amount"], admin).iloc[0, 0]
    managers = [u for u in users.values() if u.role == "regional_manager"]
    parts = sum(model.query("opportunities", ["closed_won_amount"], m).iloc[0, 0] for m in managers)
    assert parts == pytest.approx(total)


def test_filters_cannot_bypass_rls(model, users):
    mgr = next(u for u in users.values() if u.role == "regional_manager")
    other = next(r for r in ("West", "Central", "East") if r != mgr.region)
    df = model.query("opportunities", ["opportunity_count"], mgr, filters={"region": other})
    assert df.iloc[0, 0] == 0


def test_unknown_role_denied(model):
    with pytest.raises(PermissionError):
        model.query("opportunities", ["opportunity_count"], User("X", "X", "West", "intern"))
