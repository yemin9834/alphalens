"""Clerk JWT authentication — optional when CLERK_JWKS_URL is unset (local demo)."""

from __future__ import annotations

import logging
import os

from fastapi import Depends
from fastapi_clerk_auth import ClerkConfig, ClerkHTTPBearer, HTTPAuthorizationCredentials

logger = logging.getLogger(__name__)

CLERK_JWKS_URL = os.getenv("CLERK_JWKS_URL", "").strip()
CLERK_ENABLED = bool(CLERK_JWKS_URL)
DEMO_USER_ID = os.getenv("DEMO_USER_ID", "demo-user")

if CLERK_ENABLED:
    _clerk_guard = ClerkHTTPBearer(ClerkConfig(jwks_url=CLERK_JWKS_URL))

    async def get_current_user_id(
        creds: HTTPAuthorizationCredentials = Depends(_clerk_guard),
    ) -> str:
        user_id = creds.decoded["sub"]
        logger.info("Authenticated user: %s", user_id)
        return user_id

else:

    async def get_current_user_id() -> str:
        return DEMO_USER_ID
