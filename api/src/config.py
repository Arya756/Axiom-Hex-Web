import os
from pydantic import BaseModel, Field


class Settings(BaseModel):
    DATABASE_URL: str = Field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://axiom_app:axiom_secret@localhost:5432/axiom",
        )
    )
    ADMIN_DATABASE_URL: str = Field(
        default_factory=lambda: os.getenv(
            "ADMIN_DATABASE_URL",
            "postgresql+psycopg://postgres:postgres@localhost:5432/axiom",
        )
    )
    JWT_SECRET: str = Field(
        default_factory=lambda: os.getenv(
            "JWT_SECRET", "meridian-flow-axiom-secret-key-change-in-prod"
        )
    )
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day

    S3_ENDPOINT: str = Field(default_factory=lambda: os.getenv("S3_ENDPOINT", "http://localhost:9000"))
    S3_ACCESS_KEY: str = Field(default_factory=lambda: os.getenv("S3_ACCESS_KEY", "minioadmin"))
    S3_SECRET_KEY: str = Field(default_factory=lambda: os.getenv("S3_SECRET_KEY", "minioadmin"))

    DEFAULT_TENANT_ID: str = "tenant_meridian"


settings = Settings()
