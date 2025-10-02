from utils import timezone as tz


def test_get_local_timezone_uses_zoneinfo(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(tz, "ZoneInfo", lambda name: sentinel)
    assert tz.get_local_timezone() is sentinel


def test_get_local_timezone_fallback(monkeypatch):
    def raiser(_):
        raise tz.ZoneInfoNotFoundError

    monkeypatch.setattr(tz, "ZoneInfo", raiser)
    assert tz.get_local_timezone() is tz.DEFAULT_OFFSET
