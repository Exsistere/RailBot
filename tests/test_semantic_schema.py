from dataclasses import FrozenInstanceError

from app.nlp.semantic_schema import ConfidenceValue, SemanticContext


def test_semantic_context_is_frozen():
    ctx = SemanticContext.empty()
    try:
        ctx.schema_version = "v2"  # type: ignore[misc]
        raise AssertionError("Expected SemanticContext to be frozen")
    except FrozenInstanceError:
        pass


def test_with_weekday_returns_new_instance():
    ctx = SemanticContext.empty()
    ctx2 = ctx.with_weekday("monday")
    assert ctx.weekday_from_date is None
    assert ctx2.weekday_from_date == "monday"
    assert ctx2 is not ctx


def test_confidence_value_defaults():
    cv = ConfidenceValue(value="NDLS")
    assert cv.value == "NDLS"
    assert cv.confidence == 1.0

