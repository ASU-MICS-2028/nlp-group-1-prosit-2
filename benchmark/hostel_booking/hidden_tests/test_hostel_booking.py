import uuid

MISSING = 987654321


def new_room(api, beds):
    status, room = api.call("create_room", json={"name": f"Room {uuid.uuid4().hex[:6]}", "beds": beds})
    assert status in (200, 201), room
    return room


def book(api, room, check_in, check_out):
    return api.call("book_bed", path_params={"id": room["id"]},
                    json={"student_name": f"Kojo {uuid.uuid4().hex[:4]}", "check_in": check_in, "check_out": check_out})


def booked(api, room, check_in, check_out):
    status, b = book(api, room, check_in, check_out)
    assert status in (200, 201), b
    return b


def refused(status):
    return 400 <= status < 500


def d(day):
    return f"2026-12-{day:02d}"


def free(api, room, check_in, check_out):
    status, rows = api.call("free_beds", params={"check_in": check_in, "check_out": check_out})
    assert status == 200, rows
    mine = [r for r in rows if str(r["room_id"]) == str(room["id"])]
    assert len(mine) == 1, mine
    return mine[0]["free_beds"]


def test_create_room(api):
    room = new_room(api, 4)
    assert "id" in room
    assert room["beds"] == 4


def test_booking_returns_an_id(api):
    room = new_room(api, 1)
    status, b = book(api, room, d(1), d(3))
    assert status in (200, 201)
    assert "id" in b


def test_full_room_refuses_overlapping_stay(api):
    room = new_room(api, 1)
    booked(api, room, d(10), d(12))
    assert refused(book(api, room, d(11), d(13))[0])
    assert refused(book(api, room, d(9), d(11))[0])
    assert refused(book(api, room, d(10), d(12))[0])


def test_leaving_day_is_not_a_night(api):
    room = new_room(api, 1)
    booked(api, room, d(10), d(12))
    status, _ = book(api, room, d(12), d(14))
    assert status in (200, 201)
    status, _ = book(api, room, d(8), d(10))
    assert status in (200, 201)


def test_leaving_date_must_be_after_arrival(api):
    room = new_room(api, 2)
    assert refused(book(api, room, d(5), d(5))[0])
    assert refused(book(api, room, d(6), d(5))[0])
    assert free(api, room, d(1), d(10)) == 2


def test_beds_fill_up_one_by_one(api):
    room = new_room(api, 2)
    booked(api, room, d(1), d(5))
    booked(api, room, d(2), d(4))
    assert refused(book(api, room, d(3), d(6))[0])


def test_capacity_is_checked_per_night(api):
    # 2 beds: the first two stays never share a night, so a third that overlaps each of them still fits
    room = new_room(api, 2)
    booked(api, room, d(1), d(3))
    booked(api, room, d(3), d(5))
    status, _ = book(api, room, d(2), d(4))
    assert status in (200, 201)
    assert refused(book(api, room, d(2), d(3))[0])


def test_one_full_night_refuses_a_long_stay(api):
    room = new_room(api, 1)
    booked(api, room, d(10), d(11))
    assert refused(book(api, room, d(5), d(15))[0])


def test_cancel_frees_the_bed(api):
    room = new_room(api, 1)
    b = booked(api, room, d(10), d(12))
    status, _ = api.call("cancel_booking", path_params={"id": b["id"]})
    assert 200 <= status < 300
    status, _ = book(api, room, d(10), d(12))
    assert status in (200, 201)


def test_cancel_twice_or_missing_is_refused(api):
    room = new_room(api, 1)
    b = booked(api, room, d(10), d(12))
    api.call("cancel_booking", path_params={"id": b["id"]})
    assert refused(api.call("cancel_booking", path_params={"id": b["id"]})[0])
    assert refused(api.call("cancel_booking", path_params={"id": MISSING})[0])


def test_free_beds_for_a_range(api):
    room = new_room(api, 3)
    booked(api, room, d(10), d(12))
    booked(api, room, d(11), d(13))
    assert free(api, room, d(10), d(14)) == 1  # night of the 11th has both
    assert free(api, room, d(12), d(14)) == 2
    assert free(api, room, d(13), d(15)) == 3
    assert free(api, room, d(8), d(10)) == 3


def test_free_beds_counts_the_busiest_night(api):
    room = new_room(api, 2)
    booked(api, room, d(1), d(3))
    booked(api, room, d(3), d(5))
    assert free(api, room, d(1), d(5)) == 1


def test_free_beds_after_cancel(api):
    room = new_room(api, 2)
    b = booked(api, room, d(20), d(25))
    booked(api, room, d(20), d(22))
    assert free(api, room, d(20), d(25)) == 0
    api.call("cancel_booking", path_params={"id": b["id"]})
    assert free(api, room, d(20), d(25)) == 1


def test_rooms_do_not_share_beds(api):
    a, b = new_room(api, 1), new_room(api, 1)
    booked(api, a, d(10), d(12))
    status, _ = book(api, b, d(10), d(12))
    assert status in (200, 201)


def test_booking_missing_room_is_refused(api):
    status, _ = api.call("book_bed", path_params={"id": MISSING},
                         json={"student_name": "Yaa", "check_in": d(1), "check_out": d(2)})
    assert refused(status)
