# Master Viva Defense & Live Demonstration Guide

**Project:** Agentic AI Integrated Enterprise Automation and Decision Support System
**Repository:** [https://github.com/Devashree-b-s/agentic-ai-enterprise-automation](https://github.com/Devashree-b-s/agentic-ai-enterprise-automation)
**Target Audience:** Academic Examiners, Project Evaluators, Defense Panelists, and Candidates
**Date:** November 2026
**Document Version:** 1.0 (Production Release)

---

## Table of Contents
- [1. Viva Defense Quick Reference Sheet](#1-viva-defense-quick-reference-sheet)
- [2. Top 25+ Viva Examination Questions & In-Depth Technical Answers](#2-top-25-viva-examination-questions--in-depth-technical-answers)
  - [Category A: Multi-Agent Systems & LangGraph Orchestration](#category-a-multi-agent-systems--langgraph-orchestration)
  - [Category B: Retrieval-Augmented Generation (RAG) & Vector Intelligence](#category-b-retrieval-augmented-generation-rag--vector-intelligence)
  - [Category C: Human-in-the-Loop (HITL) & Governance](#category-c-human-in-the-loop-hitl--governance)
  - [Category D: Predictive Analytics & Time-Series Mathematical Modeling](#category-d-predictive-analytics--time-series-mathematical-modeling)
  - [Category E: Security, Cryptography, and RBAC](#category-e-security-cryptography-and-rbac)
  - [Category F: Software Engineering, Database Integrity, and Testing](#category-f-software-engineering-database-integrity-and-testing)
- [3. Key Architectural Trade-Offs & Defensive "Why" Questions](#3-key-architectural-trade-offs--defensive-why-questions)
- [4. Step-by-Step Live Demonstration Script](#4-step-by-step-live-demonstration-script)
  - [Phase 1: Admin Persona (System Oversight & Cross-Department Query)](#phase-1-admin-persona-system-oversight--cross-department-query)
  - [Phase 2: Manager Persona (Approvals & Predictive Decision Support)](#phase-2-manager-persona-approvals--predictive-decision-support)
  - [Phase 3: HR Specialist Persona (Employee Lifecycle & Leave Balances)](#phase-3-hr-specialist-persona-employee-lifecycle--leave-balances)
  - [Phase 4: Employee Persona (Self-Service RAG & RBAC Boundary Enforcement)](#phase-4-employee-persona-self-service-rag--rbac-boundary-enforcement)
- [5. Examiner Trap Questions & Defensive Strategies](#5-examiner-trap-questions--defensive-strategies)
- [6. Candidate Rapid-Lookup Codebase Map](#6-candidate-rapid-lookup-codebase-map)

---

## 1. Viva Defense Quick Reference Sheet

| Metric / Dimension | Verified System Value / Implementation |
| :--- | :--- |
| **Project Title** | Agentic AI Integrated Enterprise Automation and Decision Support System |
| **Core Architecture** | Multi-Tier Enterprise SPA + Fast-API Backend + LangGraph Multi-Agent Orchestrator + ChromaDB Vector Store |
| **LLM Inference Engines** | Groq Cloud API (`qwen/qwen3.8-27b`) with automatic fallback to Google GenAI (`gemini-1.5-flash`) |
| **Agent Topology** | Hierarchical Supervisor (`SupervisorAgent`) delegating to 5 Specialized Domain Agents (`HR`, `Sales`, `Inventory`, `Analytics`, `Documents`) |
| **Tool Inventory** | **23 Deterministic Tools** (5 HR, 4 Sales, 4 Inventory, 3 Analytics, 1 RAG, 3 Forecast, 3 HITL) calling compiled Python services |
| **Database & Concurrency** | Separate operational `enterprise.db` and optional historical `historical.db`; SQLite WAL, independent Alembic/provenance, read-only historical runtime |
| **RAG Pipeline** | Recursive character chunking (500 tokens, 50-token overlap), ChromaDB cosine distance similarity, magic header validation |
| **Predictive Analytics** | Chronological 4-month train vs 2-month test split, 4 competing models (Naive, SMA-3, OLS, Holt's), lowest RMSE selection |
| **HITL Governance** | Two-phase commit approval engine: Requisitions > $5,000 or by non-executives trigger pending review state |
| **Authentication & RBAC** | Argon2id password hashing (`time_cost=3`, `memory_cost=65536`), PyJWT HS256 tokens, 4 application roles |
| **Test Suite Coverage** | Current checkout: **192 passed** from both supported directories; deterministic agent fakes, no provider calls; 8 Phase 1 database foundation tests pass |
| **API Surface** | **62 unique router method/route pairs across 57 API paths and 10 mounted routers**, plus root and health |

---

## 2. Top 25+ Viva Examination Questions & In-Depth Technical Answers

### Category A: Multi-Agent Systems & LangGraph Orchestration

#### Q1: Why did you choose LangGraph instead of traditional frameworks like AutoGen or CrewAI?
> **Model Answer:**
> AutoGen and CrewAI primarily rely on free-form autonomous agent-to-agent chatter. In an enterprise ERP environment handling sensitive HR, financial, and inventory data, unconstrained multi-agent conversation introduces non-deterministic execution paths, infinite looping risks, and high token costs.
> We selected **LangGraph** because it models agent orchestration as a **Stateful Directed Acyclic Graph (DAG)**. LangGraph provides explicit, compiled state transitions (`AgentState`), deterministic checkpointing, and absolute control over workflow flow (`START` -> `SupervisorNode` -> `SpecializedAgentNode` -> `SynthesizerNode` -> `END`). This allows us to guarantee that sub-agents cannot bypass supervisor authorization or call arbitrary unauthorized tools.

#### Q2: How does the SupervisorAgent decompose complex, cross-departmental queries?
> **Model Answer:**
> In `backend/app/agents/supervisor.py`, when a user enters a complex prompt such as *"Which departments have high leave rates and how does our current sales revenue compare to our inventory reorder risk?"*, the query is processed by the `SupervisorAgent`.
> 1. The Supervisor analyzes the query intent using the configured LLM guided by `SUPERVISOR_SYSTEM_PROMPT`.
> 2. It outputs a structured `SupervisorDecision` schema containing a list of `PlannedTool` objects mapped to specific departments:
>    - `hr` -> `get_department_leave_summary`
>    - `sales` -> `get_sales_performance_metrics`
>    - `analytics` -> `get_inventory_shortage_risks`
> 3. The `MultiAgentCoordinator` (`backend/app/agents/coordinator.py`) receives these planned tools, deduplicates them, and groups them by specialized agent.

#### Q3: How do you prevent multi-agent deadlocks and handle worker thread failures?
> **Model Answer:**
> The `MultiAgentCoordinator` enforces **bounded failure containment**:
> 1. Planned tools for distinct agents are dispatched concurrently using Python's `concurrent.futures.ThreadPoolExecutor(max_workers=min(4, len(tasks_by_agent)))`.
> 2. Each worker thread runs inside an isolated execution context with a **thread-local database session** (`SessionLocal()`), preventing SQLite cross-thread connection sharing.
> 3. Execution is bounded by `AGENT_TIMEOUT_SECONDS = 60` via `as_completed(futures, timeout=...)`.
> 4. If a specialized agent encounters an unhandled exception or API timeout, the coordinator catches the error, marks that specific agent's `AgentExecutionResult.success = False`, and preserves the results of all successful peer agents.
> 5. The supervisor receives the partial results and synthesizes a response containing the available data while reporting a clean notification for the failed subtask, preventing entire system crashes.

#### Q4: What happens if the external LLM API (Groq/Gemini) goes completely offline?
> **Model Answer:**
> The system implements a two-tier resilience architecture:
> 1. **Model Fallback:** In `backend/app/agents/llm.py`, the primary provider is Groq (`qwen/qwen3.8-27b`). If Groq throws an HTTP 500, network timeout, or rate-limit exception, the LLM factory automatically catches the failure and falls back to Google GenAI (`gemini-1.5-flash`).
> 2. **Deterministic Regex & Heuristic Routing Fallback:** If both LLMs are unreachable, `fallback_route_query()` in `backend/app/agents/supervisor.py` activates. It uses deterministic keyword matching and context-aware conversation history to route known operational queries (e.g., *"show low stock"*, *"predict sales"*, *"my leave balance"*) directly to the correct tools without requiring any LLM call.
> 3. **Rule-Based Synthesis:** If the synthesizer LLM fails, `_deterministic_synthesis()` formats the raw JSON dictionary results into human-readable markdown tables.

#### Q5: How is conversation context maintained across multi-turn user dialogues?
> **Model Answer:**
> Conversation state is persisted in the database via the `Conversation` and `ConversationMessage` SQLAlchemy models (`backend/app/models/conversation.py`).
> In `backend/app/agents/supervisor.py`, `_resolve_context_references()` checks the last 5 messages from the database session. If the user submits a follow-up query containing anaphoric pronouns or elliptical phrases (e.g., *"What about Engineering?"* or *"How much do they cost?"*), the supervisor resolves the antecedent from prior user/assistant turns (e.g., blending *"Engineering"* with the previous query about *"headcount"* to form *"Engineering employee headcount"*), ensuring seamless conversational continuity.

---

### Category B: Retrieval-Augmented Generation (RAG) & Vector Intelligence

#### Q6: Explain the end-to-end RAG ingestion and retrieval architecture in your system.
> **Model Answer:**
> The RAG pipeline is implemented across `document_parser.py`, `chroma_service.py`, and `rag_synthesizer.py`:
> 1. **Ingestion & Validation:** When an authorized user uploads a file (`/api/documents/upload`), the system performs binary magic-header verification (checking `%PDF-` for PDFs and `PK\x03\x04` for DOCX) rather than trusting MIME extensions alone.
> 2. **Text Extraction & Chunking:** `DocumentParser` extracts raw text and applies recursive sliding-window chunking: 500-token chunks with a 50-token overlap to preserve contextual continuity across chunk boundaries.
> 3. **Embedding & Storage:** Chunks are stored in ChromaDB's persistent vector collection (`enterprise_knowledge`). ChromaDB computes vector embeddings using its default `all-MiniLM-L6-v2` dense embedding model.
> 4. **Retrieval & Metadata Filtering:** On query (`search_knowledge_base`), ChromaDB conducts cosine similarity retrieval. Metadata filters (such as department access or visibility scope) are applied directly at the vector query level.
> 5. **Grounded Synthesis:** The top-$k$ retrieved chunks ($k=4$) are injected into the LLM prompt with strict citation instructions, forcing the model to cite document title and chunk ID, eliminating ungrounded hallucinations.

#### Q7: Why did you implement binary magic-byte validation instead of standard file-extension checks?
> **Model Answer:**
> File extensions can be trivially spoofed by malicious actors (e.g., renaming an executable shell script or malicious payload to `policy.pdf`). By verifying the binary header bytes in `document_parser.py`:
> - PDF files must strictly begin with `b"%PDF-"`.
> - DOCX files (ZIP archives) must strictly begin with `b"PK\x03\x04"`.
> If the binary signature does not match the declared extension, the backend immediately rejects the upload with an HTTP 400 Bad Request before parsing, mitigating remote code execution (RCE) and format-confusion vulnerabilities.

#### Q8: Does your RAG system support scanned image-only PDFs?
> **Model Answer:**
> No. We intentionally disclosed this limitation in our architectural documentation. The system uses `pypdf` for programmatic text stream extraction. It does not package an optical character recognition (OCR) engine like Tesseract or Google Cloud Vision. If a user uploads a flattened, scanned image-only PDF without an embedded text layer, `pypdf` extracts zero tokens, and the upload is rejected with a message notifying the user that the document contains no extractable text.

#### Q9: How do you enforce Role-Based Access Control inside the vector database?
> **Model Answer:**
> In ChromaDB, each document chunk is stored with structured metadata: `{"department": doc.department, "uploader_id": user.id, "created_at": iso_str, "doc_id": doc.id}`.
> When the `DocumentAgent` or `search_knowledge_base` tool is invoked, the executing user's role is inspected:
> - If the user is an `Employee`, query filtering restricts results to company-wide public documents or documents tagged with the employee's specific department.
> - `HR` personnel can access HR-tagged policy documents.
> - `Admin` and `Manager` roles have unrestricted cross-departmental vector retrieval.
> This ensures that lower-privileged roles cannot access confidential executive or financial documents through conversational semantic search.

---

### Category C: Human-in-the-Loop (HITL) & Governance

#### Q10: What is the Human-in-the-Loop (HITL) pattern and why is it necessary in this enterprise system?
> **Model Answer:**
> Autonomous agents must never have unchecked authority to commit irreversible real-world actions, such as ordering thousands of dollars of inventory or altering employee payroll records.
> Our system implements a **Two-Phase Commit HITL workflow**:
> - **Phase 1 (Preparation & Proposing):** When the AI agent determines that stock is depleted, it cannot directly modify inventory stock. Instead, it calls `prepare_purchase_requisition()`, which validates stock parameters and creates an `ApprovalRequest` record in `PENDING` status with an autogenerated reference code (e.g., `REQ-20261103-XXXX`).
> - **Phase 2 (Human Evaluation & Execution):** A human executive (Admin or Manager) reviews the requisition via `/api/approvals`, inspects the financial impact, and explicitly calls `/api/approvals/{id}/review` with an `APPROVED` or `REJECTED` decision. Only upon explicit human approval is the operational state committed to the database.

#### Q11: What specific business thresholds trigger mandatory human approval?
> **Model Answer:**
> In `backend/app/services/approval_service.py`:
> 1. **Financial Value Threshold:** Any purchase order where $\text{total\_cost} = (\text{quantity} \times \text{unit\_cost}) > \$5,000$ strictly mandates human approval.
> 2. **Role Authorization Threshold:** Any purchase order initiated by a user with a non-executive role (`Employee` or `HR`) is forced into `PENDING` review, regardless of monetary amount.
> 3. **Leave Requests:** All employee leave submissions require approval by an `HR` specialist or `Manager` before the employee's remaining leave balance is decremented.

#### Q12: How is the approval audit trail maintained for compliance?
> **Model Answer:**
> The system maintains an append-only audit ledger in the `ApprovalAudit` database table (`backend/app/models/approval.py`). Whenever an approval state changes:
> - The reviewer's user ID, IP address, and timestamp are captured.
> - The previous state and new state are logged (`PENDING` -> `APPROVED` -> `EXECUTED`).
> - The reviewer's mandatory justification notes are stored.
> - Pre-change and post-change entity snapshots are preserved in JSON.
> This table is append-only and cannot be updated or deleted via standard API endpoints, satisfying corporate audit and regulatory compliance standards.

---

### Category D: Predictive Analytics & Time-Series Mathematical Modeling

#### Q13: Explain the 4 time-series forecasting models implemented in your system.
> **Model Answer:**
> In `backend/app/services/prediction_service.py`, four competing statistical models forecast monthly sales revenue:
> 1. **Naive Baseline:** Assumes future revenue equals the most recently observed month:
>    $$\hat{y}_{t+h} = y_t$$
> 2. **3-Month Simple Moving Average (SMA-3):** Averages the three preceding monthly observations:
>    $$\hat{y}_{t+h} = \frac{1}{3} \sum_{i=0}^{2} y_{t-i}$$
> 3. **Ordinary Least Squares (OLS) Linear Trend:** Fits a first-order regression trendline over time indices $t$:
>    $$\hat{y}_t = \beta_0 + \beta_1 t$$
> 4. **Holt's Linear Exponential Smoothing:** Decomposes the series into time-varying level ($\ell_t$) and trend ($b_t$) components using smoothing hyperparameters $\alpha = 0.8$ and $\beta = 0.2$:
>    $$\ell_t = \alpha y_t + (1-\alpha)(\ell_{t-1} + b_{t-1})$$
>    $$b_t = \beta(\ell_t - \ell_{t-1}) + (1-\beta)b_{t-1}$$
>    $$\hat{y}_{t+h} = \ell_t + h \cdot b_t$$

#### Q14: How does the system avoid data leakage when evaluating forecasting models?
> **Model Answer:**
> We use a **chronological out-of-sample evaluation split**. The historical dataset consists of 6 consecutive monthly periods (`2026-05` to `2026-10`):
> - **Training Set:** The initial 4 months (`2026-05` through `2026-08`).
> - **Held-Out Test Set:** The final 2 months (`2026-09` through `2026-10`).
> All 4 models are trained solely on the 4-month training set and evaluated on the 2-month test set using Root Mean Squared Error (RMSE):
> $$\text{RMSE} = \sqrt{\frac{1}{n} \sum_{i=1}^n (y_i - \hat{y}_i)^2}$$
> The model achieving the minimum test RMSE is chosen as the winner. The winning model is then refit on the complete 6-month historical dataset to generate out-of-sample forecasts for the next 3 forward months (`2026-11`, `2026-12`, `2027-01`).

#### Q15: How are inventory replenishment risk scores and safety stock calculated?
> **Model Answer:**
> In `backend/app/services/prediction_service.py` (`assess_sku_shortage_risks`), each SKU's operational risk is deterministically evaluated:
> 1. **Daily Demand Velocity:**
>    $$\bar{d} = \frac{\text{Units Sold in Lookback Period}}{\text{Lookback Days (e.g., 90)}}$$
> 2. **Lead-Time Demand (LTD):**
>    $$\text{LTD} = \bar{d} \times L \quad (\text{where } L \text{ is supplier lead time in days})$$
> 3. **Runout Time:**
>    $$T_{\text{runout}} = \frac{Q_{\text{on\_hand}}}{\bar{d}}$$
> 4. **Risk Categorization:**
>    - **CRITICAL:** $Q_{\text{on\_hand}} \le \text{Reorder Point}$ OR $T_{\text{runout}} \le L$. (Immediate stockout imminent).
>    - **MODERATE:** $Q_{\text{on\_hand}} \le 1.5 \times \text{Reorder Point}$.
>    - **LOW / SAFE:** Stock comfortably exceeds lead-time replenishment demands.

---

### Category E: Security, Cryptography, and RBAC

#### Q16: Why did you implement Argon2id instead of bcrypt or PBKDF2?
> **Model Answer:**
> - **bcrypt** is CPU-hard but has a maximum password length limit of 72 bytes and is susceptible to high-speed hardware attacks using Application-Specific Integrated Circuits (ASICs) and GPUs because it requires very little RAM.
> - **PBKDF2** is vulnerable to GPU-based parallel brute-force attacks due to its negligible memory consumption.
> - **Argon2id** (the winner of the Password Hashing Competition) combines data-independent and data-dependent memory access. It is both **CPU-hard and memory-hard**. In `backend/app/core/security.py`, we configure Argon2id with:
>   - `time_cost = 3` iterations
>   - `memory_cost = 65,536` KiB (64 MB of RAM per hash)
>   - `parallelism = 4` parallel lanes
> This makes brute-force attacks on GPUs/ASICs economically infeasible while requiring negligible overhead on our server during legitimate user authentication.

#### Q17: What is the difference between an Application Role and an Employee Job Title in your architecture?
> **Model Answer:**
> This is a crucial security distinction implemented in our database schema:
> - **Application Role (`User.role`):** A strictly bounded enum (`admin`, `manager`, `hr`, `employee`) embedded directly into the signed JWT token claims. It is inspected by FastAPI's `require_role()` dependency to grant or block HTTP endpoint access.
> - **Job Title / Designation (`Employee.job_title`):** An arbitrary organizational label stored in the HR table (e.g., *"Lead Systems Architect"*, *"Sales Executive"*, *"HR Generalist"*).
> Separating these ensures that an employee with an impressive organizational title (e.g., *"Executive Vice President"*) is not automatically granted system administrator privileges unless their account is explicitly provisioned with the `admin` application role.

#### Q18: How does the system defend against Prompt Injection and Unauthorized Data Access?
> **Model Answer:**
> 1. **Zero Raw SQL Execution from LLMs:** The system does not allow Text-to-SQL generation. The LLM cannot emit raw SQL strings; it can only request execution of predefined Python tools with strongly typed Pydantic parameters.
> 2. **Role-Enforced Tool Execution:** In `MultiAgentCoordinator`, even if a prompt injection attempts to trick the LLM into invoking an administrative tool (e.g., `create_employee_record`), the coordinator verifies `current_user.role`. If the user is an `Employee`, the tool execution is intercepted and rejected with an HTTP 403 authorization error.
> 3. **Input Sanitization:** User prompts are passed as standard text variables to LangChain `HumanMessage` objects, preventing prompt template escape sequences.

---

### Category F: Software Engineering, Database Integrity, and Testing

#### Q19: Why is SQLite in WAL mode suitable for this project, and how do you migrate to PostgreSQL for enterprise production?
> **Model Answer:**
> Standard SQLite locks the entire database file during writes, creating bottlenecks in multi-agent environments. In `backend/app/db/session.py`, we execute:
> ```python
> cursor.execute("PRAGMA journal_mode=WAL;")
> cursor.execute("PRAGMA synchronous=NORMAL;")
> cursor.execute("PRAGMA foreign_keys=ON;")
> ```
> **Write-Ahead Logging (WAL)** allows multiple concurrent readers while a writer commits to a separate WAL log, providing high concurrency on local deployments.
> **Production Migration:** Because our backend utilizes **SQLAlchemy 2.0 ORM** with Alembic migrations and standard SQL types, transitioning to PostgreSQL requires altering exactly **one line** in `.env`:
> ```bash
> DATABASE_URL=postgresql+psycopg://user:password@db-host:5432/enterprise_db
> ```
> No application models or service queries need to be rewritten.

#### Q20: What is your automated test coverage and how did you verify system reliability?
> **Model Answer:**
> The current checkout collects **192 unit and integration tests** in `backend/tests/`:
> - Both full-suite runs completed **192 passed** with external provider calls disabled. The compound multi-agent test injects deterministic routing and synthesis fakes.
> - All **8 Phase 1 database foundation tests** passed independently.
> - Phase 0 recorded 183 passing V1 tests, while the current checkout contains 184 pre-existing tests. This one-test count difference remains unresolved.
> - Test coverage spans:
>   1. `test_auth.py`: JWT token generation, expiration, invalid signatures, Argon2id verification.
>   2. `test_hr_services.py`: Employee CRUD, leave balance decrement logic, leave policy limits.
>   3. `test_sales_services.py`: Order status workflows, customer validation, revenue aggregation.
>   4. `test_inventory_services.py`: Stock movements, atomic inventory increments/decrements.
>   5. `test_multi_agent.py`: LangGraph graph compilation, coordinator concurrency, tool deduplication.
>   6. `test_predictions.py`: 4 time-series models, RMSE calculation, lead-time safety stock formulas.
>   7. `test_approvals.py`: Two-phase commit, threshold validation, audit log persistence.
> - On the frontend, **Oxlint** validates 0 linter errors, and `tsc -b && vite build` verifies type-safety in 2.50s.

---

## 3. Key Architectural Trade-Offs & Defensive "Why" Questions

```mermaid
flowchart TD
    subgraph ArchitectureDecisions["Core Architectural Decisions & Defensive Rationales"]
        D1["LangGraph vs AutoGen/CrewAI<br/><b>Chosen: LangGraph</b><br/>Deterministic DAG state transitions, cycle prevention, checkpointing."]
        D2["Argon2id vs bcrypt/PBKDF2<br/><b>Chosen: Argon2id</b><br/>Memory-hard & CPU-hard; immune to GPU/ASIC parallel brute force."]
        D3["Deterministic Tools vs Text-to-SQL<br/><b>Chosen: Python Tools</b><br/>Zero arithmetic hallucination, zero SQL injection, strict ORM isolation."]
        D4["ChromaDB vs pgvector/Pinecone<br/><b>Chosen: ChromaDB</b><br/>Zero cloud dependency, local persistence, instant developer onboarding."]
        D5["Chronological Split vs K-Fold Cross-Validation<br/><b>Chosen: Chronological (4+2 Split)</b><br/>Prevents lookahead data leakage in temporal sales forecasting."]
    end
```

| Decision / Trade-Off | Alternative Rejected | Why the Chosen Approach is Superior for Enterprise |
| :--- | :--- | :--- |
| **Deterministic Tools vs. Text-to-SQL** | Direct Text-to-SQL | LLM-generated SQL allows catastrophic arithmetic errors, prompt injection, and accidental table truncation (`DROP TABLE`). Deterministic Python services guarantee 100% mathematical precision and transaction isolation. |
| **RAG vs. LLM Fine-Tuning** | Model Fine-Tuning | Fine-tuning costs thousands of dollars, takes days to update, and causes hallucinations of obsolete data. RAG allows real-time document upload, instant deletion, zero retraining cost, and verifiable source citations. |
| **Single-Tenant vs. Multi-Tenant Schema** | Multi-Tenant Architecture | The project scope is an internal enterprise operating system for a single corporation. Introducing multi-tenant partitioning schemas would add unnecessary complexity without providing business value for an on-premises enterprise deployment. |
| **Zustand vs. Redux Toolkit** | Redux Toolkit | Zustand provides lightweight, boilerplate-free state management (less than 2 KB) with simple React hook integration, avoiding Redux's excessive reducer and action boilerplate. |
| **Tailwind CSS v4 vs. Component Libraries** | Material UI / Ant Design | Tailwind v4 compiles via a high-performance Rust-based engine, allowing bespoke enterprise dashboard theming, lightning-fast rendering, and zero CSS runtime overhead. |

---

## 4. Step-by-Step Live Demonstration Script

Follow this exact sequence during the live presentation. Ensure the backend (`http://127.0.0.1:8000`) and frontend (`http://127.0.0.1:5173`) are running.

### Phase 1: Admin Persona (System Oversight & Cross-Department Query)
1. **Login:** Navigate to `http://127.0.0.1:5173/login`. Log in with `admin@enterprise.local` / `Admin@123`.
2. **Dashboard Overview:**
   - Point out the cross-department KPI cards: Active Headcount, Monthly Revenue, Low Stock SKUs, Pending Approvals.
   - Show the dynamic Role Badge (`ADMIN`) in the top navigation bar.
3. **Conversational Multi-Agent Query:**
   - Click **AI Assistant** in the sidebar.
   - Enter query: *"Give me an executive summary of our inventory status, top selling products, and pending leave requests."*
   - **Explain to Examiner:** Observe how the **LangGraph Supervisor** activates 3 specialized agents (`inventory`, `sales`, `hr`) concurrently via the `MultiAgentCoordinator`, collates the tool outputs, and renders a unified markdown summary with exact metrics.
4. **User Management & Security:**
   - Click **Admin Panel** (`/admin`).
   - Demonstrate user listing, role assignment, and audit log inspection. Show that only the `Admin` persona can view this tab.

---

### Phase 2: Manager Persona (Approvals & Predictive Decision Support)
1. **Switch Role:** Log out and log in as `manager@enterprise.local` / `Manager@123`.
2. **Predictive Analytics & Forecasting:**
   - Click **Predictions** (`/predictions`).
   - Point out the **3-Month Sales Revenue Forecast** chart (`2026-11`, `2026-12`, `2027-01`).
   - **Explain to Examiner:** Show the model comparison table. Point out that the system trained 4 models on May-Aug 2026, evaluated them on Sep-Oct 2026, and automatically selected the model with the lowest out-of-sample RMSE.
   - Point out the **SKU Stockout Risk Assessment** table. Show SKUs highlighted as `CRITICAL` due to lead-time runout risk.
3. **Human-in-the-Loop Requisition & Approval:**
   - Switch to **AI Assistant**.
   - Enter prompt: *"Prepare purchase requisition for SKU-GFT-030 with quantity 20 units."*
   - Observe that the agent generates a pending requisition code: `REQ-20261103-XXXX`.
   - Navigate to **Approvals** (`/approvals`).
   - Locate the pending requisition. Click **Review Requisition**.
   - Enter review notes: *"Approved based on projected Q4 holiday demand surge."*
   - Click **Approve**. Show that the status transitions to `APPROVED` and `EXECUTED`, creating an immutable `ApprovalAudit` record.

---

### Phase 3: HR Specialist Persona (Employee Lifecycle & Leave Balances)
1. **Switch Role:** Log out and log in as `hr@enterprise.local` / `Hr@123`.
2. **HR Operations Dashboard:**
   - Click **HR Operations** (`/hr`).
   - Demonstrate the Department Headcount distribution, employee directory, and leave balance summary.
3. **Leave Processing:**
   - Show the **Pending Leave Requests** table.
   - Select an employee's pending Annual Leave request.
   - Approve the request. Show that the employee's `remaining_days` balance immediately decrements by the requested duration.
4. **RBAC Boundary Check:**
   - Try navigating directly to `http://127.0.0.1:5173/admin` or `http://127.0.0.1:5173/approvals`.
   - **Explain to Examiner:** Notice the `ProtectedRoute` intercepts the unauthorized route and redirects to `/unauthorized` or hides the menu item. HR cannot approve commercial purchase orders.

---

### Phase 4: Employee Persona (Self-Service RAG & RBAC Boundary Enforcement)
1. **Switch Role:** Log out and log in as `employee@enterprise.local` / `Employee@123`.
2. **Personal Dashboard:**
   - Point out that the navigation sidebar is strictly reduced to **Overview**, **Documents (Knowledge Base)**, and **AI Assistant**.
   - The user cannot see financial revenue figures, organizational salaries, or other employees' private records.
3. **RAG Knowledge Base Semantic Search:**
   - Navigate to **Documents** (`/documents`).
   - Show the uploaded enterprise policy documents (e.g., *Employee Code of Conduct*, *Leave Policy 2026*).
   - Switch to **AI Assistant**.
   - Ask: *"What is the policy regarding sick leave notice and medical certificates?"*
   - **Explain to Examiner:** Observe that the `DocumentAgent` performs a cosine-similarity vector retrieval in ChromaDB, retrieves the exact paragraph from *Leave Policy 2026*, and returns the answer with a grounded citation: `[Source: Leave_Policy_2026.pdf (Chunk 2)]`.
4. **Self-Service Leave Application:**
   - Submit a leave request for 2 days of Casual Leave.
   - Confirm that the status is set to `PENDING` awaiting HR review.

---

## 5. Examiner Trap Questions & Defensive Strategies

### Trap 1: *"Can an employee prompt the AI to approve their own leave or alter their salary?"*
> **Defense:**
> *"No, sir/ma'am. The AI has zero direct write access to the database. All state modifications must pass through compiled Python service methods. When a tool is invoked, the `MultiAgentCoordinator` extracts the authenticated user ID and role directly from the cryptographically signed JWT token—not from the LLM prompt. If an employee prompts 'Approve my leave' or 'Update my salary', the HR tool checks `current_user.role`. Since the role is `employee`, the service throws an `AccessDeniedException` and blocks the transaction before any database write occurs."*

### Trap 2: *"Why didn't you use Deep Learning (LSTM / Transformer / Prophet) for sales forecasting?"*
> **Defense:**
> *"Deep Learning models like LSTMs or Temporal Fusion Transformers require tens of thousands of sequential data points to avoid severe overfitting. In our enterprise deployment, we have 6 months of historical monthly aggregated sales data. Fitting a complex neural network on 6 observations would lead to extreme parameter overparameterization and spurious correlations. Classical statistical methods (Holt's Linear Exponential Smoothing, OLS, and Moving Averages) are mathematically optimal and robust for small-sample macroeconomic time series."*

### Trap 3: *"What prevents an attacker from stealing a JWT token and staying logged in forever?"*
> **Defense:**
> *"Our JWT tokens are strictly time-bounded using the `exp` standard claim configured to expire in 30 minutes (`ACCESS_TOKEN_EXPIRE_MINUTES = 30`). Tokens are signed using HMAC-SHA256 with a cryptographically random 256-bit secret key. The token payload contains no sensitive credentials or passwords. Once expired, the frontend Axios interceptor automatically detects the HTTP 401 response, purges the local session store, and redirects the client to the login screen."*

### Trap 4: *"What happens if the ChromaDB vector database returns irrelevant chunks (hallucination risk)?"*
> **Defense:**
> *"We implement a similarity score threshold and explicit grounding constraints in `rag_synthesizer.py`. If the cosine distance of retrieved chunks exceeds our relevance cutoff, the chunks are discarded. Furthermore, the synthesizer system prompt instructs the LLM: 'You must answer the question solely based on the provided context. If the answer cannot be found in the context, explicitly state that the knowledge base does not contain this information.' The LLM is prohibited from using external parametric memory for company policy questions."*

---

## 6. Candidate Rapid-Lookup Codebase Map

Use this cheat sheet to instantly navigate files during the viva if an examiner asks: *"Show me where this is implemented in code."*

| Feature / Logic | Exact File Path | Key Functions / Classes |
| :--- | :--- | :--- |
| **LangGraph Supervisor** | `backend/app/agents/supervisor.py` | `SupervisorAgent`, `create_supervisor_graph()`, `fallback_route_query()` |
| **Concurrent Coordinator** | `backend/app/agents/coordinator.py` | `MultiAgentCoordinator`, `coordinate_execution()`, `_execute_agent_worker()` |
| **LLM Provider Factory** | `backend/app/agents/llm.py` | `get_chat_model()`, `_build_groq_model()`, `_build_gemini_model()` |
| **Agent State Schema** | `backend/app/agents/state.py` | `AgentState`, `PlannedTool`, `SupervisorDecision` |
| **23 Business Tools** | `backend/app/agents/tools/*.py` | HR (5), Sales (4), Inventory (4), Analytics (3), RAG (1), Forecast (3), HITL (3) |
| **Vector DB (ChromaDB)** | `backend/app/services/chroma_service.py` | `ChromaService`, `query_similar_chunks()`, `index_document()` |
| **Magic Header Parser** | `backend/app/services/document_parser.py` | `DocumentParser`, `validate_file_magic()`, `chunk_text()` |
| **HITL Approvals Engine** | `backend/app/services/approval_service.py` | `create_requisition()`, `review_approval()`, `execute_approved_action()` |
| **Predictive Forecasting** | `backend/app/services/prediction_service.py` | `generate_sales_forecast()`, `assess_sku_shortage_risks()`, `_evaluate_models()` |
| **Argon2id & JWT Security**| `backend/app/core/security.py` | `verify_password()`, `get_password_hash()`, `create_access_token()` |
| **RBAC Route Guard** | `backend/app/api/deps.py` | `get_current_user()`, `require_role()` |
| **Frontend Route Guard** | `frontend/src/components/auth/ProtectedRoute.tsx` | `ProtectedRoute` |
| **Frontend Auth Store** | `frontend/src/store/auth.store.ts` | `useAuthStore` (Zustand state & token storage) |
| **Database Migrations** | `backend/alembic/versions/*.py` | Alembic migration scripts |
| **Unit & E2E Tests** | `backend/tests/` | 192 collected, including 8 Phase 1 database foundation tests |

---
*End of Master Viva Defense & Live Demonstration Guide.*
