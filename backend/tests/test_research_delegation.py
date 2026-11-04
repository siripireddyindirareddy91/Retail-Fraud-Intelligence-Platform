"""Real full-profile ASGI execution behind the thin API's transport boundary."""
import hashlib

from fastapi.testclient import TestClient
import httpx
import pytest

from app.main import create_app
from app.models import Experiment, MLModel
from app.research.data import FEATURES, generate
from app.research.ml import scores, train
from app.research.schemas import Generation
from app.research.storage import records, write_bundle, write_frame
from app.services import research_runtime
from conftest import register

pytestmark = pytest.mark.skipif(not research_runtime.modules_available("pandas", "sklearn", "pyarrow", "fastparquet"), reason="Real upstream execution requires the full research profile")


def test_delegation_preserves_predictions_datasets_artifacts_streams_and_ownership(client, app, settings, account, headers, tmp_path, monkeypatch):
    frame = generate(Generation(rows=500, fraud_rate=.2, seed=42))
    bundle, _ = train(frame, algorithm="logistic_regression")
    with app.state.sessions() as db:
        dataset = write_frame(db, settings, account["user"]["id"], frame, "Delegation dataset", "statistical", {})
        experiment = Experiment(owner_id=account["user"]["id"], name="Delegation detector", kind="training", config={})
        db.add(experiment)
        db.flush()
        artifact = write_bundle(db, settings, account["user"]["id"], bundle, "Delegation detector")
        model = MLModel(owner_id=account["user"]["id"], artifact_id=artifact.id, experiment_id=experiment.id, name="Delegation detector", algorithm="logistic_regression", version=1, threshold=bundle["threshold"])
        db.add(model)
        db.commit()
        dataset_id, model_id, artifact_id, checksum = dataset.id, model.id, artifact.id, artifact.sha256
    upstream_app = create_app(settings.model_copy(update={"research_api_origin": None}))
    calls = []
    with TestClient(upstream_app) as upstream:
        real_client = httpx.Client

        def send(request):
            assert request.headers.get("authorization")
            assert "cookie" not in request.headers
            assert request.headers.get("x-research-delegated") == "1"
            calls.append(request.url.path)
            response = upstream.request(request.method, request.url.raw_path.decode(), headers=dict(request.headers), content=request.content)
            return httpx.Response(response.status_code, headers=response.headers, content=response.content)

        monkeypatch.setattr(research_runtime.httpx, "Client", lambda **kwargs: real_client(transport=httpx.MockTransport(send), **kwargs))
        # Separate artifact roots demonstrate that the web API does not need a
        # local copy of the research service's model/data/report files.
        app.state.settings = settings.model_copy(update={"research_api_origin": "https://research.example.test", "artifact_root": tmp_path / "thin-api-artifacts"})
        response = client.get(f"/api/v1/datasets/{dataset_id}/preview?limit=2", headers=headers)
        assert response.status_code == 200 and len(response.json()["items"]) == 2
        assert client.get(f"/api/v1/datasets/{dataset_id}/statistics", headers=headers).status_code == 200
        assert client.get("/api/v1/analytics/overview", headers=headers).status_code == 200
        exported = client.get(f"/api/v1/datasets/{dataset_id}/download?format=csv", headers=headers)
        assert exported.status_code == 200 and "transaction_id" in exported.text
        artifact_response = client.get(f"/api/v1/artifacts/{artifact_id}/download", headers=headers)
        assert artifact_response.status_code == 200
        assert hashlib.sha256(artifact_response.content).hexdigest() == checksum
        prediction = client.post("/api/v1/predictions", headers=headers, json={"model_id": model_id, "features": records(frame[FEATURES].head(1))[0]})
        assert prediction.status_code == 200
        assert abs(prediction.json()["probability"] - float(scores(bundle, frame.head(1))[0])) < 1e-8
        assert prediction.json()["ground_truth"] is None
        stream = client.post("/api/v1/streams", headers=headers, json={"max_transactions": 2, "interval_seconds": 1})
        assert stream.status_code == 201
        events = client.get(f"/api/v1/streams/{stream.json()['id']}/events", headers={**headers, "Last-Event-ID": "0"})
        assert events.status_code == 200 and events.text.count("event: transaction") == 2
        assert "event: stopped" in events.text
        other = register(client, email="other-delegation@example.com")
        before = len(calls)
        hidden = client.get(f"/api/v1/datasets/{dataset_id}/preview", headers={"Authorization": "Bearer " + other["access_token"]})
        assert hidden.status_code == 404
        assert len(calls) == before
        assert not app.state.settings.artifact_root.exists()
