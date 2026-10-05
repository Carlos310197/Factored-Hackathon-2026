"""Versioned question sets for Jev decisions."""
from importlib import resources
from pathlib import Path
import yaml


def load_question_set(name: str) -> dict:
    """Load a versioned question set.
    
    Args:
        name: Question set name like "understand.v1" or "verify_reply.v1"
    
    Returns:
        Dictionary containing the question set specification
    """
    qset_path = Path(__file__).parent / "questions" / f"{name}.yaml"
    with open(qset_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
