from __future__ import annotations

from fastapi import APIRouter

from .atlas_routes import router as atlas_router
from .original_lab_routes import router as original_lab_router
from .research_routes_base import router as research_base_router

# Preserve the complete v1.0 research suite in research_routes_base while mounting
# richer additive workspaces ahead of the compatibility routes they supersede.
router=APIRouter()
router.include_router(atlas_router)
router.include_router(original_lab_router)
router.include_router(research_base_router)
