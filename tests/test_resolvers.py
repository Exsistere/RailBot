from app.nlp.station_resolver import (
    StationResolver,
    TrainClassResolver,
    QuotaResolver,
    DEFAULT_STATION_MAPPING,
    DEFAULT_TRAIN_CLASS_MAPPING,
    DEFAULT_QUOTA_MAPPING,
)


def test_station_resolver_case_insensitive():
    r = StationResolver(DEFAULT_STATION_MAPPING)
    assert r("Mumbai") == "CSTM"
    assert r(" mumbai ") == "CSTM"


def test_train_class_resolver_aliases():
    r = TrainClassResolver(DEFAULT_TRAIN_CLASS_MAPPING)
    assert r("sleeper") == "SL"
    assert r("3AC") == "3A"


def test_quota_resolver_aliases():
    r = QuotaResolver(DEFAULT_QUOTA_MAPPING)
    assert r("tatkal") == "TQ"
    assert r("General") == "GN"

