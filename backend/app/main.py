"""Main application entry point for Agentic AI Enterprise Decision Support System."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.agents import router as agents_router
from app.api.analytics import router as analytics_router
from app.api.approvals import router as approvals_router
from app.api.auth import router as auth_router
from app.api.conversations import router as conversations_router
from app.api.documents import router as documents_router
from app.api.hr import router as hr_router
from app.api.inventory import router as inventory_router
from app.api.predictions import router as predictions_router
from app.api.sales import router as sales_router
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager; schema changes are applied through Alembic."""
    yield


# Create the core FastAPI application instance
app = FastAPI(
    title="Agentic AI Integrated Enterprise and Decision Support System",
    description=(
        "Enterprise decision-support backend integrating HR, Sales, "
        "and Inventory management with deterministic analytics and AI agents."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[str(origin) for origin in settings.CORS_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger = logging.getLogger("app.main")


@app.exception_handler(Exception)
async def global_unhandled_exception_handler(request: Request, exc: Exception):
    """Global exception handler to prevent leaking raw tracebacks in production."""
    logger.exception(
        "Unhandled server exception on %s %s: %s", request.method, request.url.path, exc
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An internal server error occurred. Please contact the administrator."
        },
    )


# Register API routers
app.include_router(auth_router, prefix="/api/v1")
app.include_router(hr_router, prefix="/api/v1/hr")
app.include_router(inventory_router, prefix="/api/v1/inventory")
app.include_router(sales_router, prefix="/api/v1/sales")
app.include_router(analytics_router, prefix="/api/v1/analytics")
app.include_router(agents_router, prefix="/api/v1")
app.include_router(conversations_router, prefix="/api/v1")
app.include_router(approvals_router, prefix="/api/v1")
app.include_router(predictions_router, prefix="/api/v1")
app.include_router(documents_router, prefix="/api/v1")


@app.get("/", tags=["General"])
def read_root() -> dict[str, str]:
    """Root endpoint providing basic application metadata."""
    return {
        "message": "Welcome to the Agentic AI Integrated Enterprise and Decision Support System API",
        "status": "online",
        "version": "0.1.0",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
def health_check() -> dict[str, str]:
    """Health check endpoint to verify backend service availability."""
    return {
        "status": "healthy",
        "service": "enterprise-backend",
    }
