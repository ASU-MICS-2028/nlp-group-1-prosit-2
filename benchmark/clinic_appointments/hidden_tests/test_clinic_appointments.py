import uuid


def new_doctor(api):
    name = f"Dr. Abena Owusu {uuid.uuid4().hex[:6]}"
    status, doctor = api.call("create_doctor", json={"name": name, "specialty": "General practice"})
    assert status in (200, 201), doctor
    return doctor


def book(api, doctor, date="2031-02-10", time="09:00", patient="Yaw Darko"):
    return api.call("book_appointment", json={"doctor_id": doctor["id"], "patient_name": patient, "date": date, "time": time})


def booked(api, doctor, **kw):
    status, appt = book(api, doctor, **kw)
    assert status in (200, 201), appt
    return appt


def day_list(api, doctor, date="2031-02-10"):
    status, appts = api.call("list_doctor_appointments", path_params={"id": doctor["id"]}, params={"date": date})
    assert status == 200, appts
    return [a["id"] for a in appts]


def test_created_doctor_appears_in_list(api):
    doctor = new_doctor(api)
    assert "id" in doctor
    status, doctors = api.call("list_doctors")
    assert status == 200
    assert doctor["id"] in [d["id"] for d in doctors]


def test_create_doctor_without_name_is_refused(api):
    status, _ = api.call("create_doctor", json={"specialty": "Dentist"})
    assert 400 <= status < 500


def test_booking_appears_in_doctors_day(api):
    doctor = new_doctor(api)
    appt = booked(api, doctor)
    assert "id" in appt
    status, appts = api.call("list_doctor_appointments", path_params={"id": doctor["id"]}, params={"date": "2031-02-10"})
    assert status == 200
    assert [a["patient_name"] for a in appts] == ["Yaw Darko"]


def test_day_list_only_shows_that_date(api):
    doctor = new_doctor(api)
    monday = booked(api, doctor, date="2031-02-10")
    tuesday = booked(api, doctor, date="2031-02-11")
    assert day_list(api, doctor, "2031-02-10") == [monday["id"]]
    assert day_list(api, doctor, "2031-02-11") == [tuesday["id"]]


def test_day_list_only_shows_that_doctor(api):
    a, b = new_doctor(api), new_doctor(api)
    booked(api, a)
    assert day_list(api, b) == []


def test_double_booking_same_slot_is_refused(api):
    doctor = new_doctor(api)
    booked(api, doctor, patient="Kofi")
    status, _ = book(api, doctor, patient="Esi")
    assert 400 <= status < 500
    assert len(day_list(api, doctor)) == 1


def test_same_slot_with_another_doctor_is_allowed(api):
    a, b = new_doctor(api), new_doctor(api)
    booked(api, a)
    status, _ = book(api, b)
    assert status in (200, 201)


def test_other_time_or_other_date_is_allowed(api):
    doctor = new_doctor(api)
    booked(api, doctor, date="2031-02-10", time="09:00")
    status, _ = book(api, doctor, date="2031-02-10", time="14:30")
    assert status in (200, 201)
    status, _ = book(api, doctor, date="2031-02-12", time="09:00")
    assert status in (200, 201)


def test_booking_unknown_doctor_is_refused(api):
    status, _ = api.call("book_appointment",
                         json={"doctor_id": 987654321, "patient_name": "Ama", "date": "2031-02-10", "time": "09:00"})
    assert 400 <= status < 500


def test_booking_without_patient_name_is_refused(api):
    doctor = new_doctor(api)
    status, _ = api.call("book_appointment", json={"doctor_id": doctor["id"], "date": "2031-02-10", "time": "09:00"})
    assert 400 <= status < 500


def test_cancel_removes_appointment(api):
    doctor = new_doctor(api)
    appt = booked(api, doctor)
    status, _ = api.call("cancel_appointment", path_params={"id": appt["id"]})
    assert 200 <= status < 300
    assert day_list(api, doctor) == []


def test_cancel_frees_the_slot(api):
    doctor = new_doctor(api)
    appt = booked(api, doctor, patient="Kofi")
    api.call("cancel_appointment", path_params={"id": appt["id"]})
    status, _ = book(api, doctor, patient="Esi")
    assert status in (200, 201)
    assert len(day_list(api, doctor)) == 1


def test_cancel_missing_appointment_is_refused(api):
    status, _ = api.call("cancel_appointment", path_params={"id": 987654321})
    assert 400 <= status < 500
