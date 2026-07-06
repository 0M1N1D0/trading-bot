import pytest

from src.scheduler import parse_interval_seconds


@pytest.mark.parametrize(
    "interval,expected_seconds",
    [
        ("30s", 30),
        ("5m", 300),
        ("30m", 1800),
        ("1h", 3600),
        ("1d", 86400),
        ("2h", 7200),
    ],
)
def test_parse_interval_seconds(interval, expected_seconds):
    assert parse_interval_seconds(interval) == expected_seconds


def test_parse_interval_seconds_rejects_invalid_format():
    with pytest.raises(ValueError):
        parse_interval_seconds("5 minutes")
