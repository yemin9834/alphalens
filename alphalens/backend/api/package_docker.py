#!/usr/bin/env python3
"""
Package the AlphaLens FastAPI API for Lambda (linux/amd64).

Usage (Docker Desktop must be running):
  cd alphalens/backend/api
  uv run package_docker.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def run_command(cmd: list[str], cwd: Path | None = None) -> str:
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr)
        sys.exit(1)
    return result.stdout


LOCAL_PACKAGE_NAMES = frozenset(
    {"alphalens-database", "alphalens-shared", "alphalens-metrics"}
)


def _filter_requirements(text: str) -> list[str]:
    """Drop workspace editable paths — local packages are installed via Docker mounts."""
    filtered: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("-e "):
            print(f"Excluding editable workspace path: {stripped}")
            continue
        lower = stripped.lower()
        if any(name in lower for name in LOCAL_PACKAGE_NAMES):
            print(f"Excluding local workspace package: {stripped}")
            continue
        if "./database" in stripped or "./shared" in stripped or "./metrics" in stripped:
            print(f"Excluding local path requirement: {stripped}")
            continue
        filtered.append(line)
    return filtered


def main() -> None:
    api_dir = Path(__file__).resolve().parent
    backend_dir = api_dir.parent

    try:
        run_command(["docker", "info"])
    except Exception:
        print("Error: Docker is not running. Start Docker Desktop and retry.")
        sys.exit(1)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        package_dir = temp_path / "package"
        package_dir.mkdir()

        requirements = run_command(
            [
                "uv",
                "export",
                "--no-hashes",
                "--no-emit-project",
                "--no-emit-local",
            ],
            cwd=api_dir,
        )
        req_file = temp_path / "requirements.txt"
        req_file.write_text("\n".join(_filter_requirements(requirements)))

        local_packages = ["database", "shared", "metrics"]
        local_mounts: list[str] = []
        pip_installs = ["pip install --target ./package -r requirements.txt"]
        for pkg in local_packages:
            src = backend_dir / pkg
            local_mounts.extend(["-v", f"{src}:/{pkg}"])
            pip_installs.append(f"pip install --target ./package --no-deps /{pkg}")

        pip_installs.append("mkdir -p ./package/data && cp -r /shared/data/* ./package/data/")

        docker_cmd = [
            "docker",
            "run",
            "--rm",
            "--platform",
            "linux/amd64",
            "-v",
            f"{temp_path}:/build",
            *local_mounts,
            "--entrypoint",
            "/bin/bash",
            "public.ecr.aws/lambda/python:3.12",
            "-c",
            "cd /build && " + " && ".join(pip_installs),
        ]
        run_command(docker_cmd)

        for filename in (
            "auth.py",
            "lambda_handler.py",
            "main.py",
            "discovery_stream.py",
            "pipeline_stream.py",
            "qa_stream.py",
            "rank_stream.py",
            "run.sh",
        ):
            dest = package_dir / filename
            shutil.copy(api_dir / filename, dest)
            if filename == "run.sh":
                dest.chmod(0o755)

        qa_templates = backend_dir / "qa" / "templates.py"
        shared_qa_prompts = backend_dir / "shared" / "alphalens_shared" / "prompts" / "qa.py"
        if not shared_qa_prompts.is_file():
            print(f"Error: {shared_qa_prompts} not found — Q&A streaming requires alphalens_shared.prompts.qa")
            sys.exit(1)
        if qa_templates.is_file():
            (package_dir / "qa").mkdir(exist_ok=True)
            shutil.copy(qa_templates, package_dir / "qa" / "templates.py")

        # `pip install --no-deps /database` already places `src/` on the Lambda path
        # (main.py imports `from src import Database`).

        zip_path = api_dir / "api_lambda.zip"
        if zip_path.exists():
            zip_path.unlink()

        run_command(["zip", "-r", str(zip_path), "."], cwd=package_dir)
        size_mb = zip_path.stat().st_size / (1024 * 1024)
        print(f"Created {zip_path} ({size_mb:.1f} MB)")

        import zipfile

        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
            if not any(n.endswith("alphalens_shared/prompts/qa.py") for n in names):
                print("Error: api_lambda.zip is missing alphalens_shared/prompts/qa.py")
                sys.exit(1)
            print("Verified alphalens_shared/prompts/qa.py in zip")


if __name__ == "__main__":
    main()
