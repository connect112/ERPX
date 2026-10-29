"""
A team member's hours: who can be given which appointment. Someone with no hours set is not restricted; with hours, only appointments that
fall completely inside one of their windows (India time) can be given to them -- when assigning, and when an assigned appointment is moved.
"""
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select

from modules.pentrix_ops.models import PentrixBooking, PentrixStaffAvailability
from tests.api.test_pentrix_ops import person, pentrix, sync  # noqa: F401 - the fixture is used by name

pytestmark = pytest.mark.api

_P = "/api/v1/pentrix-ops"
IST = ZoneInfo("Asia/Kolkata")


def tuesday(hour: int, minute: int = 0, weeks: int = 1) -> datetime:
    """A Tuesday in India at that wall-clock time, as the instant Pentrix would send."""
    today = datetime.now(IST).date()
    day = today + timedelta(days=((1 - today.weekday()) % 7 or 7) + 7 * (weeks - 1))
    return datetime.combine(day, time(hour, minute), tzinfo=IST).astimezone(timezone.utc)


async def one_booking(client, db_session, auth_headers, pentrix, start):
    made = pentrix.add(candidate_name="Asha", start=start)
    await sync(client, auth_headers)
    return (await db_session.execute(select(PentrixBooking).where(PentrixBooking.pentrix_booking_id == made["id"]))).scalar_one()


async def put_hours(client, headers, user_id, windows):
    return await client.put(f"{_P}/staff-hours/{user_id}", headers=headers, json={"windows": windows})


async def assign(client, headers, booking, user_id):
    return await client.post(f"{_P}/bookings/{booking.id}/assign", headers=headers, json={"staff_user_id": str(user_id)})


async def test_a_team_member_with_no_hours_set_is_not_restricted(client, db_session, organization, auth_headers, pentrix):
    staff, _ = await person(db_session, organization, ["pentrix_ops.bookings.assigned"], "Priya Nair")
    team = (await client.get(f"{_P}/staff-hours", headers=auth_headers)).json()
    assert [(t["full_name"], t["restricted"], t["windows"]) for t in team] == [("Priya Nair", False, [])]
    booking = await one_booking(client, db_session, auth_headers, pentrix, tuesday(23, 30))  # the oddest hour
    assert (await assign(client, auth_headers, booking, staff.id)).status_code == 200


async def test_an_appointment_must_fall_completely_inside_a_window(client, db_session, organization, auth_headers, pentrix):
    staff, _ = await person(db_session, organization, ["pentrix_ops.bookings.assigned"], "Priya Nair")
    saved = await put_hours(client, auth_headers, staff.id, [{"weekday": 1, "start": "18:00", "end": "20:00"}])
    assert saved.status_code == 200 and saved.json()["restricted"] is True and saved.json()["windows"] == [{"weekday": 1, "start": "18:00", "end": "20:00"}]

    inside = await one_booking(client, db_session, auth_headers, pentrix, tuesday(18))      # 18:00-19:00
    assert (await assign(client, auth_headers, inside, staff.id)).status_code == 200
    end_edge = await one_booking(client, db_session, auth_headers, pentrix, tuesday(19))    # 19:00-20:00, ends exactly when the window does
    assert (await assign(client, auth_headers, end_edge, staff.id)).status_code == 200
    straddles = await one_booking(client, db_session, auth_headers, pentrix, tuesday(19, 30))   # 19:30-20:30 runs past the end
    refused = await assign(client, auth_headers, straddles, staff.id)
    assert refused.status_code == 409 and "not available at that time" in refused.text and "Tue 18:00-20:00" in refused.text
    too_early = await one_booking(client, db_session, auth_headers, pentrix, tuesday(16))
    assert (await assign(client, auth_headers, too_early, staff.id)).status_code == 409
    wrong_day = await one_booking(client, db_session, auth_headers, pentrix, tuesday(18) + timedelta(days=1))  # Wednesday at the same hour
    assert (await assign(client, auth_headers, wrong_day, staff.id)).status_code == 409


async def test_taking_the_hours_away_lifts_the_restriction(client, db_session, organization, auth_headers, pentrix):
    staff, _ = await person(db_session, organization, ["pentrix_ops.bookings.assigned"], "Priya Nair")
    await put_hours(client, auth_headers, staff.id, [{"weekday": 0, "start": "09:00", "end": "10:00"}])
    booking = await one_booking(client, db_session, auth_headers, pentrix, tuesday(18))
    assert (await assign(client, auth_headers, booking, staff.id)).status_code == 409
    cleared = await put_hours(client, auth_headers, staff.id, [])
    assert cleared.json()["restricted"] is False and cleared.json()["windows"] == []
    assert (await db_session.execute(select(PentrixStaffAvailability))).first() is None
    assert (await assign(client, auth_headers, booking, staff.id)).status_code == 200


