#!/usr/bin/env python3
"""
Package the Q&A Lambda using Docker (linux/amd64).

Alex planner pattern: openai-agents[litellm] in main dependencies,
uv export with minimal filtering, local workspace packages via --no-deps.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

LAMBDA_UNZIPPED_LIMIT_BYTES = 262_144_000

AGENT_FILES = (
    "lambda_handler.py",
    "agent.py",
    "templates.py",
    "server.py",
    "sse_stream.py",
    "run.sh",
)
LOCAL_PACKAGES = ("database", "shared")


def run_command(cmd: list[str], cwd: Path | None = None) -> str:
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        if result.stderr:
            print(result.stderr)
        if result.stdout:
            print(result.stdout)
        sys.exit(1)
    return result.stdout


def _unzipped_bytes(package_dir: Path) -> int:
    return sum(f.stat().st_size for f in package_dir.rglob("*") if f.is_file())


def _filter_requirements(text: str) -> list[str]:
    filtered: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("-e "):
            print(f"Excluding editable workspace path: {stripped}")
            continue
        if line.startswith("pyperclip"):
            print(f"Excluding from Lambda: {line}")
            continue
        filtered.append(line)
    return filtered


def package_lambda() -> Path:
    qa_dir = Path(__file__).parent.resolve()
    backend_dir = qa_dir.parent

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        package_dir = temp_path / "package"
        package_dir.mkdir()

        print("Creating Q&A Lambda package (Alex planner pattern)...")

        requirements_result = run_command(
            ["uv", "export", "--no-hashes", "--no-emit-project"],
            cwd=qa_dir,
        )
        req_file = temp_path / "requirements.txt"
        req_file.write_text("\n".join(_filter_requirements(requirements_result)))

        volume_args: list[str] = []
        pip_local = []
        for pkg in LOCAL_PACKAGES:
            volume_args.extend(["-v", f"{backend_dir / pkg}:/{pkg}"])
            pip_local.append(f"pip install --target ./package --no-deps /{pkg}")

        docker_cmd = [
            "docker",
            "run",
            "--rm",
            "--platform",
            "linux/amd64",
            "-v",
            f"{temp_path}:/build",
            *volume_args,
            "--entrypoint",
            "/bin/bash",
            "public.ecr.aws/lambda/python:3.12",
            "-c",
            (
                "cd /build && "
                "pip install --target ./package -r requirements.txt && "
                + " && ".join(pip_local)
                + " && mkdir -p ./package/data && cp -r /shared/data/* ./package/data/"
            ),
        ]

        run_command(docker_cmd)

        for filename in AGENT_FILES:
            dest = package_dir / filename
            shutil.copy(qa_dir / filename, dest)
            if filename == "run.sh":
                dest.chmod(0o755)

        missing = [
            name
            for name in ("litellm", "agents")
            if not (package_dir / name).is_dir()
        ]
        if missing:
            print(
                "ERROR: LLM package incomplete — missing: "
                + ", ".join(missing)
            )
            sys.exit(1)
        print("Verified: litellm/ and agents/ present in package")

        unzipped = _unzipped_bytes(package_dir)
        unzipped_mb = unzipped / (1024 * 1024)
        limit_mb = LAMBDA_UNZIPPED_LIMIT_BYTES / (1024 * 1024)
        print(f"Unzipped size: {unzipped_mb:.1f} MB (Lambda limit: {limit_mb:.0f} MB)")
        if unzipped > LAMBDA_UNZIPPED_LIMIT_BYTES:
            print("ERROR: Package exceeds Lambda unzipped size limit.")
            sys.exit(1)

        zip_path = qa_dir / "qa_lambda.zip"
        if zip_path.exists():
            zip_path.unlink()

        run_command(["zip", "-r", str(zip_path), "."], cwd=package_dir)
        size_mb = zip_path.stat().st_size / (1024 * 1024)
        print(f"Created {zip_path} ({size_mb:.1f} MB zipped)")
        return zip_path


def main() -> None:
    try:
        run_command(["docker", "--version"])
    except FileNotFoundError:
        print("Error: Docker is not installed or not in PATH")
        sys.exit(1)
    package_lambda()


if __name__ == "__main__":
    main()
