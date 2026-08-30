from datetime import UTC, datetime, timedelta

from freezegun import freeze_time

from core.link import consume_link_code, create_link_code


@freeze_time("2026-08-30 10:00:00")
def test_create_and_consume_link_code() -> None:
    req = create_link_code("ha-user-1")
    assert len(req.code) == 6
    ha_user_id = consume_link_code(req.code)
    assert ha_user_id == "ha-user-1"


@freeze_time("2026-08-30 10:00:00")
def test_consume_link_code_twice_fails() -> None:
    req = create_link_code("ha-user-2")
    assert consume_link_code(req.code) == "ha-user-2"
    assert consume_link_code(req.code) is None


@freeze_time("2026-08-30 10:00:00")
def test_expired_link_code() -> None:
    req = create_link_code("ha-user-3")
    with freeze_time(datetime.now(UTC) + timedelta(minutes=11)):
        assert consume_link_code(req.code) is None
