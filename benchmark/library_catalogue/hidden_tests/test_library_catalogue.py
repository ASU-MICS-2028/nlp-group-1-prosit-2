import uuid

MISSING = 987654321


def ok(status):
    return 200 <= status < 300


def refused(status):
    return 400 <= status < 500


def new_book(api, copies=2):
    title = f"Things Fall Apart {uuid.uuid4().hex[:6]}"
    status, book = api.call("add_book", json={"title": title, "author": "Chinua Achebe", "copies": copies})
    assert ok(status), book
    return book


def available(api, book):
    status, got = api.call("get_book", path_params={"id": book["id"]})
    assert status == 200, got
    return got["available"]


def borrow(api, book, student):
    return api.call("borrow_book", path_params={"id": book["id"]}, json={"student": student})[0]


def give_back(api, book, student):
    return api.call("return_book", path_params={"id": book["id"]}, json={"student": student})[0]


def test_add_book_returns_it_with_all_copies_on_shelf(api):
    book = new_book(api, copies=3)
    assert "id" in book
    assert book["copies"] == 3
    assert book["available"] == 3


def test_added_book_appears_in_list(api):
    book = new_book(api)
    status, books = api.call("list_books")
    assert status == 200
    assert book["id"] in [b["id"] for b in books]


def test_get_book_by_id(api):
    book = new_book(api)
    status, got = api.call("get_book", path_params={"id": book["id"]})
    assert status == 200
    assert got["title"] == book["title"]
    assert got["author"] == "Chinua Achebe"


def test_get_missing_book_is_404(api):
    status, _ = api.call("get_book", path_params={"id": MISSING})
    assert status == 404


def test_borrowing_takes_one_copy_off_the_shelf(api):
    book = new_book(api, copies=2)
    assert ok(borrow(api, book, "Kwame Asante"))
    assert available(api, book) == 1


def test_borrowing_is_refused_when_no_copies_left(api):
    book = new_book(api, copies=1)
    assert ok(borrow(api, book, "Abena Owusu"))
    assert refused(borrow(api, book, "Yaw Boateng"))
    assert available(api, book) == 0


def test_returning_puts_the_copy_back(api):
    book = new_book(api, copies=2)
    borrow(api, book, "Efua Mensah")
    assert ok(give_back(api, book, "Efua Mensah"))
    assert available(api, book) == 2


def test_returned_copy_can_be_borrowed_again(api):
    book = new_book(api, copies=1)
    borrow(api, book, "Kojo Darko")
    give_back(api, book, "Kojo Darko")
    assert ok(borrow(api, book, "Ama Serwaa"))
    assert available(api, book) == 0


def test_student_who_did_not_borrow_cannot_return(api):
    book = new_book(api, copies=2)
    borrow(api, book, "Akua Badu")
    assert refused(give_back(api, book, "Kofi Annor"))
    assert available(api, book) == 1


def test_cannot_return_a_different_book_than_borrowed(api):
    a, b = new_book(api), new_book(api)
    borrow(api, a, "Esi Quaye")
    assert refused(give_back(api, b, "Esi Quaye"))
    assert available(api, b) == 2


def test_borrowing_one_book_does_not_change_another(api):
    a, b = new_book(api), new_book(api)
    borrow(api, a, "Nana Agyei")
    assert available(api, b) == 2


def test_borrow_missing_book_is_404(api):
    status, _ = api.call("borrow_book", path_params={"id": MISSING}, json={"student": "Yaa Asantewaa"})
    assert status == 404


def test_add_book_without_title_is_refused(api):
    status, _ = api.call("add_book", json={"author": "Ama Ata Aidoo", "copies": 2})
    assert refused(status)
