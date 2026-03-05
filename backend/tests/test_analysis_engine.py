from app.services.analysis_engine import build_report


def test_report_shape_and_bounds():
    report = build_report("test-seed")
    assert 0 <= report["hook_score"] <= 100
    assert 0 <= report["pacing_score"] <= 100
    assert 0 <= report["confidence"] <= 1
    assert "hook_analysis" in report
    assert "pacing_timeline" in report
    assert "caption_formula" in report
    assert "remake_template" in report
