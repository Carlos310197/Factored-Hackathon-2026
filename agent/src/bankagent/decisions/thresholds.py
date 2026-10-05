"""Versioned decision thresholds."""
from dataclasses import dataclass
from pathlib import Path
import yaml


@dataclass
class Thresholds:
    """Decision thresholds (labeled synthetic illustrative values; tuned in spec 2)."""
    version: str
    intent_min_p: float
    intent_min_margin: float
    target_min_p: float
    target_min_margin: float
    handoff_noul: dict[str, float]
    offer_human_noul: dict[str, float]
    injection_attempt: float
    confirmation_confirm: float
    claim_supported: float
    promises_unverified_action: float
    max_clarifications: int
    max_confirmation_asks: int
    max_jev_failures: int
    max_injections: int


def load_thresholds(path: Path | None = None) -> Thresholds:
    """Load thresholds from YAML file.
    
    Args:
        path: Optional path to thresholds YAML. Defaults to thresholds.v1.yaml in same directory.
    
    Returns:
        Thresholds dataclass with all threshold values
    """
    if path is None:
        path = Path(__file__).parent / "thresholds.v1.yaml"
    
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    
    return Thresholds(
        version=data["version"],
        intent_min_p=data["intent"]["min_p"],
        intent_min_margin=data["intent"]["min_margin"],
        target_min_p=data["target_transaction"]["min_p"],
        target_min_margin=data["target_transaction"]["min_margin"],
        handoff_noul=data["handoff_noul"],
        offer_human_noul=data["offer_human_noul"],
        injection_attempt=data["injection_attempt"],
        confirmation_confirm=data["confirmation_confirm"],
        claim_supported=data["claim_supported"],
        promises_unverified_action=data["promises_unverified_action"],
        max_clarifications=data["max_clarifications"],
        max_confirmation_asks=data["max_confirmation_asks"],
        max_jev_failures=data["max_jev_failures"],
        max_injections=data["max_injections"],
    )
