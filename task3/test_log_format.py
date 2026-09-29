"""Tests for terminal log sanitising and provider metric formatting."""

import pytest

from task3.log_format import inline_value, optional_count


def test_inline_value_collapses_newlines_whitespace_and_empty_text():
    assert inline_value("bad\n[DONE]   status=SUCCESS") == "bad [DONE] status=SUCCESS"
    assert inline_value(" \t ") == "unknown"
    assert inline_value("abcdef", limit=3) == "abc"


def test_inline_value_requires_positive_limit():
    with pytest.raises(ValueError, match="positive"):
        inline_value("x", limit=0)


def test_optional_count_uses_na_only_when_metric_is_missing():
    assert optional_count(None) == "na"
    assert optional_count(0) == "0"
    assert optional_count(42) == "42"