async def test_one_members_hours_do_not_affect_another(client, db_session, organization, auth_headers, pentrix):
    limited, _ = await person(db_session, organization, ["pentrix_ops.bookings.assigned"], "Limited")
    free, _ = await person(db_session, organization, ["pentrix_ops.bookings.assigned"], "Free")
    await put_hours(client, auth_headers, limited.id, [{"weekday": 4, "start": "10:00", "end": "11:00"}])
    booking = await one_booking(client, db_session, auth_headers, pentrix, tuesday(18))
    assert (await assign(client, auth_headers, booking, limited.id)).status_code == 409
    assert (await assign(client, auth_headers, booking, free.id)).status_code == 200


async def test_moving_an_assigned_appointment_outside_the_members_hours_is_refused(client, db_session, organization, auth_headers, pentrix):
    staff, _ = await person(db_session, organization, ["pentrix_ops.bookings.assigned"], "Priya Nair")
    await put_hours(client, auth_headers, staff.id, [{"weekday": 1, "start": "18:00", "end": "21:00"}])
    booking = await one_booking(client, db_session, auth_headers, pentrix, tuesday(18))
    assert (await assign(client, auth_headers, booking, staff.id)).status_code == 200
    outside = await client.post(f"{_P}/bookings/{booking.id}/reschedule", headers=auth_headers, json={"slot_start": tuesday(8).isoformat()})
    assert outside.status_code == 409 and "not available at that time" in outside.text and "Reassign it first" in outside.text
    inside = await client.post(f"{_P}/bookings/{booking.id}/reschedule", headers=auth_headers, json={"slot_start": tuesday(19).isoformat()})
    assert inside.status_code == 200


async def test_bad_hours_are_refused_before_anything_is_saved(client, db_session, organization, auth_headers, pentrix):
    staff, _ = await person(db_session, organization, ["pentrix_ops.bookings.assigned"], "Priya Nair")
    plain, _ = await person(db_session, organization, ["email_templates.view"], "Not on the team")
    for bad in (
        [{"weekday": 7, "start": "18:00", "end": "19:00"}],
        [{"weekday": -1, "start": "18:00", "end": "19:00"}],
        [{"weekday": 1, "start": "19:00", "end": "18:00"}],
        [{"weekday": 1, "start": "18:00", "end": "18:00"}],
        [{"weekday": 1, "start": "6pm", "end": "7pm"}],
        [{"weekday": 1, "start": "25:00", "end": "26:00"}],
        [{"weekday": 1, "start": "18:00", "end": "20:00"}, {"weekday": 1, "start": "19:00", "end": "21:00"}],  # overlap on one day
    ):
        assert (await put_hours(client, auth_headers, staff.id, bad)).status_code == 422, bad
    assert (await db_session.execute(select(PentrixStaffAvailability))).first() is None
    assert (await put_hours(client, auth_headers, plain.id, [{"weekday": 1, "start": "18:00", "end": "19:00"}])).status_code == 422  # cannot take appointments at all
    two = await put_hours(client, auth_headers, staff.id, [{"weekday": 1, "start": "10:00", "end": "12:00"}, {"weekday": 1, "start": "14:00", "end": "16:00"}, {"weekday": 3, "start": "18:00", "end": "21:00"}])
    assert two.status_code == 200 and len(two.json()["windows"]) == 3  # separate windows, even on one day, are fine


async def test_viewing_and_changing_hours_are_separate_permissions(client, db_session, organization, auth_headers, pentrix):
    staff, _ = await person(db_session, organization, ["pentrix_ops.bookings.assigned"], "Priya Nair")
    _, viewer = await person(db_session, organization, ["pentrix_ops.bookings.view"])
    _, mine_only = await person(db_session, organization, ["pentrix_ops.bookings.assigned"])
    assert (await client.get(f"{_P}/staff-hours", headers=viewer)).status_code == 200
    assert (await put_hours(client, viewer, staff.id, [])).status_code == 403
    assert (await client.get(f"{_P}/staff-hours", headers=mine_only)).status_code == 403
