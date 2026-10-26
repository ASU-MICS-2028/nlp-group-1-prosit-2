import uuid

MISSING = 987654321


def new_student(api):
    status, s = api.call("create_student", json={"name": f"Esi {uuid.uuid4().hex[:6]}"})
    assert status in (200, 201), s
    return s


def new_course(api, credits=3):
    status, c = api.call("create_course", json={"name": f"Course {uuid.uuid4().hex[:6]}", "credits": credits})
    assert status in (200, 201), c
    return c


def score(api, student, course, value):
    return api.call("record_score", path_params={"id": student["id"]}, json={"course_id": course["id"], "score": value})


def results(api, student):
    status, r = api.call("get_results", path_params={"id": student["id"]})
    assert status == 200, r
    return r


def by_course(r):
    return {str(c["course_id"]): c for c in r["courses"]}


def graded(api, scores):
    """One student, one 3-credit course per score; returns {score: result entry}."""
    s = new_student(api)
    ids = {}
    for v in scores:
        c = new_course(api)
        assert 200 <= score(api, s, c, v)[0] < 300
        ids[v] = str(c["id"])
    got = by_course(results(api, s))
    return {v: got[i] for v, i in ids.items()}


def test_create_student_and_course(api):
    s, c = new_student(api), new_course(api, credits=2)
    assert "id" in s and "id" in c
    assert c["credits"] == 2


def test_score_appears_in_results_with_grade(api):
    s, c = new_student(api), new_course(api)
    status, _ = score(api, s, c, 85)
    assert 200 <= status < 300
    entry = by_course(results(api, s))[str(c["id"])]
    assert entry["score"] == 85
    assert entry["grade"] == "A"
    assert abs(entry["grade_point"] - 4.0) < 1e-6


def test_grading_scale_bands(api):
    expected = {90: ("A", 4.0), 77: ("B+", 3.5), 72: ("B", 3.0), 67: ("C+", 2.5),
                62: ("C", 2.0), 57: ("D+", 1.5), 52: ("D", 1.0), 30: ("F", 0.0)}
    got = graded(api, list(expected))
    for v, (letter, points) in expected.items():
        assert got[v]["grade"] == letter, v
        assert abs(got[v]["grade_point"] - points) < 1e-6, v


def test_grading_scale_boundaries(api):
    expected = {100: "A", 80: "A", 79: "B+", 75: "B+", 70: "B", 50: "D", 49: "F", 0: "F"}
    got = graded(api, list(expected))
    for v, letter in expected.items():
        assert got[v]["grade"] == letter, v


def test_gpa_is_weighted_by_credit_hours(api):
    s = new_student(api)
    score(api, s, new_course(api, credits=3), 85)  # A 4.0 x 3
    score(api, s, new_course(api, credits=1), 40)  # F 0.0 x 1
    assert abs(results(api, s)["gpa"] - 3.0) < 1e-6


def test_gpa_is_rounded_to_two_decimals(api):
    s = new_student(api)
    score(api, s, new_course(api, credits=3), 77)  # B+ 3.5
    score(api, s, new_course(api, credits=2), 62)  # C 2.0
    score(api, s, new_course(api, credits=2), 30)  # F 0.0
    assert abs(results(api, s)["gpa"] - 2.07) < 1e-6  # 14.5 / 7 = 2.0714...


def test_entering_a_score_again_replaces_it(api):
    s, c, other = new_student(api), new_course(api, credits=2), new_course(api, credits=2)
    score(api, s, other, 80)
    score(api, s, c, 45)
    status, _ = score(api, s, c, 72)
    assert 200 <= status < 300
    r = results(api, s)
    assert len(r["courses"]) == 2
    entry = by_course(r)[str(c["id"])]
    assert entry["score"] == 72 and entry["grade"] == "B"
    assert abs(r["gpa"] - 3.5) < 1e-6


def test_score_outside_0_to_100_is_refused(api):
    s, c = new_student(api), new_course(api)
    assert 400 <= score(api, s, c, 101)[0] < 500
    assert 400 <= score(api, s, c, -1)[0] < 500
    assert results(api, s)["courses"] == []


def test_score_for_missing_course_is_refused(api):
    s = new_student(api)
    status, _ = api.call("record_score", path_params={"id": s["id"]}, json={"course_id": MISSING, "score": 70})
    assert 400 <= status < 500


def test_course_credits_must_be_1_to_6(api):
    for bad in (0, 7):
        status, _ = api.call("create_course", json={"name": f"Bad {uuid.uuid4().hex[:6]}", "credits": bad})
        assert 400 <= status < 500, bad


def test_results_are_per_student(api):
    a, b, c = new_student(api), new_student(api), new_course(api)
    score(api, a, c, 90)
    score(api, b, c, 55)
    entry = by_course(results(api, b))[str(c["id"])]
    assert entry["grade"] == "D+"
    assert len(results(api, b)["courses"]) == 1


def test_results_for_missing_student_is_404(api):
    status, _ = api.call("get_results", path_params={"id": MISSING})
    assert status == 404
