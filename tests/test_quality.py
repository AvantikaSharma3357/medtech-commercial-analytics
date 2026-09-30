from mca.quality import run_checks


def failed(con):
    return {r.check.name for r in run_checks(con) if not r.passed}


def test_clean_data_has_no_errors(con):
    errors = [r for r in run_checks(con) if not r.passed and r.check.severity == "error"]
    assert errors == []


def test_detects_orphan_opportunity(con):
    con.execute("UPDATE opportunities SET AccountId = 'A9999' WHERE Id = 'O00001'")
    assert "opportunity_orphans" in failed(con)


def test_detects_duplicate_account(con):
    con.execute("INSERT INTO accounts SELECT * FROM accounts LIMIT 1")
    assert "accounts_unique_id" in failed(con)


def test_detects_close_before_create(con):
    con.execute("UPDATE opportunities SET CloseDate = CreatedDate - INTERVAL 5 DAY "
                "WHERE Id = 'O00002'")
    assert "close_after_create" in failed(con)


def test_detects_stage_flag_mismatch(con):
    con.execute("UPDATE opportunities SET StageName = 'Prospecting' "
                "WHERE Id = (SELECT MIN(Id) FROM opportunities WHERE IsWon)")
    assert "stage_matches_flags" in failed(con)
