from app.core.config import normalize_redis_url


def test_normalize_redis_url_adds_scheme_when_missing():
    assert normalize_redis_url("localhost:6379") == "redis://localhost:6379"
    assert normalize_redis_url("redis://localhost:6379") == "redis://localhost:6379"
    assert normalize_redis_url("rediss://localhost:6379") == "rediss://localhost:6379"


def test_normalize_redis_url_keeps_empty_value():
    assert normalize_redis_url("") == ""
    assert normalize_redis_url(None) == ""
