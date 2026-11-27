from datetime import datetime

from app.config import Settings
from app.postgres_store import _Filter, _apply_update, _decode, _encode


def test_filter_compiles_nested_or_regex_and_in_without_interpolating_values():
    where = _Filter(
        "reservations",
        {
            "$or": [
                {"guest.email": {"$regex": ".*", "$options": "i"}},
                {"status": {"$in": ["pending", "confirmed"]}},
            ]
        },
    )

    sql = where.compile()

    assert "guest', 'email" in sql
    assert "~*" in sql
    assert "jsonb_array_elements($3::jsonb)" in sql
    assert where.params == ["reservations", ".*", '["pending","confirmed"]']


def test_update_operators_change_nested_values_without_mutating_original():
    original = {"meta": {"count": 1}, "tags": ["first"], "states": ["active", "inactive"]}

    changed = _apply_update(
        original,
        {
            "$inc": {"meta.count": 2},
            "$push": {"tags": "second"},
            "$addToSet": {"tags": "second"},
            "$pull": {"states": "inactive"},
        },
    )

    assert changed == {"meta": {"count": 3}, "tags": ["first", "second"], "states": ["active"]}
    assert original == {"meta": {"count": 1}, "tags": ["first"], "states": ["active", "inactive"]}


def test_json_storage_round_trips_datetimes_and_date_only_strings():
    value = {"at": datetime(2026, 11, 22, 12, 30), "day": "2026-11-22"}

    decoded = _decode(_encode(value))

    assert decoded == value


def test_mongodb_url_is_used_for_database_connection():
    settings = Settings(mongodb_url="mongodb+srv://hotel:secret@cluster.example.mongodb.net")

    assert settings.async_database_url == "mongodb+srv://hotel:secret@cluster.example.mongodb.net"
