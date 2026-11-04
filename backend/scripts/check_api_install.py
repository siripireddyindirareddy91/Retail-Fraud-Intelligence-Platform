"""Reject accidental research dependencies; never print environment values."""
import hashlib
from importlib.metadata import distributions
from pathlib import Path
import sys

FORBIDDEN = {"numpy", "pandas", "scipy", "scikit-learn", "joblib", "xgboost", "xgboost-cpu", "fastparquet", "shap", "sdv", "torch", "mlflow", "mlflow-skinny", "matplotlib", "pyarrow", "reportlab", "triton"}


def main():
    installed = {item.metadata["Name"].lower().replace("_", "-") for item in distributions() if item.metadata["Name"]}
    found = sorted(name for name in installed if name in FORBIDDEN or name.startswith("nvidia-"))
    if found:
        raise SystemExit("API install contains forbidden research distributions: " + ", ".join(found))
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    from app.main import create_app
    assert callable(create_app)
    assert not any(name in sys.modules for name in ("numpy", "pandas", "scipy", "sklearn", "joblib", "xgboost", "torch", "sdv", "shap", "mlflow", "pyarrow", "matplotlib", "reportlab"))
    digest = hashlib.sha256((root / "uv.lock").read_bytes()).hexdigest()
    print(f"API_INSTALL_PROFILE=web; research_packages=0; lock_sha256={digest}")


if __name__ == "__main__":
    main()
