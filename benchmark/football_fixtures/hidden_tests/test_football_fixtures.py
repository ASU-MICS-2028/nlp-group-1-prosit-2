import uuid

MISSING = 987654321
DATE = "2026-11-14"


def ok(status):
    return 200 <= status < 300


def refused(status):
    return 400 <= status < 500


def new_team(api):
    status, team = api.call("add_team", json={"name": f"Asante Stars {uuid.uuid4().hex[:6]}"})
    assert ok(status), team
    return team


def new_fixture(api, home, away, date=DATE):
    status, fixture = api.call("create_fixture", json={"home_team_id": home["id"], "away_team_id": away["id"], "date": date})
    assert ok(status), fixture
    return fixture


def get(api, fixture):
    status, got = api.call("get_fixture", path_params={"id": fixture["id"]})
    assert status == 200, got
    return got


def ids(fixtures):
    return {f["id"] for f in fixtures}


def test_add_team_returns_it_with_an_id(api):
    team = new_team(api)
    assert "id" in team
    assert team["name"].startswith("Asante Stars")


def test_added_team_appears_in_list(api):
    team = new_team(api)
    status, teams = api.call("list_teams")
    assert status == 200
    assert team["id"] in [t["id"] for t in teams]


def test_fixture_keeps_its_teams_and_date(api):
    home, away = new_team(api), new_team(api)
    got = get(api, new_fixture(api, home, away))
    assert str(got["home_team_id"]) == str(home["id"])
    assert str(got["away_team_id"]) == str(away["id"])
    assert got["date"] == DATE


def test_new_fixture_has_no_score_yet(api):
    got = get(api, new_fixture(api, new_team(api), new_team(api)))
    assert got.get("home_goals") is None
    assert got.get("away_goals") is None


def test_team_cannot_play_itself(api):
    team = new_team(api)
    status, _ = api.call("create_fixture", json={"home_team_id": team["id"], "away_team_id": team["id"], "date": DATE})
    assert refused(status)
    _, fixtures = api.call("team_fixtures", path_params={"id": team["id"]})
    assert fixtures == []


def test_fixture_with_unknown_team_is_refused(api):
    team = new_team(api)
    status, _ = api.call("create_fixture", json={"home_team_id": team["id"], "away_team_id": MISSING, "date": DATE})
    assert refused(status)


def test_recorded_score_is_kept_for_each_side(api):
    fixture = new_fixture(api, new_team(api), new_team(api))
    status, _ = api.call("record_score", path_params={"id": fixture["id"]}, json={"home_goals": 2, "away_goals": 1})
    assert ok(status)
    got = get(api, fixture)
    assert got["home_goals"] == 2
    assert got["away_goals"] == 1


def test_negative_score_is_refused(api):
    fixture = new_fixture(api, new_team(api), new_team(api))
    status, _ = api.call("record_score", path_params={"id": fixture["id"]}, json={"home_goals": -1, "away_goals": 0})
    assert refused(status)
    status, _ = api.call("record_score", path_params={"id": fixture["id"]}, json={"home_goals": 0, "away_goals": -3})
    assert refused(status)
    assert get(api, fixture).get("home_goals") is None


def test_record_score_for_missing_fixture_is_404(api):
    status, _ = api.call("record_score", path_params={"id": MISSING}, json={"home_goals": 1, "away_goals": 1})
    assert status == 404


def test_get_missing_fixture_is_404(api):
    status, _ = api.call("get_fixture", path_params={"id": MISSING})
    assert status == 404


def test_team_fixtures_include_home_and_away_only(api):
    team, a, b, c = new_team(api), new_team(api), new_team(api), new_team(api)
    at_home = new_fixture(api, team, a)
    away = new_fixture(api, b, team, "2026-11-21")
    other = new_fixture(api, a, c)
    status, fixtures = api.call("team_fixtures", path_params={"id": team["id"]})
    assert status == 200
    assert ids(fixtures) == {at_home["id"], away["id"]}
    assert other["id"] not in ids(fixtures)


def test_new_team_has_no_fixtures(api):
    team = new_team(api)
    status, fixtures = api.call("team_fixtures", path_params={"id": team["id"]})
    assert status == 200
    assert fixtures == []


def test_add_team_without_name_is_refused(api):
    status, _ = api.call("add_team", json={})
    assert refused(status)
