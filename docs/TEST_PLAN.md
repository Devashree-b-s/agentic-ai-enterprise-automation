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

### Level 6: Dataset Ingestion Foundation
- Use only small synthetic CSV and XLSX fixtures; never use downloaded benchmark
  datasets in routine tests.
- Cover required headers, worksheet selection, data types, malformed rows,
  configured business-key duplicates, SHA-256 provenance, completed-batch
  idempotency, failed-batch retry, transaction rollback, bounded rejection
  reporting, batch status transitions, explicit target isolation, path/size and
  file-format checks, HMAC hooks, and chunked processing.
- Create isolated SQLite target tables and provenance registries per test. Do not
  initialize either project database or invoke application startup for ingestion
  unit tests.

---

## 3. Test Running Standard
All backend tests reside under `backend/tests/`. Run them from both supported
working directories with disposable database and Chroma locations; do not point
test runs at `data/enterprise.db`, `data/historical.db`, or the persistent Chroma
store. On Windows PowerShell, set the three paths to a unique temporary directory
before each run:

```powershell
$projectRoot = (Resolve-Path ".").Path
$projectDrive = [System.IO.Path]::GetPathRoot($projectRoot)
$testRoot = Join-Path $projectDrive "agentic-tests-<unique-id>"
New-Item -ItemType Directory -Path $testRoot | Out-Null
$env:TEMP = $testRoot
$env:TMP = $testRoot
$env:HOME = $testRoot
$env:USERPROFILE = $testRoot
$env:PYTHONDONTWRITEBYTECODE = "1"
$env:PYTHONPATH = Join-Path $projectRoot "backend"
$env:PYTEST_ADDOPTS = ""
$env:DATABASE_URL = "sqlite:///$($testRoot.Replace('\','/'))/enterprise.db"
$env:HISTORICAL_DATABASE_URL = "sqlite:///$($testRoot.Replace('\','/'))/historical.db"
$env:CHROMA_PERSIST_DIR = Join-Path $testRoot "chroma"
$env:LLM_PROVIDER = "invalid-test-provider"
$env:GROQ_API_KEY = ""
$env:GEMINI_API_KEY = ""

# Initialize the disposable worker database before multi-agent tests.
Set-Location (Join-Path $projectRoot "backend")
..\.venv\Scripts\python.exe -B -m alembic upgrade head

# From backend
..\.venv\Scripts\python.exe -B -m pytest --rootdir="$projectRoot" --confcutdir="$(Join-Path $projectRoot 'backend\tests')" tests -v

# From the project root; use a fresh, separate testRoot and DB first.
Set-Location $projectRoot
.\.venv\Scripts\python.exe -B -m pytest backend\tests -v

# After both commands complete
Remove-Item -LiteralPath $testRoot -Recurse -Force
```

The current checkout collects 214 tests, including 8 Phase 1 database foundation
tests and 22 Phase 2 ingestion tests (one symlink test may be skipped when Windows
does not permit symlink creation). The compound multi-agent test injects
deterministic routing and synthesis fakes; keep provider calls disabled for
automated test runs. Each full suite uses a migrated disposable operational
database because concurrent agent workers create their own SQLAlchemy sessions
against `DATABASE_URL`.
