"""Main application entry point for Agentic AI Enterprise Decision Support System."""

from fastapi import FastAPI

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
)


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
