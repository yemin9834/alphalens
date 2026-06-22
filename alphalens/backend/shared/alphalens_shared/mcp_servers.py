"""
MCP server factories for AlphaLens agents (Guide 4 live discovery).

Lazy-imports openai-agents MCP — not used in slim Lambda packages.
"""

from __future__ import annotations

import glob
import json
import logging
import os
import shutil
import threading
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, List

logger = logging.getLogger(__name__)

MCP_LOGGING_ENABLED = os.getenv("MCP_LOGGING", "false").lower() == "true"

PLAYWRIGHT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
)
PLAYWRIGHT_BROWSER_GLOB = "/ms-playwright/chromium-*/chrome-linux*/chrome"
PLAYWRIGHT_BROWSER_FALLBACK = "/ms-playwright/chromium-1208/chrome-linux64/chrome"
STDERR_MAX_LENGTH = 4000


def _trim_for_log(value: Any, max_length: int = STDERR_MAX_LENGTH) -> str:
    text = str(value)
    if len(text) <= max_length:
        return text
    return f"{text[:max_length]}... [trimmed {len(text) - max_length} chars]"


def _require_mcp_packages() -> None:
    try:
        import agents.mcp  # noqa: F401
        import mcp  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "MCP mode requires openai-agents with MCP support. "
            "In backend/discovery run: uv sync --group llm"
        ) from exc


def _logging_mcp_stdio_class():
    from agents.mcp import MCPServerStdio
    from mcp.client.stdio import stdio_client

    class LoggingMCPServerStdio(MCPServerStdio):
        @asynccontextmanager
        async def create_streams(self):
            read_fd, write_fd = os.pipe()
            stderr_reader = os.fdopen(read_fd, "r", encoding="utf-8", errors="replace")
            stderr_writer = os.fdopen(write_fd, "w", encoding="utf-8", errors="replace")

            def drain_stderr() -> None:
                try:
                    for line in stderr_reader:
                        message = line.rstrip()
                        if message:
                            logger.error("[mcp:stderr] %s", _trim_for_log(message))
                except Exception:
                    logger.exception("Failed to read MCP subprocess stderr")
                finally:
                    stderr_reader.close()

            stderr_thread = threading.Thread(
                target=drain_stderr,
                name="mcp-stderr",
                daemon=True,
            )
            stderr_thread.start()

            try:
                async with stdio_client(self.params, errlog=stderr_writer) as streams:
                    yield streams
            finally:
                stderr_writer.close()
                stderr_thread.join(timeout=1)

    return LoggingMCPServerStdio


def _make_mcp_stdio(params: dict, timeout_seconds: int):
    _require_mcp_packages()
    from agents.mcp import MCPServerStdio

    if MCP_LOGGING_ENABLED:
        return _logging_mcp_stdio_class()(params=params, client_session_timeout_seconds=timeout_seconds)
    return MCPServerStdio(params=params, client_session_timeout_seconds=timeout_seconds)


