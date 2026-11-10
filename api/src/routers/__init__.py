from api.src.routers.auth import router as auth_router
from api.src.routers.content import router as content_router
from api.src.routers.findings import router as findings_router
from api.src.routers.revisions import router as revisions_router
from api.src.routers.sources import router as sources_router

__all__ = [
    "auth_router",
    "sources_router",
    "content_router",
    "revisions_router",
    "findings_router",
]
