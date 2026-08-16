from __future__ import annotations

from fastapi import APIRouter

from .original_lab_routes import router as original_lab_router
from .research_routes_base import router as research_base_router

# Preserve the complete v1.0 research suite byte-for-byte in research_routes_base,
# then mount the recovered deep Original-Language Lab ahead of it. Main imports this
# single router exactly as before.
router = APIRouter()
router.include_router(original_lab_router)
router.include_router(research_base_router)
