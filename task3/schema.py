"""Load the canonical action-plan schema for LLM structured output."""

from copy import deepcopy
import json
from pathlib import Path
from typing import Any


_SCHEMA_PATH = Path(__file__).with_name("action_plan.schema.json")


def load_action_plan_schema() -> dict[str, Any]:
    """Return an independent copy of the checked-in JSON schema."""
    with _SCHEMA_PATH.open(encoding="utf-8") as source:
        return json.load(source)


def openai_response_format() -> dict[str, Any]:
    """Return the strict format object accepted by the OpenAI Responses API."""
    return {
        "type": "json_schema",
        "name": "task3_action_plan",
        "strict": True,
        "schema": deepcopy(load_action_plan_schema()),
    }
