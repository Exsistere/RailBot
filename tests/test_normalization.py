from app.nlp.normalization import canonicalize_semantic_context
from app.nlp.semantic_schema import SemanticContext, ConfidenceValue
from app.nlp.station_resolver import (
    StationResolver,
    TrainClassResolver,
    QuotaResolver,
    DEFAULT_STATION_MAPPING,
    DEFAULT_TRAIN_CLASS_MAPPING,
    DEFAULT_QUOTA_MAPPING,
)


def test_canonicalize_stations_class_quota_and_pax():
    ctx = SemanticContext(
        origin_station=ConfidenceValue("Mumbai"),
        destination_station=ConfidenceValue("new delhi"),
        travel_date=ConfidenceValue("2026-06-15"),
        train_class=ConfidenceValue("sleeper"),
        quota=ConfidenceValue("tatkal"),
        passenger_count=ConfidenceValue("2"),
    )

    resolvers = {
        "station": StationResolver(DEFAULT_STATION_MAPPING),
        "train_class": TrainClassResolver(DEFAULT_TRAIN_CLASS_MAPPING),
        "quota": QuotaResolver(DEFAULT_QUOTA_MAPPING),
    }
    out = canonicalize_semantic_context(ctx, resolvers)

    assert out.origin_station and out.origin_station.value == "CSTM"
    assert out.destination_station and out.destination_station.value == "NDLS"
    assert out.train_class and out.train_class.value == "SL"
    assert out.quota and out.quota.value == "TQ"
    assert out.passenger_count and out.passenger_count.value == "2"


def test_canonicalize_invalid_class_and_quota_become_none():
    ctx = SemanticContext(
        train_class=ConfidenceValue("spaceship"),
        quota=ConfidenceValue("vip"),
    )
    out = canonicalize_semantic_context(ctx, resolvers={})
    assert out.train_class is None
    assert out.quota is None

