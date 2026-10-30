# Enterprise System Architecture

## 1. Overview
The **Agentic AI Integrated Enterprise and Decision Support System** is a modular enterprise solution designed to integrate three major operational departments:
- **HR Management:** Employees, roles, attendance, and leave management.
- **Sales Management:** Orders, customers, transactions, and revenue tracking.
- **Inventory Management:** Stock levels, low-stock detection, and reordering workflows.

The system allows business executives to query organizational data via natural language, orchestrated through specialized AI agents and verified by deterministic business calculations.

---

## 2. Directory Layout
```text
Agentic-AI-Enterprise/
│
├── backend/
│   ├── app/
│   │   ├── api/          # HTTP route endpoints (FastAPI routers)
│   │   ├── agents/       # AI agents, LangGraph orchestration, tool definitions
│   │   ├── services/     # Pure deterministic business logic and analytics
│   │   ├── models/       # SQLAlchemy ORM database models
│   │   ├── schemas/      # Pydantic validation schemas (request/response)
│   │   ├── core/         # Security, JWT, Argon2 hashing, and configuration
│   │   ├── db/           # Database engine, session management, and Base model
│   │   └── main.py       # FastAPI application entry point
│   │
│   ├── tests/            # Automated test suite (pytest)
│   ├── alembic/          # Database migration scripts
│   ├── alembic.ini       # Alembic migration configuration
│   ├── requirements.txt  # Pinned backend dependencies
│   └── .env.example      # Environment variables template
│
├── frontend/             # Single-page application (React + TypeScript + Vite)
│   ├── public/
│   ├── src/
│   │   ├── assets/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── hooks/
│   │   ├── services/
│   │   ├── store/
│   │   ├── types/
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   └── vite.config.ts
│
├── data/                 # Local data storage, SQLite database, uploads, and ChromaDB
│
├── docs/                 # System architecture and test plan documentation
│   ├── ARCHITECTURE.md
│   └── TEST_PLAN.md
│
├── .gitignore            # Git exclusion rules
└── README.md             # Project documentation and quickstart
```

---

## 3. Layer Responsibilities & Strict Rules

1. **API Layer (`backend/app/api/`):**
   - Handles incoming HTTP requests and generates HTTP responses.
   - Responsible for route registration, parameter extraction, and status codes.
   - Does **not** perform direct SQL queries or calculations.

2. **Schemas Layer (`backend/app/schemas/`):**
   - Built with **Pydantic**.
   - Validates incoming request payloads and serializes outgoing JSON responses.
   - Completely separate from database models to prevent leaking internal database schemas.

3. **Models Layer (`backend/app/models/`):**
   - Built with **SQLAlchemy 2.0 ORM**.
   - Defines database tables, column types, constraints, and relationships.

4. **Database Configuration (`backend/app/db/`):**
   - Defines the SQLAlchemy engine, session maker, and dependency injection (`get_db`).

5. **Services Layer (`backend/app/services/`):**
   - Contains deterministic business logic (e.g., revenue summation, leave balance checks, stock deduction).
   - Keeps business rules isolated from API controllers for easy testability.

6. **Core Layer (`backend/app/core/`):**
   - Central application settings (`config.py` using `pydantic-settings`).
   - Security primitives: password hashing (Argon2), JWT token creation, and RBAC utilities.

7. **Agents Layer (`backend/app/agents/`):**
   - LangGraph multi-agent workflows.
   - LLMs act as reasoners that invoke deterministic Python tools in `services/`.
   - Never bypasses authorization or performs destructive actions without human approval.