def create_playwright_mcp_server(timeout_seconds: int = 120):
    """
    Playwright MCP for browsing company sites and supply-chain pages.

    Local dev: npx @playwright/mcp (requires Node.js).
    Docker/App Runner: playwright-mcp with bundled Chromium (Alex pattern).
    """
    custom_command = os.getenv("PLAYWRIGHT_MCP_COMMAND")
    if custom_command:
        parts = custom_command.split()
        params = {"command": parts[0], "args": parts[1:]}
        logger.info("Using PLAYWRIGHT_MCP_COMMAND: %s", custom_command)
        return _make_mcp_stdio(params, timeout_seconds)

    if shutil.which("playwright-mcp"):
        args = [
            "--headless",
            "--isolated",
            "--no-sandbox",
            "--ignore-https-errors",
            "--user-agent",
            PLAYWRIGHT_USER_AGENT,
        ]
        chrome_paths = glob.glob(PLAYWRIGHT_BROWSER_GLOB)
        if chrome_paths:
            args.extend(["--executable-path", chrome_paths[0]])
        elif os.path.isfile(PLAYWRIGHT_BROWSER_FALLBACK):
            args.extend(["--executable-path", PLAYWRIGHT_BROWSER_FALLBACK])

        config_path = "/tmp/playwright-mcp.config.json"
        with open(config_path, "w", encoding="utf-8") as config_file:
            json.dump(
                {
                    "browser": {
                        "launchOptions": {
                            "args": ["--single-process", "--no-zygote", "--disable-gpu"]
                        }
                    }
                },
                config_file,
            )
        args.extend(["--config", config_path])
        params = {
            "command": "playwright-mcp",
            "args": args,
            "env": {"DEBUG": os.getenv("PLAYWRIGHT_DEBUG", "")},
        }
        return _make_mcp_stdio(params, timeout_seconds)

    # Default: npx @playwright/mcp (works on student Mac/Windows/Linux with Node)
    params = {
        "command": "npx",
        "args": [
            "-y",
            "@playwright/mcp@latest",
            "--headless",
            "--isolated",
            "--user-agent",
            PLAYWRIGHT_USER_AGENT,
        ],
    }
    logger.info("Using npx @playwright/mcp for local Playwright MCP")
    return _make_mcp_stdio(params, timeout_seconds)


def create_brave_search_mcp_server(timeout_seconds: int = 60):
    """Brave Search MCP — requires BRAVE_API_KEY in environment."""
    api_key = os.getenv("BRAVE_API_KEY", "").strip()
    if not api_key:
        raise ValueError("BRAVE_API_KEY is required for Brave Search MCP")

    params = {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-brave-search"],
        "env": {"BRAVE_API_KEY": api_key},
    }
    return _make_mcp_stdio(params, timeout_seconds)


def discovery_mcp_enabled() -> bool:
    """True when at least one MCP server can be started for discovery."""
    if os.getenv("DISCOVERY_PLAYWRIGHT_MCP", "true").lower() == "true":
        return shutil.which("npx") is not None or shutil.which("playwright-mcp") is not None
    if os.getenv("BRAVE_API_KEY", "").strip():
        return shutil.which("npx") is not None
    return False


@asynccontextmanager
async def discovery_mcp_stack(timeout_seconds: int = 120) -> AsyncIterator[List[Any]]:
    """
    Enter all configured discovery MCP servers (Playwright + optional Brave).

    Set DISCOVERY_PLAYWRIGHT_MCP=false to skip browser MCP.
    Set BRAVE_API_KEY for search MCP.
    """
    from contextlib import AsyncExitStack

    servers: List[Any] = []
    async with AsyncExitStack() as stack:
        if os.getenv("DISCOVERY_PLAYWRIGHT_MCP", "true").lower() == "true":
            pw = await stack.enter_async_context(
                create_playwright_mcp_server(timeout_seconds=timeout_seconds)
            )
            servers.append(pw)
            logger.info("Playwright MCP server ready")

        if os.getenv("BRAVE_API_KEY", "").strip():
            brave = await stack.enter_async_context(
                create_brave_search_mcp_server(timeout_seconds=min(timeout_seconds, 90))
            )
            servers.append(brave)
            logger.info("Brave Search MCP server ready")

        if not servers:
            raise RuntimeError(
                "No discovery MCP servers started. Enable DISCOVERY_PLAYWRIGHT_MCP "
                "and/or set BRAVE_API_KEY (requires npx)."
            )

        yield servers


@asynccontextmanager
async def brave_search_mcp_stack(timeout_seconds: int = 90) -> AsyncIterator[List[Any]]:
    """Brave Search MCP only — lighter stack for Phase 2 news research."""
    from contextlib import AsyncExitStack

    api_key = os.getenv("BRAVE_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("BRAVE_API_KEY is required for news research MCP")

    async with AsyncExitStack() as stack:
        brave = await stack.enter_async_context(
            create_brave_search_mcp_server(timeout_seconds=timeout_seconds)
        )
        logger.info("Brave Search MCP ready (news research)")
        yield [brave]
