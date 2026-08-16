from __future__ import annotations

from fastapi import APIRouter

from .atlas_routes import router as atlas_router
from .original_lab_routes import router as original_lab_router
from .research_pro_routes import router as research_pro_router
from .research_routes_base import router as research_base_router

# Mount data-heavy workspaces ahead of compatibility routes. The base router still
# serves the stable legacy endpoints used elsewhere in the application.
router = APIRouter()
router.include_router(atlas_router)
router.include_router(original_lab_router)
router.include_router(research_pro_router)
router.include_router(research_base_router)
