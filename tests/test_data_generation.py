from generate_data import build


def test_generation_is_deterministic():
    a, b = build(seed=7), build(seed=7)
    for name in a:
        assert a[name].equals(b[name])


def test_every_rep_owns_accounts_in_their_region():
    data = build()
    merged = data["accounts"].merge(data["users"], left_on="OwnerId", right_on="Id",
                                    suffixes=("", "_owner"))
    assert (merged.Region == merged.Region_owner).all()
