"""Tests for persistent agent run lifecycle, ownership, and chat integration."""

import pytest
from app.models.agent_run import AgentRun, AgentRunStatus
from app.models.user import User, UserRole
from app.schemas.agent import AgentChatResponse
from app.services.agent_run_service import (
    AgentRunPersistenceError,
    InvalidAgentRunTransition,
    agent_run_service,
)
from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy.exc import SQLAlchemyError


def _create_user(db_session, email: str = "run.fixture@enterprise.com") -> User:
    user = User(
        email=email,
        hashed_password="test-password-hash",
        role=UserRole.EMPLOYEE.value,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


def _successful_response() -> AgentChatResponse:
    return AgentChatResponse(
        answer="There are 4 active employees.",
        departments_used=["hr"],
        agents_involved=["hr_agent"],
        tools_used=["list_active_employees"],
        success=True,
        source_attribution="database",
    )


def test_agent_run_lifecycle_and_transition_validation(db_session):
    user = _create_user(db_session)
    run = agent_run_service.create_running(
        db_session, user_id=user.id, conversation_id=None
    )
    assert run.status == AgentRunStatus.RUNNING.value
    assert run.started_at is not None
    assert run.completed_at is None

    completed = agent_run_service.mark_completed(
        db_session, run, _successful_response()
    )
    assert completed.status == AgentRunStatus.COMPLETED.value
    assert completed.completed_at is not None
    assert completed.completed_at >= completed.started_at
    assert completed.result_metadata == {
        "departments_used": ["hr"],
        "agents_involved": ["hr_agent"],
        "tools_used": ["list_active_employees"],
        "source_attribution": "database",
    }

    with pytest.raises(InvalidAgentRunTransition):
        agent_run_service.mark_failed(db_session, completed, "Should not transition.")


def test_agent_run_failed_state_has_safe_bounded_summary(db_session):
    user = _create_user(db_session)
    run = agent_run_service.create_running(
        db_session, user_id=user.id, conversation_id=None
    )
    failed = agent_run_service.mark_failed(
        db_session,
        run,
        "Agent execution failed. " + ("x" * 400),
    )
    assert failed.status == AgentRunStatus.FAILED.value
    assert failed.started_at is not None
    assert failed.completed_at is not None
    assert len(failed.error_summary) == 250
    assert "traceback" not in failed.error_summary.lower()


def test_agent_run_result_metadata_is_bounded(db_session):
    user = _create_user(db_session)
    run = agent_run_service.create_running(
        db_session, user_id=user.id, conversation_id=None
    )
    response = _successful_response()
    response.tools_used = ["tool-" + ("x" * 200)] * 50
    completed = agent_run_service.mark_completed(db_session, run, response)
    assert completed.status == AgentRunStatus.COMPLETED.value
    assert len(completed.result_metadata["tools_used"]) == 20
    assert all(len(value) == 100 for value in completed.result_metadata["tools_used"])


def test_initial_commit_then_refresh_failure_fails_run_and_blocks_execution(
    client: TestClient, admin_headers: dict[str, str], db_session, monkeypatch
):
    from app.api import agents as agents_api

    original_refresh = db_session.refresh
    calls = []

    def fail_agent_run_refresh(instance, *args, **kwargs):
        if isinstance(instance, AgentRun):
            raise SQLAlchemyError("simulated post-commit refresh failure")
        return original_refresh(instance, *args, **kwargs)

    monkeypatch.setattr(db_session, "refresh", fail_agent_run_refresh)
    monkeypatch.setattr(
        agents_api,
        "run_supervisor_chat",
        lambda **kwargs: calls.append(kwargs) or _successful_response(),
    )
    response = client.post(
        "/api/v1/agents/chat",
        json={"message": "How many employees are active?"},
        headers=admin_headers,
    )

    assert response.status_code == 503
    assert calls == []
    run = db_session.scalar(select(AgentRun))
    assert run.status == AgentRunStatus.FAILED.value
    assert run.error_summary == "Agent run could not be verified."
    assert run.completed_at is not None


def test_completed_commit_then_refresh_failure_keeps_completed_state(db_session, monkeypatch):
    user = _create_user(db_session)
    run = agent_run_service.create_running(
        db_session, user_id=user.id, conversation_id=None
    )

    def fail_refresh(instance, *args, **kwargs):
        raise SQLAlchemyError("simulated post-commit refresh failure")

    monkeypatch.setattr(db_session, "refresh", fail_refresh)
    completed = agent_run_service.mark_completed(
        db_session, run, _successful_response()
    )
    assert completed.status == AgentRunStatus.COMPLETED.value
    db_session.expire_all()
    persisted = db_session.scalar(select(AgentRun).where(AgentRun.id == run.id))
    assert persisted.status == AgentRunStatus.COMPLETED.value
    assert persisted.completed_at is not None


def test_failed_commit_then_refresh_failure_keeps_failed_state(db_session, monkeypatch):
    user = _create_user(db_session)
    run = agent_run_service.create_running(
        db_session, user_id=user.id, conversation_id=None
    )

    def fail_refresh(instance, *args, **kwargs):
        raise SQLAlchemyError("simulated post-commit refresh failure")

    monkeypatch.setattr(db_session, "refresh", fail_refresh)
    failed = agent_run_service.mark_failed(db_session, run, "Agent execution failed.")
    assert failed.status == AgentRunStatus.FAILED.value
    db_session.expire_all()
    persisted = db_session.scalar(select(AgentRun).where(AgentRun.id == run.id))
    assert persisted.status == AgentRunStatus.FAILED.value
    assert persisted.completed_at is not None


def test_terminal_commit_failure_rolls_back(db_session):
    user = _create_user(db_session)
    run = agent_run_service.create_running(
        db_session, user_id=user.id, conversation_id=None
    )
    rollbacks = []

    def fail_agent_run_commit(session):
        if any(isinstance(item, AgentRun) for item in session.dirty):
            raise SQLAlchemyError("simulated terminal commit failure")

    def count_rollback(session):
        rollbacks.append(True)

    event.listen(db_session, "before_commit", fail_agent_run_commit)
    event.listen(db_session, "after_rollback", count_rollback)
    try:
        with pytest.raises(AgentRunPersistenceError):
            agent_run_service.mark_completed(db_session, run, _successful_response())
    finally:
        event.remove(db_session, "before_commit", fail_agent_run_commit)
        event.remove(db_session, "after_rollback", count_rollback)

    assert rollbacks
    persisted = db_session.scalar(select(AgentRun).where(AgentRun.id == run.id))
    assert persisted.status == AgentRunStatus.RUNNING.value
    assert persisted.completed_at is None


def test_agent_run_api_ownership_filtering_and_pagination(
    client: TestClient, admin_headers: dict[str, str], manager_headers: dict[str, str],
    db_session,
):
    first = agent_run_service.create_running(
        db_session, user_id=1, conversation_id=None
    )
    agent_run_service.mark_completed(db_session, first, _successful_response())
    second = agent_run_service.create_running(
        db_session, user_id=1, conversation_id=None
    )
    agent_run_service.mark_failed(db_session, second, "Agent execution failed.")

    listed = client.get(
        "/api/v1/agent-runs?skip=0&limit=1&status=FAILED",
        headers=admin_headers,
    )
    assert listed.status_code == 200
    payload = listed.json()
    assert payload["total"] == 1
    assert payload["limit"] == 1
    assert len(payload["items"]) == 1
    assert payload["items"][0]["id"] == second.id
    assert payload["items"][0]["status"] == "FAILED"

    own_detail = client.get(
        f"/api/v1/agent-runs/{first.id}", headers=admin_headers
    )
    assert own_detail.status_code == 200
    assert own_detail.json()["user_id"] == 1

    cross_user_detail = client.get(
        f"/api/v1/agent-runs/{first.id}", headers=manager_headers
    )
    assert cross_user_detail.status_code == 404
    cross_user_list = client.get("/api/v1/agent-runs", headers=manager_headers)
    assert cross_user_list.status_code == 200
    assert cross_user_list.json()["total"] == 0


def test_agent_run_api_requires_authentication(client: TestClient):
    assert client.get("/api/v1/agent-runs").status_code == 401
    assert (
        client.get(
            "/api/v1/agent-runs/00000000-0000-0000-0000-000000000001"
        ).status_code
        == 401
    )


def test_agent_chat_tracks_success_without_changing_response_contract(
    client: TestClient, admin_headers: dict[str, str], monkeypatch
):
    from app.api import agents as agents_api

    monkeypatch.setattr(
        agents_api, "run_supervisor_chat", lambda **kwargs: _successful_response()
    )
    response = client.post(
        "/api/v1/agents/chat",
        json={"message": "How many employees are active?"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"] == "There are 4 active employees."
    assert payload["success"] is True
    assert payload["conversation_id"] is not None
    assert set(payload) == {
        "answer",
        "departments_used",
        "agents_involved",
        "tools_used",
        "success",
        "error",
        "source_attribution",
        "citations",
        "conversation_id",
    }

    runs = client.get("/api/v1/agent-runs", headers=admin_headers).json()
    assert runs["total"] == 1
    run = runs["items"][0]
    assert run["status"] == "COMPLETED"
    assert run["agent_type"] == "supervisor_chat"
    assert run["started_at"] is not None
    assert run["completed_at"] is not None
    assert "message" not in run
    assert "answer" not in run["result_metadata"]


def test_agent_chat_tracks_execution_failure(
    client: TestClient, admin_headers: dict[str, str], monkeypatch
):
    from app.api import agents as agents_api

    def fail_execution(**kwargs):
        raise RuntimeError("sensitive raw exception content")

    monkeypatch.setattr(agents_api, "run_supervisor_chat", fail_execution)
    response = client.post(
        "/api/v1/agents/chat",
        json={"message": "How many employees are active?"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["success"] is False
    assert "sensitive raw exception content" not in response.text

    runs = client.get(
        "/api/v1/agent-runs?status=FAILED", headers=admin_headers
    ).json()
    assert runs["total"] == 1
    assert runs["items"][0]["status"] == "FAILED"
    assert runs["items"][0]["error_summary"] == "Agent execution failed."


def test_agent_chat_tracks_unsuccessful_supervisor_response(
    client: TestClient, admin_headers: dict[str, str], monkeypatch
):
    from app.api import agents as agents_api

    unsuccessful = AgentChatResponse(
        answer="This request is unsupported.",
        success=False,
        error="Unsupported request.",
    )
    monkeypatch.setattr(
        agents_api, "run_supervisor_chat", lambda **kwargs: unsuccessful
    )
    response = client.post(
        "/api/v1/agents/chat",
        json={"message": "Tell me a joke"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["success"] is False
    runs = client.get("/api/v1/agent-runs?status=FAILED", headers=admin_headers)
    assert runs.json()["total"] == 1
    assert runs.json()["items"][0]["status"] == "FAILED"


def test_agent_chat_does_not_execute_when_initial_tracking_fails(
    client: TestClient, admin_headers: dict[str, str], monkeypatch
):
    from app.api import agents as agents_api

    calls = []

    def fail_tracking(*args, **kwargs):
        raise AgentRunPersistenceError("database detail must not leak")

    monkeypatch.setattr(agents_api.agent_run_service, "create_running", fail_tracking)
    monkeypatch.setattr(
        agents_api,
        "run_supervisor_chat",
        lambda **kwargs: calls.append(kwargs) or _successful_response(),
    )
    response = client.post(
        "/api/v1/agents/chat",
        json={"message": "How many employees are active?"},
        headers=admin_headers,
    )
    assert response.status_code == 503
    assert "database detail must not leak" not in response.text
    assert calls == []


def test_agent_chat_does_not_report_success_when_completion_tracking_fails(
    client: TestClient, admin_headers: dict[str, str], monkeypatch
):
    from app.api import agents as agents_api

    original_mark_failed = agents_api.agent_run_service.mark_failed

    def fail_completion(*args, **kwargs):
        raise AgentRunPersistenceError("completion write failed")

    monkeypatch.setattr(agents_api.agent_run_service, "mark_completed", fail_completion)
    monkeypatch.setattr(
        agents_api.agent_run_service, "mark_failed", original_mark_failed
    )
    monkeypatch.setattr(
        agents_api, "run_supervisor_chat", lambda **kwargs: _successful_response()
    )
    response = client.post(
        "/api/v1/agents/chat",
        json={"message": "How many employees are active?"},
        headers=admin_headers,
    )
    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Agent run tracking is temporarily unavailable."
    )
    listed = client.get("/api/v1/agent-runs?status=FAILED", headers=admin_headers)
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["error_summary"] == (
        "Execution result could not be recorded."
    )


def test_agent_chat_returns_503_and_retains_running_when_terminal_writes_fail(
    client: TestClient,
    admin_headers: dict[str, str],
    db_session,
    monkeypatch,
):
    from app.api import agents as agents_api

    monkeypatch.setattr(
        agents_api, "run_supervisor_chat", lambda **kwargs: _successful_response()
    )

    run_commit_attempts = 0

    def fail_agent_run_commit(session):
        nonlocal run_commit_attempts
        if any(isinstance(item, AgentRun) for item in session.dirty):
            run_commit_attempts += 1
            if run_commit_attempts > 1:
                raise SQLAlchemyError("simulated terminal commit failure")

    event.listen(db_session, "before_commit", fail_agent_run_commit)
    try:
        response = client.post(
            "/api/v1/agents/chat",
            json={"message": "How many employees are active?"},
            headers=admin_headers,
        )
    finally:
        event.remove(db_session, "before_commit", fail_agent_run_commit)

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Agent run tracking is temporarily unavailable."
    )
    db_session.expire_all()
    run = db_session.scalar(select(AgentRun))
    assert run.status == AgentRunStatus.RUNNING.value
    assert run.completed_at is None
    assert run_commit_attempts == 3


def test_agent_run_api_rejects_invalid_pagination_and_status(
    client: TestClient, admin_headers: dict[str, str]
):
    invalid_limit = client.get(
        "/api/v1/agent-runs?limit=0", headers=admin_headers
    )
    assert invalid_limit.status_code == 422
    invalid_status = client.get(
        "/api/v1/agent-runs?status=UNKNOWN", headers=admin_headers
    )
    assert invalid_status.status_code == 422
