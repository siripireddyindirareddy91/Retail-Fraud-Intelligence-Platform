"""Measure downloaded Linux wheels without installing or executing their code.

Run from the checkout root:
  backend/.venv/Scripts/python.exe backend/scripts/audit_bundle.py --prepare
  backend/.venv/Scripts/python.exe -m pip download --dest runtime/qa/bundle-audit/final-linux-wheels --only-binary=:all: --platform manylinux_2_28_x86_64 --platform manylinux_2_24_x86_64 --platform manylinux2014_x86_64 --platform manylinux_2_17_x86_64 --python-version 3.12 --implementation cp --abi cp312 --abi abi3 --abi none -r runtime/qa/bundle-audit/api-requirements.txt
  backend/.venv/Scripts/python.exe backend/scripts/audit_bundle.py

The result is a component estimate, never a claim about a built Vercel Function.
"""
import argparse
from email.parser import BytesParser
import hashlib
import json
import marshal
from pathlib import Path
import tomllib
import zipfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--wheels", type=Path)
    args = parser.parse_args()
    backend = Path(__file__).resolve().parents[1]
    root = backend.parent
    output = root / "runtime" / "qa" / "bundle-audit"
    output.mkdir(parents=True, exist_ok=True)
    manifest = tomllib.loads((backend / "pyproject.toml").read_text())
    if args.prepare:
        (output / "api-requirements.txt").write_text("\n".join(manifest["project"]["dependencies"]) + "\n")
        print("Prepared API-only dependency download list")
        return
    directory = args.wheels or output / "final-linux-wheels"
    wheels = sorted(directory.glob("*.whl"))
    if not wheels:
        raise SystemExit("No wheels found; prepare and download the complete API dependency graph first")
    rows, lock = [], []
    runtime_package = None
    for wheel in wheels:
        total = bytecode = 0
        with zipfile.ZipFile(wheel) as archive:
            metadata = next(name for name in archive.namelist() if name.endswith(".dist-info/METADATA"))
            fields = BytesParser().parsebytes(archive.read(metadata))
            if fields["Name"].lower().replace("_", "-") == "vercel-runtime":
                runtime_package = fields["Version"]
            lock.append(f"{fields['Name']}=={fields['Version']}")
            for item in archive.infolist():
                total += item.file_size
                if item.filename.endswith(".py"):
                    try:
                        code = compile(archive.read(item), "/var/task/" + item.filename, "exec", dont_inherit=True)
                        bytecode += 16 + len(marshal.dumps(code))
                    except (SyntaxError, UnicodeError):
                        # Some packages ship intentionally invalid syntax fixtures;
                        # their original bytes are still counted in full.
                        pass
        with wheel.open("rb") as stream:
            checksum = hashlib.file_digest(stream, "sha256").hexdigest()
        rows.append({"wheel": wheel.name, "sha256": checksum, "uncompressed_bytes": total, "additional_pyc_bytes": bytecode})
    source = [path for path in backend.iterdir() if path.is_file() and not path.name.startswith(".env") and path.suffix not in (".db", ".log")]
    for directory in (backend / "app", backend / "alembic"):
        source.extend(path for path in directory.rglob("*") if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc")
    source_bytes = sum(path.stat().st_size for path in source)
    source_pyc = sum(16 + len(marshal.dumps(compile(path.read_bytes(), "/var/task/" + path.relative_to(backend).as_posix(), "exec", dont_inherit=True))) for path in source if path.suffix == ".py")
    dependency_bytes = sum(row["uncompressed_bytes"] for row in rows)
    pyc_bytes = sum(row["additional_pyc_bytes"] for row in rows) + source_pyc
    report = {"target": "Linux x86_64 CPython 3.12 wheels, downloaded on Windows", "wheel_count": len(rows), "dependency_bytes": dependency_bytes, "application_source_bytes": source_bytes, "additional_pyc_bytes": pyc_bytes, "estimated_component_bytes": dependency_bytes + source_bytes + pyc_bytes, "vercel_runtime_package_included": runtime_package, "vercel_runtime_overhead": "published runtime wheel counted when present; remaining platform wrapper overhead not measured", "actual_vercel_bundle_verified": False, "wheels": rows}
    (output / "final-size-report.json").write_text(json.dumps(report, indent=2) + "\n")
    (output / "measured-api-lock.txt").write_text("\n".join(sorted(lock, key=str.lower)) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key != "wheels"}, indent=2))
    print("Largest dependencies (decimal MB):")
    for row in sorted(rows, key=lambda row: -row["uncompressed_bytes"])[:8]:
        print(f"{row['uncompressed_bytes'] / 1e6:.2f} {row['wheel']}")


if __name__ == "__main__":
    main()
