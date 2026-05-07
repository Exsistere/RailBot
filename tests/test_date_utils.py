import pytest

from app.nlp.date_utils import derive_weekday, is_valid_iso_date


def test_is_valid_iso_date():
    assert is_valid_iso_date("2026-06-15") is True
    assert is_valid_iso_date("2026-6-15") is False
    assert is_valid_iso_date("not-a-date") is False


def test_derive_weekday():
    # 2026-06-15 is Monday
    assert derive_weekday("2026-06-15") == "monday"


def test_derive_weekday_invalid_raises():
    with pytest.raises(ValueError):
        derive_weekday("2026-99-99")

