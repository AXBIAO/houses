from __future__ import annotations

from datetime import date

import pytest

from backend.app.domain.listing_search import (
    FilterError,
    GeoPoint,
    ListingFilters,
    add_months,
    compile_filters,
    resolve_stay,
)

TODAY = date(2026, 10, 17)


@pytest.mark.parametrize(
    ("start", "months", "expected"),
    [
        (date(2026, 1, 31), 1, date(2026, 2, 28)),
        (date(2028, 1, 31), 1, date(2028, 2, 29)),
        (date(2026, 10, 17), 3, date(2027, 1, 17)),
        (date(2026, 12, 1), 12, date(2027, 12, 1)),
    ],
)
def test_add_months_clamps_month_end(start, months, expected):
    assert add_months(start, months) == expected


def test_resolve_stay_none_without_dates():
    assert resolve_stay(ListingFilters(), TODAY) is None


def test_resolve_stay_months_from_move_in():
    stay = resolve_stay(ListingFilters(move_in=date(2026, 11, 1), months=6), TODAY)
    assert (stay.start, stay.end, stay.explicit_length) == (date(2026, 11, 1), date(2027, 5, 1), True)


def test_resolve_stay_defaults_move_in_to_today():
    stay = resolve_stay(ListingFilters(months=1), TODAY)
    assert stay.start == TODAY


def test_resolve_stay_single_day_when_only_move_in():
    stay = resolve_stay(ListingFilters(move_in=date(2026, 10, 20)), TODAY)
    assert stay.nights == 1 and not stay.explicit_length


@pytest.mark.parametrize(
    "filters",
    [
        ListingFilters(move_in=date(2026, 10, 1)),
        ListingFilters(move_in=date(2026, 10, 20), move_out=date(2026, 10, 20)),
        ListingFilters(move_in=date(2026, 10, 20), move_out=date(2030, 1, 1)),
    ],
)
def test_resolve_stay_rejects_invalid(filters):
    with pytest.raises(FilterError):
        resolve_stay(filters, TODAY)


def test_compile_keeps_user_input_out_of_sql():
    q = compile_filters(ListingFilters(keyword="'; DROP TABLE listings; --", tags=("近地铁",)), TODAY)
    assert "DROP" not in q.where
    assert "'; DROP TABLE listings; --" in q.params[0]


def test_compile_escapes_like_wildcards():
    q = compile_filters(ListingFilters(keyword="100%_"), TODAY)
    assert q.params[0] == "%100\\%\\_%"


def test_distance_sort_requires_point():
    assert "distance_km" not in compile_filters(ListingFilters(sort="distance"), TODAY).order_by
    q = compile_filters(ListingFilters(sort="distance", near=GeoPoint(30.5, 104.0)), TODAY)
    assert q.order_by.startswith("distance_km") and q.distance_params == (30.5, 30.5, 104.0)
