"""
Q&A agent — follow-up questions on completed analysis jobs.

MVP: deterministic answers via run().
Guide 4+: Bedrock Q&A via create_agent() + run_llm() (Alex reporter pattern, no tools).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, AsyncIterator, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

from dotenv import load_dotenv

from templates import QA_INSTRUCTIONS, create_qa_task

load_dotenv(override=True)

AGENT_NAME = "Q&A Specialist"
INSTRUCTIONS = QA_INSTRUCTIONS

USE_LLM_QA = os.getenv("USE_LLM_QA", "false").lower() == "true"


def run(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Answer a question — deterministic unless USE_LLM_QA=true."""
    from alphalens_shared.bedrock_agent import log_agent_mode

    log_agent_mode(AGENT_NAME, llm=USE_LLM_QA)
    if USE_LLM_QA:
        import asyncio

        return asyncio.run(run_llm(payload))
    from alphalens_shared.services.qa import run_qa

    return run_qa(payload)


def create_agent(
    question: str,
    job_context: Dict[str, Any],
) -> Tuple[Any, str]:
    """
    Create Bedrock Q&A agent (Alex reporter pattern without tools).

    Job context is embedded in the task — no tools needed.

    Returns:
        (model, task)
    """
    from alphalens_shared.bedrock_agent import get_litellm_model, require_llm_packages

    require_llm_packages()
    task = create_qa_task(question, job_context)
    model = get_litellm_model()
    return model, task


async def run_llm(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Run Bedrock Q&A agent."""
    from alphalens_shared.bedrock_agent import run_bedrock_agent

    job_id = payload.get("jobId") or payload.get("job_id")
    question = (payload.get("question") or "").strip()
    if not job_id or not question:
        return {"success": False, "error": "jobId and question are required"}

    job = _load_job(job_id, payload.get("clerk_user_id"))
    if not job:
        return {"success": False, "error": f"Job {job_id} not found"}
    if job.get("status") != "completed":
        return {
            "success": False,
            "error": f"Job status is {job.get('status')}; wait for analysis to complete",
        }

    from alphalens_shared.services.qa import _job_context

    job_context = _job_context(job)
    _, task = create_agent(question, job_context)

    answer = await run_bedrock_agent(
        name=AGENT_NAME,
        instructions=INSTRUCTIONS,
        task=task,
        max_turns=5,
    )

    return {
        "success": True,
        "jobId": job_id,
        "question": question,
        "answer": str(answer),
    }


async def stream_llm_tokens(payload: Dict[str, Any]) -> AsyncIterator[str]:
    """Stream Q&A answer tokens for SSE clients."""
    job_id = payload.get("jobId") or payload.get("job_id")
    question = (payload.get("question") or "").strip()
    clerk_user_id = payload.get("clerk_user_id")
    if not job_id or not question:
        yield "Error: jobId and question are required."
        return

    yield "Loading job context… "
    job = await asyncio.to_thread(_load_job, job_id, clerk_user_id)
    if not job:
        yield f"Error: Job {job_id} not found."
        return
    if job.get("status") != "completed":
        yield f"Error: Job status is {job.get('status')}; wait for analysis to complete."
        return

    from alphalens_shared.bedrock_agent import get_litellm_model_name, require_llm_packages
    from alphalens_shared.services.qa import _job_context

    require_llm_packages()
    import litellm

    job_context = _job_context(job)
    task = create_qa_task(question, job_context)
    messages = [
        {"role": "system", "content": QA_INSTRUCTIONS},
        {"role": "user", "content": task},
    ]

    model_name = get_litellm_model_name()
    logger.info(
        "Q&A LLM stream job=%s provider=%s model=%s",
        job_id,
        os.getenv("LLM_PROVIDER", "bedrock"),
        model_name,
    )
    yield "Generating answer… "

    response = await litellm.acompletion(
        model=model_name,
        messages=messages,
        stream=True,
    )
    async for chunk in response:
        delta = chunk.choices[0].delta.content or ""
        if delta:
            yield delta


def _load_job(job_id: str, clerk_user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    from alphalens_shared.services.qa import _load_job as load_job

    return load_job(job_id, clerk_user_id)


__all__ = [
    "AGENT_NAME",
    "INSTRUCTIONS",
    "create_agent",
    "run",
    "run_llm",
    "stream_llm_tokens",
]
