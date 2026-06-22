"""Q&A prompt templates — follow-up questions on completed analysis jobs."""

from __future__ import annotations

import json
from typing import Any, Dict

QA_INSTRUCTIONS = """
You are the AlphaLens Q&A agent. Answer follow-up questions about a completed
portfolio analysis using ONLY the job context provided in the task.

Rules:
- Ground every answer in the recommendation and ranking data supplied
- If the context does not contain enough information, say so
- Do not invent holdings, scores, or prices
- Keep answers concise and actionable
"""


def create_qa_task(question: str, job_context: Dict[str, Any]) -> str:
    return f"""
User question:
{question}

Completed analysis job context:
{json.dumps(job_context, indent=2)[:12000]}

Answer the question using only this context.
""".strip()
