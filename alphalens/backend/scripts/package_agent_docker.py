#!/usr/bin/env python3
"""
Package an AlphaLens agent Lambda using Docker (linux/amd64).

Usage:
  uv run package_agent_docker.py orchestrator
  uv run package_agent_docker.py orchestrator --include-llm
  uv run package_agent_docker.py all --include-llm
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Never bundle MCP / web-server stacks in zip Lambda packages.
RUNTIME_EXCLUDE_PACKAGES = {
    "mcp",
    "fastapi",
    "uvicorn",
    "starlette",
    "sse-starlette",
    "httpx-sse",
    "typer",
    "rich",
    "pygments",
    "griffelib",
    "shellingham",
    "fastuuid",
    "pyperclip",
    "fastapi-clerk-auth",
    "mangum",
    "websockets",
    "python-multipart",
}

# Slim MVP packages also omit LLM stacks (default Guide 3 deploy).
SLIM_LLM_EXCLUDE_PACKAGES = {
    "openai",
    "openai-agents",
    "litellm",
    "tiktoken",
    "tokenizers",
    "huggingface-hub",
    "hf-xet",
    "aiohttp",
    "aiosignal",
    "frozenlist",
    "multidict",
    "yarl",
    "propcache",
    "aiohappyeyeballs",
    "tenacity",
    "anyio",
    "httpx",
    "httpcore",
    "h11",
    "sniffio",
    "jinja2",
    "markupsafe",
    "cryptography",
    "pyjwt",
    "pydantic-settings",
    "jsonschema",
    "jsonschema-specifications",
    "referencing",
    "rpds-py",
    "importlib-metadata",
    "zipp",
    "annotated-doc",
    "mdurl",
    "markdown-it-py",
    "jiter",
    "distro",
    "types-requests",
}

LLM_CAPABLE_AGENTS = frozenset({"orchestrator", "portfolio", "qa"})

# Slim zip agents: openai client for optional LLM narrative (no litellm).
SLIM_OPENAI_PACKAGES = frozenset(
    {
        "openai",
        "httpx",
        "httpcore",
        "anyio",
        "h11",
        "sniffio",
        "distro",
        "jiter",
        "certifi",
        "idna",
    }
)
ANALYST_SLIM_OPENAI_PACKAGES = SLIM_OPENAI_PACKAGES
VALIDATOR_SLIM_OPENAI_PACKAGES = SLIM_OPENAI_PACKAGES

# Alex bundles openai-agents in main deps (~72 MB planner zip). AlphaLens LLM zips must
# omit yfinance/pandas pulled in via alphalens-metrics — not used by LLM portfolio/qa/orchestrator paths.
LLM_EXPORT_EXCLUDE = {
    "yfinance",
    "pandas",
    "numpy",
    "peewee",
    "multitasking",
    "curl-cffi",
    "curl_cffi",
    "beautifulsoup4",
    "soupsieve",
    "protobuf",
    "platformdirs",
    "fsspec",
    "filelock",
    "hf-xet",
    "huggingface-hub",
    "tokenizers",
    "tiktoken",
}

# LLM orchestrator/qa invoke analyst Lambda — no yfinance metrics code needed in zip.
LLM_SKIP_LOCAL_PACKAGES: dict[str, frozenset[str]] = {
    "orchestrator": frozenset({"metrics"}),
    "qa": frozenset({"metrics"}),
}

# Lambda unzipped deployment limit (bytes)
LAMBDA_UNZIPPED_LIMIT_BYTES = 262_144_000

# Run inside the Docker build after pip install (--include-llm only).
# Must end with `true` — bare `find` exits 1 when nothing matches and breaks `&&` chains.
LLM_PACKAGE_PRUNE_CMD = (
    "set +e; cd /build/package && "
    "find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null; "
    "find . -type d -name 'tests' -exec rm -rf {} + 2>/dev/null; "
    "find . -type d -name 'test' -exec rm -rf {} + 2>/dev/null; "
    "rm -rf litellm/proxy litellm/benchmarking litellm/integrations litellm/experimental; "
    "if [ -d litellm/llms ]; then "
    "find litellm/llms -mindepth 1 -maxdepth 1 -type d "
    "! -name 'bedrock' ! -name 'openai' ! -name 'custom_llm' -exec rm -rf {} + 2>/dev/null; "
    "fi; "
    "rm -rf pandas numpy numpy.libs yfinance curl_cffi multitasking peewee; "
    "rm -rf mcp starlette uvicorn sse_starlette httpx_sse websockets python_multipart "
    "tokenizers huggingface_hub hf_xet beautifulsoup4 soupsieve; "
    "find . -name '*.pyc' -delete 2>/dev/null; "
    "true"
)


def _requirement_name(line: str) -> str | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or stripped.startswith("-e "):
        return None
    return stripped.split("==")[0].split("[")[0].strip().lower()


def exclude_packages(*, include_llm: bool) -> set[str]:
    excluded = set(RUNTIME_EXCLUDE_PACKAGES)
    if not include_llm:
        excluded |= SLIM_LLM_EXCLUDE_PACKAGES
    return excluded


def filter_requirements(
    text: str,
    *,
    include_llm: bool,
    agent_name: str | None = None,
) -> list[str]:
    excluded = exclude_packages(include_llm=include_llm)
    if include_llm:
        excluded |= LLM_EXPORT_EXCLUDE
    if agent_name in ("analyst", "validator", "portfolio") and not include_llm:
        excluded -= SLIM_OPENAI_PACKAGES
    filtered = []
    for line in text.splitlines():
        name = _requirement_name(line)
        if name and name in excluded:
            continue
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("-e "):
            continue
        if stripped.startswith("pyperclip"):
            continue
        filtered.append(line)
    return filtered


AGENT_CONFIG = {
    "orchestrator": {
        "files": ["lambda_handler.py", "pipeline_job.py", "job_stages.py", "agent.py", "templates.py"],
        "local_packages": ["database", "shared", "metrics"],
        "copy_shared_data": True,
    },
    "validator": {
        "files": ["lambda_handler.py", "agent.py", "templates.py"],
        "local_packages": ["shared"],
        "copy_shared_data": True,
    },
    "analyst": {
        "files": ["lambda_handler.py", "agent.py", "templates.py"],
        "local_packages": ["shared", "metrics"],
        "copy_shared_data": True,
    },
    "portfolio": {
        "files": ["lambda_handler.py", "agent.py", "templates.py"],
        "local_packages": ["shared", "metrics"],
        "copy_shared_data": True,
    },
    "discovery": {
        "files": ["lambda_handler.py", "agent.py", "templates.py"],
        "local_packages": ["shared"],
        "copy_shared_data": True,
    },
    "qa": {
        "files": ["lambda_handler.py", "agent.py", "templates.py"],
        "local_packages": ["database", "shared"],
        "copy_shared_data": True,
    },
}


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


def _unzipped_bytes(package_dir: Path) -> int:
    return sum(f.stat().st_size for f in package_dir.rglob("*") if f.is_file())


def package_agent(agent_name: str, *, include_llm: bool = False) -> Path:
    if agent_name not in AGENT_CONFIG:
        print(f"Unknown agent: {agent_name}. Choose from: {', '.join(AGENT_CONFIG)}")
        sys.exit(1)

    if include_llm and agent_name not in LLM_CAPABLE_AGENTS:
        print(
            f"Note: {agent_name} has no LLM mode — packaging slim zip "
            "(--include-llm applies to orchestrator, portfolio, qa only)."
        )
        include_llm = False

    config = AGENT_CONFIG[agent_name]
    backend_dir = Path(__file__).resolve().parent.parent
    agent_dir = backend_dir / agent_name

    if not agent_dir.is_dir():
        print(f"Agent directory not found: {agent_dir}")
        sys.exit(1)

    if include_llm:
        print(f"Packaging {agent_name} with LLM dependencies (openai-agents + litellm)...")

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        package_dir = temp_path / "package"
        package_dir.mkdir()

        export_cmd = ["uv", "export", "--no-hashes", "--no-emit-project"]
        if include_llm:
            export_cmd.extend(["--group", "llm"])
        requirements = run_command(export_cmd, cwd=agent_dir)
        filtered = filter_requirements(
            requirements, include_llm=include_llm, agent_name=agent_name
        )
        req_file = temp_path / "requirements.txt"
        req_file.write_text("\n".join(filtered))

        local_mounts = []
        pip_installs = ["pip install --target ./package -r requirements.txt"]
        skip_local = LLM_SKIP_LOCAL_PACKAGES.get(agent_name, frozenset()) if include_llm else frozenset()
        for pkg in config["local_packages"]:
            if pkg in skip_local:
                print(f"Skipping local package {pkg}/ for LLM zip (Alex-style slim bundle)")
                continue
            src = backend_dir / pkg
            local_mounts.extend(["-v", f"{src}:/{pkg}"])
            pip_installs.append(f"pip install --target ./package --no-deps /{pkg}")

        if config.get("copy_shared_data"):
            pip_installs.append("mkdir -p ./package/data && cp -r /shared/data/* ./package/data/")

        if include_llm:
            pip_installs.append(LLM_PACKAGE_PRUNE_CMD)

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
        if include_llm:
            print("Docker build + LLM prune completed.")
            missing = [
                name
                for name in ("litellm", "agents")
                if not (package_dir / name).is_dir()
            ]
            if missing:
                print(
                    "ERROR: LLM package is incomplete — missing: "
                    + ", ".join(missing)
                    + ". Re-run with --include-llm (Docker must finish without errors)."
                )
                sys.exit(1)
            print("Verified: litellm/ and agents/ present in package")

        for filename in config["files"]:
            shutil.copy(agent_dir / filename, package_dir / filename)

        if agent_name in ("analyst", "validator", "portfolio") and not include_llm:
            if not (package_dir / "openai").is_dir():
                print(
                    f"ERROR: {agent_name} package missing openai/ — required for "
                    f"USE_LLM_{agent_name.upper()}_NARRATIVE. Check SLIM_OPENAI_PACKAGES."
                )
                sys.exit(1)
            print(f"Verified: openai/ present in {agent_name} slim package")
        if agent_name == "validator" and not include_llm:
            if not (package_dir / "yfinance").is_dir():
                print(
                    "ERROR: validator package missing yfinance/ — required for market lookup."
                )
                sys.exit(1)
            print("Verified: yfinance/ present in validator slim package")

        zip_path = agent_dir / f"{agent_name}_lambda.zip"
        if zip_path.exists():
            zip_path.unlink()

        if include_llm:
            unzipped = _unzipped_bytes(package_dir)
            unzipped_mb = unzipped / (1024 * 1024)
            limit_mb = LAMBDA_UNZIPPED_LIMIT_BYTES / (1024 * 1024)
            print(f"Unzipped size: {unzipped_mb:.1f} MB (Lambda limit: {limit_mb:.0f} MB)")
            if unzipped > LAMBDA_UNZIPPED_LIMIT_BYTES:
                print(
                    "ERROR: Package exceeds Lambda unzipped size limit. "
                    "Use slim packages (no --include-llm) for zip Lambdas, or deploy LLM "
                    "agents as container images (see alphalens-discovery-live)."
                )
                sys.exit(1)

        run_command(["zip", "-r", str(zip_path), "."], cwd=package_dir)
        zipped_mb = zip_path.stat().st_size / (1024 * 1024)
        print(f"Created {zip_path} ({zipped_mb:.1f} MB zipped)")
        return zip_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Package AlphaLens agent for Lambda")
    parser.add_argument("agent", nargs="?", help="Agent name (or 'all')")
    parser.add_argument(
        "--include-llm",
        action="store_true",
        help="Bundle openai-agents + litellm for orchestrator, portfolio, or qa",
    )
    args = parser.parse_args()

    if not args.agent:
        parser.print_help()
        sys.exit(1)

    if args.agent == "all":
        for name in AGENT_CONFIG:
            use_llm = args.include_llm and name in LLM_CAPABLE_AGENTS
            package_agent(name, include_llm=use_llm)
    else:
        package_agent(args.agent, include_llm=args.include_llm)


if __name__ == "__main__":
    main()
