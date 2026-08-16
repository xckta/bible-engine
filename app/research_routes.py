from __future__ import annotations

from fastapi import APIRouter

from .asset_routes import router as asset_router
from .atlas_routes import router as atlas_router
from .original_lab_routes import router as original_lab_router
from .research_pro_routes import router as research_pro_router
from .research_routes_base import router as research_base_router

# Asset routes intentionally mount first so a browser always receives the current
# local build instead of a stale cached research bundle. Data-heavy workspaces mount
# ahead of the compatibility endpoints they extend.
router = APIRouter()
router.include_router(asset_router)
router.include_router(atlas_router)
router.include_router(original_lab_router)
router.include_router(research_pro_router)
router.include_router(research_base_router)
