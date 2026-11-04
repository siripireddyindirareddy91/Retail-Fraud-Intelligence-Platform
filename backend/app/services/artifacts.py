import hashlib
import json
import os
from pathlib import Path

from ..core.errors import APIError
from ..models import Artifact, uid


def safe_path(root: Path, key: str):
    root = root.resolve()
    path = (root / key).resolve()
    if root not in path.parents:
        raise APIError(400, "invalid_storage_path", "The artifact path is invalid.")
    return path


def write_json(db, root: Path, owner_id: str, name: str, content: dict):
    payload = json.dumps(content, sort_keys=True, indent=2, allow_nan=False).encode()
    return write_bytes(db, root, owner_id, name, payload, "application/json", ".json")


def write_bytes(db, root: Path, owner_id: str, name: str, payload: bytes, content_type: str, extension: str):
    artifact_id = uid()
    key = f"{owner_id}/{artifact_id}{extension}"
    path = safe_path(root, key)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Generated keys are unique; exclusive creation prevents artifact replacement.
    with path.open("xb") as output:
        output.write(payload)
        output.flush()
        os.fsync(output.fileno())
    artifact = Artifact(id=artifact_id, owner_id=owner_id, storage_key=key, name=name, content_type=content_type, size_bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest())
    db.add(artifact)
    db.flush()
    return artifact


def inspect_artifact(root, artifact):
    path = safe_path(root, artifact.storage_key)
    if not path.is_file():
        return {"id": artifact.id, "valid": False, "reason": "missing_file"}
    checksum = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(chunk)
            size += len(chunk)
    valid = checksum.hexdigest() == artifact.sha256 and size == artifact.size_bytes
    return {"id": artifact.id, "valid": valid, "reason": None if valid else "checksum_or_size_mismatch"}
