from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.src.routers.auth import router as auth_router
from api.src.routers.content import router as content_router
from api.src.routers.findings import router as findings_router
from api.src.routers.governance import router as governance_router
from api.src.routers.insights import router as insights_router
from api.src.routers.revisions import router as revisions_router
from api.src.routers.sources import router as sources_router

app = FastAPI(
    title="Axiom BrandLedger API",
    description="Multimodal Brand Compliance & Verification Engine API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(sources_router)
app.include_router(content_router)
app.include_router(revisions_router)
app.include_router(findings_router)
app.include_router(governance_router)
app.include_router(insights_router)


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "axiom-api"}
