"""Run with either the API-only install or the complete research environment."""
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tomllib

import pytest

from app.models import Experiment, MLModel
from app.research.data import generate
from app.research.ml import train
from app.research.schemas import Generation
from app.research.storage import records, write_bundle
from app.services.research_runtime import modules_available


def test_api_manifest_and_bundle_configuration_preserve_runtime_modules():
    backend = Path(__file__).resolve().parents[1]
    manifest = tomllib.loads((backend / "pyproject.toml").read_text())
    dependencies = manifest["project"]["dependencies"]
    assert not any(item.split(">=")[0] in {"numpy", "pandas", "scipy", "scikit-learn", "joblib", "sdv", "shap", "torch", "mlflow", "matplotlib", "reportlab", "pyarrow", "xgboost", "xgboost-cpu", "fastparquet"} for item in dependencies)
    research = manifest["project"]["optional-dependencies"]["research"]
    assert all(any(item.startswith(name + ">=") for item in research) for name in ("numpy", "pandas", "scipy", "scikit-learn", "xgboost-cpu", "fastparquet", "sdv", "torch", "shap", "mlflow", "matplotlib", "reportlab", "pyarrow"))
    configuration = json.loads((backend / "vercel.json").read_text())["functions"]["asgi.py"]
    assert configuration["includeFiles"] == "app/**"
    assert "app/" not in configuration["excludeFiles"]
    assert "tests/**" in configuration["excludeFiles"]


def test_cold_api_import_loads_no_scientific_libraries(tmp_path):
    environment = dict(os.environ, RF_ENVIRONMENT="test", RF_COOKIE_SECURE="false", RF_JWT_SECRET=secrets.token_urlsafe(48), RF_DATABASE_URL=f"sqlite:///{(tmp_path / 'cold.db').as_posix()}")
    code = "from asgi import app; import sys,json; roots=('numpy','pandas','scipy','sklearn','xgboost','shap','sdv','torch','mlflow','pyarrow','matplotlib','reportlab'); print(json.dumps([name for name in roots if name in sys.modules])); assert len(app.openapi()['paths']) == 55"
    result = subprocess.run([sys.executable, "-c", code], cwd=Path(__file__).resolve().parents[1], env=environment, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, "Cold API import failed"
    assert json.loads(result.stdout.strip()) == []
    assert not (tmp_path / "cold.db").exists()


@pytest.mark.parametrize("algorithm", ["logistic_regression", "random_forest", "xgboost", "isolation_forest"])
@pytest.mark.skipif(not modules_available("numpy", "pandas", "sklearn", "xgboost"), reason="Requires the full research profile; thin API delegation is tested separately")
def test_all_detector_types_score_through_authenticated_api(algorithm, client, app, headers, account):
    frame = generate(Generation(rows=500, fraud_rate=.2, seed=42))
    bundle, _ = train(frame, algorithm=algorithm)
    with app.state.sessions() as db:
        experiment = Experiment(owner_id=account["user"]["id"], name="API profile fit", kind="training", config={})
        db.add(experiment)
        db.flush()
        artifact = write_bundle(db, app.state.settings, account["user"]["id"], bundle, "API profile detector")
        model = MLModel(owner_id=account["user"]["id"], artifact_id=artifact.id, experiment_id=experiment.id, name=algorithm, algorithm=algorithm, version=1, threshold=bundle["threshold"], status="active")
        db.add(model)
        db.commit()
        model_id = model.id
    from app.research.data import FEATURES
    features = records(frame[FEATURES].head(1))[0]
    response = client.post("/api/v1/predictions", headers=headers, json={"model_id": model_id, "features": features})
    assert response.status_code == 200
    assert response.json()["predicted_class"] in (0, 1)
    assert response.json()["ground_truth"] is None
    expected = "anomaly_score" if algorithm == "isolation_forest" else "probability"
    assert 0 <= response.json()[expected] <= 1
    assert client.post("/api/v1/predictions", json={"model_id": model_id, "features": features}).status_code == 401


@pytest.mark.skipif(not modules_available("pandas", "fastparquet"), reason="Requires the full research profile")
def test_api_reading_worker_parquet_preserves_values(tmp_path):
    import importlib.util
    import pandas as pd
    frame = generate(Generation(rows=100, seed=42))
    if importlib.util.find_spec("pyarrow"):
        # Full worker emits PyArrow Parquet; API reads that same file via Fastparquet.
        path = tmp_path / "worker.parquet"
        frame.to_parquet(path, index=False, engine="pyarrow")
    else:
        path = tmp_path / "api.parquet"
        frame.to_parquet(path, index=False, engine="fastparquet")
    loaded = pd.read_parquet(path, engine="fastparquet")
    pd.testing.assert_frame_equal(frame, loaded)


def test_queued_research_and_runtime_disclosure(client, headers):
    import importlib.util
    response = client.post("/api/v1/datasets/generate", headers=headers, json={"name": "Worker-bound dataset", "rows": 100, "seed": 42})
    if modules_available("sdv", "torch", "pyarrow"):
        assert response.status_code == 202
        assert client.get("/api/v1/jobs/" + response.json()["job_id"], headers=headers).json()["state"] == "queued"
    else:
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "research_worker_unavailable"
    capabilities = client.get("/api/v1/capabilities", headers=headers).json()
    assert capabilities["availability_scope"] == "api_process"
    assert capabilities["research_execution"] == "separate_worker"
    if importlib.util.find_spec("sdv") is None:
        assert capabilities["generation"]["ctgan"] is False
        assert capabilities["research_engine_status"] == "external_worker_required"
