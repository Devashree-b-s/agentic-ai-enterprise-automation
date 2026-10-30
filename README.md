# Agentic AI Integrated Enterprise and Decision Support System

An intelligent enterprise decision-support system integrating HR, Sales, and Inventory departments with deterministic business logic and specialized LangGraph AI agents.

---

## Architecture Overview
The project follows a clean, modular architecture:
- **Backend:** FastAPI, Pydantic v2, SQLAlchemy 2.0, SQLite, Alembic, JWT, Argon2.
- **Agentic AI:** LangGraph supervisor & specialized domain agents, tool calling, ChromaDB RAG.
- **Frontend (Phase 11+):** React, TypeScript, Vite, Tailwind CSS.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/TEST_PLAN.md](docs/TEST_PLAN.md) for complete details.

---

## Getting Started

### 1. Environment Setup
```powershell
# Create virtual environment
python -m venv .venv

# Activate on Windows PowerShell
.\.venv\Scripts\Activate.ps1

# Install initial dependencies
pip install -r backend/requirements.txt
```

### 2. Configuration
Copy the template environment variables:
```powershell
cp backend/.env.example backend/.env
```
