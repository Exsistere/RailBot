from app.nlp.semantic_schema import ConfidenceValue, SemanticContext
from app.planner_extractors.check_pnr_extractor import CheckPNRParamExtractor


def test_check_pnr_extractor_reads_pnr_from_semantic_context():
    ctx = SemanticContext(pnr_number=ConfidenceValue("8106636505"))
    out = CheckPNRParamExtractor().extract(ctx)
    assert out["pnr_number"] == "8106636505"


def test_check_pnr_extractor_handles_missing_pnr():
    out = CheckPNRParamExtractor().extract(SemanticContext.empty())
    assert out["pnr_number"] is None

