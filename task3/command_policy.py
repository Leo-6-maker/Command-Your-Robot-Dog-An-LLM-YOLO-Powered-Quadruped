"""Provider-neutral local rejection rules for terminal commands."""

import re
import unicodedata


_DANGEROUS_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\battack\b",
        r"\bhurt\b",
        r"\binjure\b",
        r"\bhit\b",
        r"\bram\b",
        r"\bcrash\b",
        r"\bdestroy\b",
        r"\bdamage\b",
        r"\brun\s+over\b",
        r"\bknock\s+over\b",
    )
)


def local_rejection_reason(command: str) -> str | None:
    """Reject clear policy violations before any paid provider request.

    Ambiguous and unrelated English commands are intentionally left to the LLM;
    this local layer only handles cases that can be identified conservatively.
    """
    if not isinstance(command, str):
        raise TypeError("command must be text")
    if any(_is_non_ascii_letter(character) for character in command):
        return "Please enter the robot command in English."
    if any(pattern.search(command) for pattern in _DANGEROUS_PATTERNS):
        return "Unsafe or harmful robot commands are not allowed."
    return None


def _is_non_ascii_letter(character: str) -> bool:
    return ord(character) > 127 and unicodedata.category(character).startswith("L")
