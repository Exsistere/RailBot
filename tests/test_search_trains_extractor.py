from app.planner_extractors.search_trains_extractor import SearchTrainsParamExtractor
from app.nlp.semantic_schema import SemanticContext, ConfidenceValue


def test_search_trains_extractor_is_deterministic_and_derives_weekday():
    ctx = SemanticContext(
        origin_station=ConfidenceValue("NDLS"),
        destination_station=ConfidenceValue("CSTM"),
        travel_date=ConfidenceValue("2026-06-15"),
        quota=ConfidenceValue("GN"),
        train_class=ConfidenceValue("SL"),
    )
    out = SearchTrainsParamExtractor().extract(ctx)
    assert out["origin_station"] == "NDLS"
    assert out["destination_station"] == "CSTM"
    assert out["travel_date"] == "2026-06-15"
    assert out["travel_day"] == "monday"
    assert out["quota"] == "GN"


def test_search_trains_extractor_prefers_precomputed_weekday():
    ctx = SemanticContext(
        origin_station=ConfidenceValue("NDLS"),
        destination_station=ConfidenceValue("CSTM"),
        travel_date=ConfidenceValue("2026-06-15"),
        weekday_from_date="sunday",
    )
    out = SearchTrainsParamExtractor().extract(ctx)
    assert out["travel_day"] == "sunday"

