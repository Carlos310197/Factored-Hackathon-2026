"""Output guard: a reply may mention only ids that belong to this session (spec §6.4 layer 4)."""
import re

ID_PATTERN = re.compile(r"\b(?:TRX|PRD|CLI|CMP|DSP|HND|RCP)-[A-Z0-9]{8,}\b")


def unknown_ids(text: str, allowed: set[str]) -> set[str]:
    return {m for m in ID_PATTERN.findall(text) if m not in allowed}
