from importlib import resources
from pathlib import Path
import yaml


def load_question_set(name: str) -> dict:
    qset_path = Path(__file__).parent / "questions" / f"{name}.yaml"
    with open(qset_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
