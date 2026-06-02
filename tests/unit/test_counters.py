from ai_ha.ingest.counters import HourBucketRing


def test_hour_bucket_from_ts():
    ring = HourBucketRing()
    assert ring.bucket_for(3_600_000) == 1
    assert ring.bucket_for(7_199_999) == 1
    assert ring.bucket_for(7_200_000) == 2


def test_now_bucket_unix():
    expected = 100
    actual = HourBucketRing().now_bucket(now_ms=expected * 3_600_000)
    assert actual == expected
