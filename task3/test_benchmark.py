"""Tests for deterministic Step 13 scoring and cost reporting."""

from task3.benchmark import (
    estimated_openai_cost_usd,
    load_cases,
    plans_match,
    summarize,
)
from task3.planner import PlanningResult
from task3.validator import validate_plan


def test_fixed_suite_has_required_group_counts_and_unique_ids():
    cases = load_cases()

    assert len(cases) == 20
    assert len({case["id"] for case in cases}) == 20
    assert sum(case["group"] == "basic" for case in cases) == 10
    assert sum(case["group"] == "paraphrase" for case in cases) == 5
    assert sum(case["group"] == "invalid" for case in cases) == 5


def test_semantic_match_ignores_numeric_json_representation_but_not_direction():
    expected = {
        "accepted": True,
        "actions": [
            {"type": "move", "vx": 0, "vy": -0.2, "wz": 0, "duration_s": 1}
        ],
    }
    equivalent = {
        "accepted": True,
        "actions": [
            {
                "type": "move",
                "vx": 0.0,
                "vy": -0.2,
                "wz": 0.0,
                "duration_s": 1.0,
            }
        ],
    }
    wrong_direction = {
        "accepted": True,
        "actions": [
            {"type": "move", "vx": 0, "vy": 0.2, "wz": 0, "duration_s": 1}
        ],
    }

    assert plans_match(expected, equivalent)
    assert not plans_match(expected, wrong_direction)


def test_openai_cost_uses_cached_and_uncached_rates_separately():
    result = PlanningResult(
        plan=validate_plan(
            {"accepted": False, "message": "Rejected.", "actions": []}
        ),
        provider="openai",
        model="gpt-4o-mini",
        latency_s=1.0,
        raw_json="{}",
        input_tokens=1_000,
        cached_input_tokens=400,
        output_tokens=100,
    )

    assert estimated_openai_cost_usd(result) == 0.00018


def test_summary_reports_group_accuracy_failures_tokens_and_latency():
    records = [
        {
            "id": "a",
            "group": "basic",
            "correct": True,
            "latency_s": 1.0,
            "input_tokens": 10,
            "cached_input_tokens": 2,
            "output_tokens": 3,
            "estimated_cost_usd": 0.001,
        },
        {
            "id": "b",
            "group": "paraphrase",
            "correct": False,
            "latency_s": 3.0,
            "input_tokens": 20,
            "cached_input_tokens": 4,
            "output_tokens": 5,
            "estimated_cost_usd": 0.002,
        },
        {
            "id": "c",
            "group": "invalid",
            "correct": True,
            "latency_s": 2.0,
            "input_tokens": None,
            "cached_input_tokens": None,
            "output_tokens": None,
            "estimated_cost_usd": 0.0,
        },
    ]

    summary = summarize(records)

    assert summary["correct"] == 2
    assert summary["accuracy_percent"] == 66.7
    assert summary["latency_mean_s"] == 2.0
    assert summary["latency_median_s"] == 2.0
    assert summary["input_tokens"] == 30
    assert summary["cached_input_tokens"] == 6
    assert summary["output_tokens"] == 8
    assert summary["estimated_cost_usd"] == 0.003
    assert summary["failures"] == ["b"]
