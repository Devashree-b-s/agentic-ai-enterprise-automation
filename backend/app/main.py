"""Main application entry point for Agentic AI Enterprise Decision Support System."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.api.hr import router as hr_router
from app.api.inventory import router as inventory_router
from app.api.sales import router as sales_router
from app.db.base import Base
from app.db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager to initialize resources on startup."""
    # Ensure database tables exist on startup in development
    Base.metadata.create_all(bind=engine)
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

# Register API routers
app.include_router(auth_router, prefix="/api/v1")
app.include_router(hr_router, prefix="/api/v1/hr")
app.include_router(inventory_router, prefix="/api/v1/inventory")
app.include_router(sales_router, prefix="/api/v1/sales")


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
