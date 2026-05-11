from services.osint_intel import (
    analyze_browser_artifact,
    analyze_result_cluster,
    build_browser_followup_plan,
)


def test_result_cluster_analysis_surfaces_credibility_location_and_next_steps():
    cluster = {
        "cluster_size": 3,
        "engines": ["TinEyeScraper", "GoogleLensScraper"],
        "top_result": {
            "url": "https://maps.example.org/place/Times-Square-New-York",
            "title": "Times Square New York original image",
            "similarity_pct": 91,
            "source_domain": "maps.example.org",
        },
        "items": [
            {"url": "https://maps.example.org/place/Times-Square-New-York", "title": "Times Square New York", "similarity_pct": 91},
            {"url": "https://example.org/archive", "title": "NYC archived copy", "similarity_pct": 88},
            {"url": "https://another.example/post", "title": "New York repost", "similarity_pct": 76},
        ],
    }

    analysis = analyze_result_cluster(cluster)

    assert analysis["source_credibility"]["label"] in {"Strong", "Good"}
    assert analysis["match_strength"]["label"] == "Very strong"
    assert analysis["location_clues"]
    assert any("source page" in step.lower() for step in analysis["next_steps"])
    assert analysis["triage_lanes"]


def test_browser_artifact_analysis_extracts_cross_reference_clues():
    artifact = analyze_browser_artifact(
        "https://example.com/post",
        "Contact @needle in Seattle, WA",
        "Reach us at tip@example.com. GPS 47.6062, -122.3321. Archive this page.",
    )

    assert artifact["entities"]["emails"] == ["tip@example.com"]
    assert "@needle" in artifact["entities"]["handles"]
    assert artifact["geo_clues"]
    assert artifact["recommended_actions"]


def test_browser_followup_plan_is_bounded_and_evidence_first():
    plan = build_browser_followup_plan(
        [
            {"url": "https://one.example/a", "title": "Original source"},
            {"url": "https://two.example/b", "title": "Mirror"},
        ],
        max_pages=1,
    )

    assert plan["pages_to_visit"] == ["https://one.example/a"]
    assert plan["mode"] == "bounded_browser_assist"
    assert "approved URL" in plan["safety_note"]
