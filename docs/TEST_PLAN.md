# Test Plan & Verification Strategy

## 1. Objectives
Ensure all business calculations, authentication flows, database migrations, API contracts, and agentic workflows are systematically validated with automated tests.

---

## 2. Testing Levels

### Level 1: Unit Testing (Pytest)
- **Domain Services:** Verify deterministic calculations (e.g., revenue formulas, stock thresholds, leave deduction rules).
- **Core Security:** Verify Argon2 password hashing, salt verification, and JWT token issuance/expiration.
- **Pydantic Validation:** Test schemas against valid and invalid payloads.

### Level 2: Database & Model Testing
- Test database session creation and teardown.
- Validate foreign key constraints, unique constraints, and cascades.
- Validate Alembic schema migrations forward and rollback.

### Level 3: Integration & API Testing (HTTPX & FastAPI TestClient)
- Test HTTP status codes (200, 201, 400, 401, 403, 404, 422).
- Test JWT protected endpoints with valid, expired, and missing tokens.
- Test Role-Based Access Control (RBAC): Ensure an HR user cannot modify Inventory or Sales data.

### Level 4: Agent & Workflow Testing
- Test deterministic tool execution independently of LLM calls.
- Test LangGraph state transitions and conditional routing.
- Test human-in-the-loop interruption triggers for high-risk actions.

### Level 5: Frontend Testing (Phase 11+)
- Vitest and React Testing Library for UI components and API client integration.

---

## 3. Test Running Standard
All backend tests will reside under `backend/tests/` and run using:
```bash
pytest backend/tests/ -v
```
No feature will be marked complete until its test suite passes with zero errors.
