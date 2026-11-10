from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.src.routers.auth import router as auth_router
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


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "axiom-api"}

