import pytest

from mca.semantic import SemanticError, TimeRange


def test_every_measure_compiles_and_runs(model, admin):
    for cube in model.cubes.values():
        for measure in cube.measures:
            df = model.query(cube.name, [measure], admin)
            assert len(df) == 1


def test_every_dimension_groups(model, admin):
    for cube in model.cubes.values():
        measure = next(iter(cube.measures))
        for dim in cube.dimensions:
            df = model.query(cube.name, [measure], admin, dimensions=[dim])
            assert dim in df.columns and len(df) > 0


def test_bookings_match_raw_data(model, admin, con):
    semantic = model.query("opportunities", ["closed_won_amount"], admin).iloc[0, 0]
    raw = con.execute("SELECT SUM(Amount) FROM opportunities WHERE IsWon").fetchone()[0]
    assert semantic == pytest.approx(raw)


def test_win_rate_is_a_proportion(model, admin):
    df = model.query("opportunities", ["win_rate"], admin, dimensions=["region"])
    assert df.win_rate.between(0, 1).all()


def test_ratio_is_composed_from_base_measures(model, admin):
    df = model.query("opportunities", ["avg_deal_size", "closed_won_amount", "closed_won_count"],
                     admin).iloc[0]
    assert df.avg_deal_size == pytest.approx(df.closed_won_amount / df.closed_won_count)


def test_time_range_filters_rows(model, admin):
    full = model.query("opportunities", ["closed_won_count"], admin).iloc[0, 0]
    year = model.query("opportunities", ["closed_won_count"], admin,
                       time_range=TimeRange("close_date", "2025-01-01", "2025-12-31")).iloc[0, 0]
    assert 0 < year < full


def test_unknown_measure_rejected(model, admin):
    with pytest.raises(SemanticError):
        model.query("opportunities", ["revenue_made_up"], admin)


def test_unknown_filter_dimension_rejected(model, admin):
    with pytest.raises(SemanticError):
        model.query("opportunities", ["opportunity_count"], admin, filters={"1=1; --": "x"})


def test_filter_values_are_parameterized(model, admin):
    sql, params = model.compile("opportunities", ["opportunity_count"], admin,
                                filters={"region": "West' OR '1'='1"})
    assert "OR '1'='1" not in sql
    assert model.query("opportunities", ["opportunity_count"], admin,
                       filters={"region": "West' OR '1'='1"}).iloc[0, 0] == 0
