from app.nlp.semantic_extractor import SemanticExtractor
from app.nlp.semantic_schema import SemanticContext, ConfidenceValue


class FakeLLM:
    def __init__(self):
        self.calls = 0

    def generate_json(self, prompt: str, system_prompt: str = "") -> dict:
        self.calls += 1
        return {
            "origin_station": "Delhi",
            "destination_station": "Mumbai",
            "travel_date": "2026-06-15",
            "train_class": "sleeper",
            "quota": "general",
            "passenger_count": "1",
        }


def _parser(data: dict) -> SemanticContext:
    return SemanticContext(
        origin_station=ConfidenceValue(data.get("origin_station")),
        destination_station=ConfidenceValue(data.get("destination_station")),
        travel_date=ConfidenceValue(data.get("travel_date")),
        train_class=ConfidenceValue(data.get("train_class")),
        quota=ConfidenceValue(data.get("quota")),
        passenger_count=ConfidenceValue(data.get("passenger_count")),
    )


def test_semantic_extractor_calls_llm_once():
    llm = FakeLLM()
    ex = SemanticExtractor(llm_client=llm, parser=_parser)
    ctx = ex.extract("delhi to mumbai on 2026-06-15", intent_hint="SEARCH_TRAINS")
    assert llm.calls == 1
    assert ctx.origin_station and ctx.origin_station.value.lower() == "delhi"

