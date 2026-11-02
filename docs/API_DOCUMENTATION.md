# Enterprise REST API Specification & RBAC Matrix

**Project:** Agentic AI Based Intelligent Enterprise Automation and Decision Support System
**Repository:** [https://github.com/Devashree-b-s/agentic-ai-enterprise-automation](https://github.com/Devashree-b-s/agentic-ai-enterprise-automation)
**Document Path:** `docs/API_DOCUMENTATION.md`
**API Version:** `0.1.0`
**Base URL:** `http://127.0.0.1:8000/api/v1`
**Production Base URL:** `/api/v1`
**Date:** November 2026

---

## 1. Global API Standards & Authentication

### 1.1 Authentication Scheme
All endpoints (except `/api/v1/auth/login`, `/api/v1/auth/register`, `/health`, and `/`) require an HTTP Bearer JSON Web Token (JWT) passed in the `Authorization` header:

```http
Authorization: Bearer <jwt_access_token>
```

Tokens are issued via `POST /api/v1/auth/login`. The token payload encodes the subject (`sub` = email), application role (`role` = Admin, Manager, HR, or Employee), and token expiration timestamp (`exp`).

### 1.2 Global HTTP Status Codes
| Status Code | Description & Usage |
| :--- | :--- |
| **`200 OK`** | Request succeeded. Returns requested data payload. |
| **`201 Created`** | Resource successfully created (e.g. Employee, Order, Document, Conversation). |
| **`400 Bad Request`** | Semantic validation error (e.g., negative stock, invalid state transition). |
| **`401 Unauthorized`** | Missing, invalid, or expired JWT bearer token. |
| **`403 Forbidden`** | Authenticated user lacks the required RBAC role. |
| **`404 Not Found`** | Resource identifier does not exist in the database. |
| **`422 Unprocessable`** | Pydantic schema validation failure (e.g., invalid data types, missing required fields). |
| **`500 Internal Error`** | Unhandled server exception (caught by global exception middleware). |

---

## 2. Complete RBAC Permission Matrix

The platform enforces four hierarchical authorization roles:

| API Functional Group | Endpoint Pattern | Admin | Manager | HR | Employee |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Authentication: Self Profile** | `GET /api/v1/auth/me` |  |  |  |  |
| **Authentication: User Provisioning** | `POST /api/v1/auth/users` |  | ❌ | ❌ | ❌ |
| **HR: Employee Directory Read** | `GET /api/v1/hr/employees/` |  |  |  | ❌ (Self) |
| **HR: Employee Directory Write** | `POST, PUT, DELETE /api/v1/hr/employees/*` |  | ❌ |  | ❌ |
| **HR: Submit Leave Application** | `POST /api/v1/hr/leaves` |  |  |  |  |
| **HR: Leave Status Review** | `PATCH /api/v1/hr/leaves/{id}/status` |  |  |  | ❌ |
| **Sales: Customers & Orders Read** | `GET /api/v1/sales/*` |  |  | ❌ | ❌ |
| **Sales: Customers & Orders Write** | `POST, PUT, PATCH /api/v1/sales/*` |  |  | ❌ | ❌ |
| **Inventory: Products & Movements Read** | `GET /api/v1/inventory/*` |  |  | ❌ | ❌ |
| **Inventory: Stock Adjustments & Check-in** | `POST /api/v1/inventory/stock/*` |  |  | ❌ | ❌ |
| **Cross-Department Analytics** | `GET /api/v1/analytics/*` |  |  | ❌ | ❌ |
| **Predictive Analytics & Forecasts** | `GET /api/v1/predictions/*` |  |  | ❌ | ❌ |
| **Agentic AI Conversational Chat** | `POST /api/v1/agents/chat` |  |  |  |  (Scoped) |
| **Conversation Thread History** | `GET, POST, PATCH /api/v1/conversations/*` |  |  |  |  |
| **RAG: Document Upload & Indexing** | `POST /api/v1/documents/upload` |  |  |  | ❌ |
| **RAG: Document Semantic Search & Q&A** | `POST /api/v1/documents/search, /ask` |  |  |  |  (Scoped) |
| **HITL: Submit Approval Proposal** | `POST /api/v1/approvals` |  |  |  |  |
| **HITL: Review Approval (Approve/Reject)**| `POST /api/v1/approvals/{id}/approve` |  |  |  (Leave) | ❌ |
| **HITL: Execute Approved Action** | `POST /api/v1/approvals/{id}/execute` |  |  |  | ❌ |

---

## 3. Detailed Endpoint Reference by Group

### 3.1 Authentication & User Management (`/api/v1/auth`)

#### 1. `POST /api/v1/auth/login`
- **Description:** Authenticate using corporate email and password to receive a JWT access token.
- **Auth Required:** None (Public).
- **Request Body:** Form URL-encoded (`OAuth2PasswordRequestForm`)
  - `username` (string): Corporate email address (e.g. `admin@enterprise.com`).
  - `password` (string): User password.
- **Success Response (`200 OK`):** `TokenResponse`
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "role": "Admin",
    "email": "admin@enterprise.com",
    "employee_id": 1
  }
  ```
- **Error Responses:** `401 Unauthorized` (Invalid credentials), `403 Forbidden` (Inactive account).

#### 2. `GET /api/v1/auth/me`
- **Description:** Retrieve current authenticated user profile and linked employee identity.
- **Auth Required:** Authenticated user (`Admin`, `Manager`, `HR`, `Employee`).
- **Success Response (`200 OK`):** `UserResponse`
  ```json
  {
    "id": 1,
    "email": "admin@enterprise.com",
    "role": "Admin",
    "is_active": true,
    "employee_id": 1,
    "created_at": "2026-11-01T00:00:00Z"
  }
  ```

#### 3. `POST /api/v1/auth/register`
- **Description:** Public registration endpoint. Always provisions accounts with default `Employee` application role.
- **Auth Required:** None (Public).
- **Request Body:** `UserRegister` (`email`, `password`)
- **Success Response (`201 Created`):** `UserResponse`

#### 4. `POST /api/v1/auth/users`
- **Description:** Privileged administrative user creation. Allows assigning specific roles (`Admin`, `Manager`, `HR`, `Employee`) and linking to specific employee IDs.
- **Auth Required:** `Admin` role only.
- **Request Body:** `UserCreateByAdmin` (`email`, `password`, `role`, `employee_id`, `is_active`)
- **Success Response (`201 Created`):** `UserResponse`
- **Error Responses:** `400 Bad Request` (Email already registered), `403 Forbidden` (Non-admin caller).

---

### 3.2 Human Resources & Leaves (`/api/v1/hr`)

#### 1. `GET /api/v1/hr/employees/`
- **Description:** List employees with pagination and department/status filters.
- **Auth Required:** `Admin`, `HR`, `Manager`.
- **Query Parameters:** `skip` (int, default: 0), `limit` (int, default: 100), `department` (optional string), `is_active` (optional bool).
- **Success Response (`200 OK`):** `list[EmployeeResponse]`

#### 2. `POST /api/v1/hr/employees/`
- **Description:** Register a new employee record.
- **Auth Required:** `Admin`, `HR`.
- **Request Body:** `EmployeeCreate` (`employee_id`, `full_name`, `department`, `role`, `is_active`)
- **Success Response (`201 Created`):** `EmployeeResponse`

#### 3. `GET /api/v1/hr/employees/{employee_id}`
- **Description:** Fetch specific employee by primary key ID.
- **Auth Required:** `Admin`, `HR`, `Manager` (or `Employee` accessing own linked ID).
- **Success Response (`200 OK`):** `EmployeeResponse`

#### 4. `PUT /api/v1/hr/employees/{employee_id}`
- **Description:** Update an existing employee profile.
- **Auth Required:** `Admin`, `HR`.
- **Request Body:** `EmployeeUpdate`
- **Success Response (`200 OK`):** `EmployeeResponse`

#### 5. `DELETE /api/v1/hr/employees/{employee_id}`
- **Description:** Delete an employee. Blocked if linked to active user accounts or orders.
- **Auth Required:** `Admin`, `HR`.
- **Success Response (`200 OK`):** `{"message": "Employee deleted successfully"}`

#### 6. `POST /api/v1/hr/leaves`
- **Description:** Submit a new leave request.
- **Auth Required:** Authenticated user (`Admin`, `Manager`, `HR`, `Employee`).
- **Request Body:** `LeaveCreate` (`employee_id`, `leave_type`, `start_date`, `end_date`, `reason`)
- **Success Response (`201 Created`):** `LeaveResponse`

#### 7. `GET /api/v1/hr/leaves`
- **Description:** List leave applications with optional filtering.
- **Auth Required:** `Admin`, `HR`, `Manager` (Employees view only their own records).
- **Query Parameters:** `skip`, `limit`, `status`, `department`, `leave_type`.
- **Success Response (`200 OK`):** `list[LeaveResponse]`

#### 8. `PATCH /api/v1/hr/leaves/{leave_id}/status`
- **Description:** Review and approve or reject a leave request.
- **Auth Required:** `Admin`, `HR`, `Manager`.
- **Request Body:** `LeaveStatusUpdate` (`status`: APPROVED / REJECTED, `rejection_reason`: optional string)
- **Success Response (`200 OK`):** `LeaveResponse`

#### 9. `GET /api/v1/hr/reports/leaves`
- **Description:** Retrieve consolidated leave statistics across departments.
- **Auth Required:** `Admin`, `HR`, `Manager`.
- **Success Response (`200 OK`):** `LeaveSummaryReport`

---

### 3.3 Sales Operations (`/api/v1/sales`)

#### 1. `GET /api/v1/sales/customers` & `POST /api/v1/sales/customers`
- **Description:** List customers or create a new corporate customer account.
- **Auth Required:** `Admin`, `Manager`.
- **Request Body (POST):** `CustomerCreate` (`customer_code`, `name`, `email`, `phone`, `company`)
- **Success Response:** `list[CustomerResponse]` (GET), `CustomerResponse` (POST).

#### 2. `POST /api/v1/sales/orders`
- **Description:** Create a new multi-line sales order.
- **Auth Required:** `Admin`, `Manager`.
- **Request Body:** `OrderCreate` (`customer_id`, `order_date`, `notes`, `items`: list of `OrderItemCreate`)
- **Success Response (`201 Created`):** `OrderDetailResponse`

#### 3. `GET /api/v1/sales/orders` & `GET /api/v1/sales/orders/{order_id}`
- **Description:** List orders with pagination and status filters, or get order details with line items.
- **Auth Required:** `Admin`, `Manager`.
- **Success Response (`200 OK`):** `list[OrderResponse]` (List), `OrderDetailResponse` (Detail).

#### 4. `PATCH /api/v1/sales/orders/{order_id}/status`
- **Description:** Transition order lifecycle status.
- **Important Business Rule:** Transitioning to `CONFIRMED` verifies stock and deducts `quantity_on_hand` via an outbound `StockMovement`. Transitioning from `CONFIRMED` to `CANCELLED` restores deducted stock.
- **Auth Required:** `Admin`, `Manager`.
- **Request Body:** `OrderStatusUpdate` (`status`: CONFIRMED / SHIPPED / DELIVERED / CANCELLED)
- **Success Response (`200 OK`):** `OrderDetailResponse`

#### 5. `GET /api/v1/sales/reports/monthly` & `GET /api/v1/sales/reports/summary`
- **Description:** Aggregated recognized monthly revenue reports and top-selling products.
- **Auth Required:** `Admin`, `Manager`.
- **Success Response (`200 OK`):** `MonthlyRevenueReport`, `SalesSummaryReport`.

---

### 3.4 Inventory Management (`/api/v1/inventory`)

#### 1. `GET /api/v1/inventory/products` & `POST /api/v1/inventory/products`
- **Description:** Query product catalog or define a new catalog SKU.
- **Auth Required:** `Admin`, `Manager`.
- **Request Body (POST):** `ProductCreate` (`sku`, `name`, `unit_price`, `cost_price`, `reorder_threshold`, `target_stock`)
- **Success Response:** `list[ProductResponse]`, `ProductResponse`.

#### 2. `GET /api/v1/inventory/alerts/low-stock`
- **Description:** Automated low-stock detection identifying items where `quantity_on_hand <= reorder_threshold`.
- **Auth Required:** `Admin`, `Manager`.
- **Success Response (`200 OK`):** `LowStockAlertReport`

#### 3. `POST /api/v1/inventory/stock/in`
- **Description:** Check in incoming inventory delivery. Decrements `quantity_on_order` if fulfilling purchase orders and increments physical `quantity_on_hand`.
- **Auth Required:** `Admin`, `Manager`.
- **Request Body:** `StockInRequest` (`product_id`, `quantity`, `unit_price`, `reason`, `reference`, `fulfill_on_order`)
- **Success Response (`200 OK`):** `StockMovementResponse`

#### 4. `POST /api/v1/inventory/stock/out` & `POST /api/v1/inventory/stock/adjust`
- **Description:** Record manual inventory dispatch or stock reconciliation count adjustment.
- **Auth Required:** `Admin`, `Manager`.
- **Request Body:** `StockOutRequest`, `StockAdjustRequest`.
- **Success Response (`200 OK`):** `StockMovementResponse`.

#### 5. `GET /api/v1/inventory/reports/summary`
- **Description:** Enterprise inventory health metrics (Total SKUs, Valuation, Units on Hand, Units on Order, Low Stock Count).
- **Auth Required:** `Admin`, `Manager`.
- **Success Response (`200 OK`):** `InventorySummaryReport`

---

### 3.5 Cross-Department Analytics (`/api/v1/analytics`)

#### 1. `GET /api/v1/analytics/overview`
- **Description:** Unified executive dashboard metrics: Total Recognized Revenue, Active Headcount, Low Stock Count, Pending Approvals Count.
- **Auth Required:** `Admin`, `Manager`.
- **Success Response (`200 OK`):** `OverviewAnalytics`

#### 2. `GET /api/v1/analytics/cross-department`
- **Description:** Correlates monthly revenue performance against warehouse stock levels and staffing allocations.
- **Auth Required:** `Admin`, `Manager`.
- **Success Response (`200 OK`):** `CrossDepartmentReport`

#### 3. `GET /api/v1/analytics/replenishment`
- **Description:** Prescriptive replenishment suggestions derived from target stock, lead times, and current stock.
- **Auth Required:** `Admin`, `Manager`.
- **Success Response (`200 OK`):** `list[ReplenishmentAnalyticsItem]`

---

### 3.6 Agentic AI Supervisor & Conversations (`/api/v1/agents` & `/api/v1/conversations`)

#### 1. `POST /api/v1/agents/chat`
- **Description:** Primary entry point for natural language interaction with the LangGraph Multi-Agent Supervisor.
- **Auth Required:** Authenticated user (`Admin`, `Manager`, `HR`, `Employee`).
- **Request Body:** `AgentChatRequest`
  ```json
  {
    "message": "Which products are currently at risk of stockout within 30 days?",
    "conversation_id": 1
  }
  ```
- **Success Response (`200 OK`):** `AgentChatResponse`
  ```json
  {
    "answer": "Based on current demand velocity, 2 products face critical stockout risk: SKU-GFT-001 and SKU-GFT-004...",
    "tools_used": ["get_inventory_shortage_risks"],
    "departments_used": ["inventory", "predictions"],
    "citations": [],
    "conversation_id": 1,
    "pending_approval": null
  }
  ```

#### 2. `GET /api/v1/conversations` & `POST /api/v1/conversations`
- **Description:** List past conversation threads owned by the user, or initialize a new chat session.
- **Auth Required:** Authenticated user.
- **Success Response:** `list[ConversationResponse]`, `ConversationResponse`.

#### 3. `GET /api/v1/conversations/{conversation_id}`
- **Description:** Fetch conversation detail with complete chronological message history and tool calls.
- **Auth Required:** Authenticated owner or `Admin`.
- **Success Response (`200 OK`):** `ConversationDetailResponse`

---

### 3.7 Knowledge Base & Document Intelligence (`/api/v1/documents`)

#### 1. `POST /api/v1/documents/upload`
- **Description:** Ingest, parse, chunk, embed, and index a corporate policy document into ChromaDB.
- **Auth Required:** `Admin`, `Manager`, `HR` (`Employee` role is blocked with HTTP 403).
- **Request Body:** `multipart/form-data`
  - `file`: Binary file (`.pdf`, `.docx`, `.txt`).
  - `department`: Corporate scope (`general`, `hr`, `sales`, `inventory`).
- **Validation:** Enforces magic byte headers (`%PDF-`, `PK\x03\x04`). Rejects scanned raster PDFs lacking text layers.
- **Success Response (`200 OK`):** `DocumentIngestResponse`

#### 2. `POST /api/v1/documents/search`
- **Description:** Vector similarity search over ChromaDB embeddings with metadata department filtering.
- **Auth Required:** Authenticated user.
- **Request Body:** `DocumentSearchRequest` (`query`, `department`, `top_k`)
- **Success Response (`200 OK`):** `DocumentSearchResponse` (list of `DocumentChunkResult`)

#### 3. `POST /api/v1/documents/ask`
- **Description:** End-to-end RAG Q&A retrieving relevant policy chunks and synthesizing an attributed answer.
- **Auth Required:** Authenticated user.
- **Request Body:** `RAGAnswerRequest` (`query`, `department`, `top_k`)
- **Success Response (`200 OK`):** `RAGAnswerResponse` (answer, source citations, chunk scores)

#### 4. `DELETE /api/v1/documents/{document_id}`
- **Description:** Delete all indexed chunks and metadata belonging to a document from ChromaDB.
- **Auth Required:** `Admin`, `Manager`, `HR`.
- **Success Response (`200 OK`):** `DocumentDeleteResponse`

---

### 3.8 Human-in-the-Loop Approvals (`/api/v1/approvals`)

#### 1. `GET /api/v1/approvals` & `GET /api/v1/approvals/pending`
- **Description:** List approval requests with optional status filtering, or view the active pending review queue.
- **Auth Required:** `Admin`, `Manager`, `HR`.
- **Success Response (`200 OK`):** `list[ApprovalResponse]`

#### 2. `GET /api/v1/approvals/{request_id}` & `GET /api/v1/approvals/{request_id}/history`
- **Description:** Retrieve full details of an approval proposal (including deserialized JSON payload) or its immutable audit log.
- **Auth Required:** `Admin`, `Manager`, `HR` (or original requester).
- **Success Response (`200 OK`):** `ApprovalDetailResponse`, `list[ApprovalAuditResponse]`.

#### 3. `POST /api/v1/approvals/{request_id}/approve` & `POST /api/v1/approvals/{request_id}/reject`
- **Description:** Review and authorize or reject a proposal.
- **Auth Required:** Purchase orders: `Admin`, `Manager`. Leave requests: `Admin`, `Manager`, `HR`.
- **Request Body (POST):** `ApprovalReviewRequest` (`notes`: optional approval comments or mandatory rejection reason)
- **Success Response (`200 OK`):** `ApprovalResponse`

#### 4. `POST /api/v1/approvals/{request_id}/execute`
- **Description:** Trigger two-phase commit execution of an approved request.
- **Business Behavior:**
  - For purchase requisitions: Increments `Product.quantity_on_order`. Physical stock is **not** modified.
  - For leave requests: Commits a formal `LeaveRequest` record.
  - **Idempotency:** Repeated calls on already `EXECUTED` requests return HTTP 400.
- **Auth Required:** `Admin`, `Manager`, `HR`.
- **Success Response (`200 OK`):** `{"request_code": "REQ-PO-...", "status": "executed", "result": {...}}`

---

### 3.9 Predictive Analytics & Forecasting (`/api/v1/predictions`)

#### 1. `GET /api/v1/predictions/sales-forecast`
- **Description:** 3-month forward sales revenue forecast generated by the best-performing evaluated model.
- **Auth Required:** `Admin`, `Manager`.
- **Success Response (`200 OK`):** `SalesForecastResponse`
  ```json
  {
    "forecast_model_used": "Holt's Linear Trend",
    "evaluation_split": "Train: 4 months (2026-05 to 2026-08), Test: 2 months (2026-09 to 2026-10)",
    "forecast_next_3_months": [
      {"month": "2026-11", "predicted_revenue": 108420.50, "confidence_lower": 98200.00, "confidence_upper": 118641.00},
      {"month": "2026-12", "predicted_revenue": 121045.20, "confidence_lower": 109500.00, "confidence_upper": 132590.40},
      {"month": "2027-01", "predicted_revenue": 133670.00, "confidence_lower": 120800.00, "confidence_upper": 146540.00}
    ]
  }
  ```

#### 2. `GET /api/v1/predictions/model-performance`
- **Description:** Out-of-sample error comparison across all four competing time-series models on held-out test data.
- **Auth Required:** `Admin`, `Manager`.
- **Success Response (`200 OK`):** `ModelPerformanceResponse` (benchmarks Naive, 3-Month SMA, OLS Trend, and Holt's Smoothing with MAE, RMSE, and MAPE).

#### 3. `GET /api/v1/predictions/inventory-risk`
- **Description:** SKU-level stockout risk evaluation based on daily velocity, available stock, and projected monthly demand.
- **Auth Required:** `Admin`, `Manager`.
- **Success Response (`200 OK`):** `InventoryRiskResponse` (categorized into Critical, Moderate, and Low risk).

---

### 3.10 System Health (`/` & `/health`)

#### 1. `GET /health`
- **Description:** System health check endpoint verifying database connectivity.
- **Auth Required:** None (Public).
- **Success Response (`200 OK`):**
  ```json
  {
    "status": "healthy",
    "database": "connected",
    "timestamp": "2026-11-03T04:20:00.000Z"
  }
  ```
