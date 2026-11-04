import io
import json
import pickle

import numpy as np
import pandas as pd

from ..models import Artifact, Dataset
from ..services.artifacts import inspect_artifact, safe_path, write_bytes


def clean(value):
    if isinstance(value, dict):
        return {str(key): clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [clean(item) for item in value]
    if isinstance(value, (float, np.floating)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def records(frame):
    return json.loads(frame.to_json(orient="records"))


def read_frame(db, settings, dataset):
    artifact = db.get(Artifact, dataset.artifact_id)
    if not inspect_artifact(settings.artifact_root, artifact)["valid"]:
        raise ValueError("Dataset integrity check failed")
    return pd.read_parquet(safe_path(settings.artifact_root, artifact.storage_key))


def write_frame(db, settings, owner_id, frame, name, method, config):
    buffer = io.BytesIO()
    frame.to_parquet(buffer, index=False)
    artifact = write_bytes(db, settings.artifact_root, owner_id, f"{name[:80]}.parquet", buffer.getvalue(), "application/vnd.apache.parquet", ".parquet")
    dataset = Dataset(owner_id=owner_id, artifact_id=artifact.id, name=name, method=method, row_count=len(frame), fraud_count=int(frame.is_fraud.sum()), config=clean(config), status="completed")
    db.add(dataset)
    db.flush()
    return dataset


def write_bundle(db, settings, owner_id, bundle, name):
    return write_bytes(db, settings.artifact_root, owner_id, name, pickle.dumps(bundle, protocol=5), "application/octet-stream", ".pkl")


def read_bundle(db, settings, artifact_id):
    # Only internally produced, database-referenced, checksummed artifacts may load.
    # There is no upload endpoint and no user-controlled pickle path.
    artifact = db.get(Artifact, artifact_id)
    if not artifact or not artifact.storage_key.endswith(".pkl") or not inspect_artifact(settings.artifact_root, artifact)["valid"]:
        raise ValueError("Model artifact integrity check failed")
    return pickle.loads(safe_path(settings.artifact_root, artifact.storage_key).read_bytes())
