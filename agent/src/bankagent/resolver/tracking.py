"""MLflow tracking for resolver training runs. Local store under agent/mlruns/ (gitignored)."""
from pathlib import Path


class MlflowTracker:
    def __init__(self, root: Path, experiment: str = "transaction-resolver"):
        import mlflow

        root.mkdir(parents=True, exist_ok=True)
        mlflow.set_tracking_uri(f"sqlite:///{root / 'mlflow.db'}")
        if mlflow.get_experiment_by_name(experiment) is None:
            mlflow.create_experiment(experiment, artifact_location=(root / "artifacts").resolve().as_uri())
        mlflow.set_experiment(experiment)
        self.mlflow = mlflow

    def log(self, run_name: str, params: dict, metrics: dict, artifact_dir: Path) -> None:
        with self.mlflow.start_run(run_name=run_name):
            self.mlflow.log_params({k: v for k, v in params.items() if v is not None})
            self.mlflow.log_metrics({k: float(v) for k, v in metrics.items() if isinstance(v, (int, float))})
            self.mlflow.log_artifacts(str(artifact_dir))
