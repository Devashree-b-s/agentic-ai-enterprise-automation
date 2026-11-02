"""Tests for Phase 3: Persistent AI Conversation Memory and User Isolation."""

from fastapi.testclient import TestClient


def test_create_and_list_conversations(client: TestClient, admin_headers: dict[str, str]):
    """Test creating a conversation and listing user conversations."""
    # 1. Create conversation
    res = client.post(
        "/api/v1/conversations",
        json={"title": "Q3 Planning Session"},
        headers=admin_headers,
    )
    assert res.status_code == 201
    conv = res.json()
    assert conv["title"] == "Q3 Planning Session"
    conv_id = conv["id"]

    # 2. List conversations
    res_list = client.get("/api/v1/conversations", headers=admin_headers)
    assert res_list.status_code == 200
    convs = res_list.json()
    assert any(c["id"] == conv_id for c in convs)


def test_conversation_messages_persisted(
    client: TestClient, admin_headers: dict[str, str]
):
    """Test sending chat messages attaches to conversation and persists history."""
    # 1. Create conversation
    res = client.post(
        "/api/v1/conversations",
        json={"title": "Staffing Inquiries"},
        headers=admin_headers,
    )
    assert res.status_code == 201
    conv_id = res.json()["id"]

    # 2. Send initial message
    res_chat = client.post(
        "/api/v1/agents/chat",
        json={"message": "How many active employees are there?", "conversation_id": conv_id},
        headers=admin_headers,
    )
    assert res_chat.status_code == 200
    data = res_chat.json()
    assert data["conversation_id"] == conv_id

    # 3. Retrieve conversation details
    res_detail = client.get(f"/api/v1/conversations/{conv_id}", headers=admin_headers)
    assert res_detail.status_code == 200
    detail = res_detail.json()
    assert detail["message_count"] == 2
    assert len(detail["messages"]) == 2
    assert detail["messages"][0]["role"] == "user"
    assert "How many active employees" in detail["messages"][0]["content"]
    assert detail["messages"][1]["role"] == "assistant"
    assert len(detail["messages"][1]["content"]) > 10


def test_context_aware_followup_query(
    client: TestClient, admin_headers: dict[str, str]
):
    """Test context-aware follow-up question resolves previous conversational subject."""
    # 1. Create conversation
    res = client.post(
        "/api/v1/conversations",
        json={"title": "Contextual Followup Session"},
        headers=admin_headers,
    )
    conv_id = res.json()["id"]

    # 2. First query establishes topic (employees)
    client.post(
        "/api/v1/agents/chat",
        json={"message": "How many employees are currently active?", "conversation_id": conv_id},
        headers=admin_headers,
    )

    # 3. Follow-up query omits 'employee' keyword entirely
    res_followup = client.post(
        "/api/v1/agents/chat",
        json={"message": "What about in Engineering?", "conversation_id": conv_id},
        headers=admin_headers,
    )
    assert res_followup.status_code == 200
    data = res_followup.json()
    assert "list_department_staffing" in data["tools_used"] or "hr" in data["departments_used"]
    assert "engineering" in data["answer"].lower()


def test_user_isolation_blocks_unauthorized_access(
    client: TestClient, admin_headers: dict[str, str], manager_headers: dict[str, str]
):
    """Test strict user isolation: User B cannot access, read, or modify User A's conversation."""
    # 1. Admin creates a conversation
    res = client.post(
        "/api/v1/conversations",
        json={"title": "Confidential Executive Strategy"},
        headers=admin_headers,
    )
    conv_id = res.json()["id"]

    # 2. Manager attempts to read Admin's conversation detail
    res_get = client.get(f"/api/v1/conversations/{conv_id}", headers=manager_headers)
    assert res_get.status_code in (403, 404)

    # 3. Manager attempts to rename Admin's conversation
    res_patch = client.patch(
        f"/api/v1/conversations/{conv_id}",
        json={"title": "Hijacked Title"},
        headers=manager_headers,
    )
    assert res_patch.status_code in (403, 404)

    # 4. Manager attempts to delete Admin's conversation
    res_del = client.delete(f"/api/v1/conversations/{conv_id}", headers=manager_headers)
    assert res_del.status_code in (403, 404)

    # 5. Manager attempts to post chat message into Admin's conversation
    res_chat = client.post(
        "/api/v1/agents/chat",
        json={"message": "Inject prompt into other user session", "conversation_id": conv_id},
        headers=manager_headers,
    )
    assert res_chat.status_code in (403, 404)


def test_rename_and_delete_conversation(client: TestClient, admin_headers: dict[str, str]):
    """Test renaming and deleting conversation."""
    # 1. Create conversation
    res = client.post(
        "/api/v1/conversations",
        json={"title": "Temporary Session"},
        headers=admin_headers,
    )
    conv_id = res.json()["id"]

    # 2. Rename conversation
    res_rename = client.patch(
        f"/api/v1/conversations/{conv_id}",
        json={"title": "Renamed Permanent Title"},
        headers=admin_headers,
    )
    assert res_rename.status_code == 200
    assert res_rename.json()["title"] == "Renamed Permanent Title"

    # 3. Delete conversation
    res_del = client.delete(f"/api/v1/conversations/{conv_id}", headers=admin_headers)
    assert res_del.status_code == 204

    # 4. Verify 404 on get
    res_check = client.get(f"/api/v1/conversations/{conv_id}", headers=admin_headers)
    assert res_check.status_code == 404
