"""Persistence and lifecycle transitions for agent execution records."""

import json
import logging
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import func, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.agent_run import AgentRun, AgentRunStatus
from app.schemas.agent import AgentChatResponse

MAX_RESULT_METADATA_BYTES = 4096
logger = logging.getLogger("app.services.agent_run")


class AgentRunPersistenceError(Exception):
    """Raised when an agent run cannot be safely persisted."""


class InvalidAgentRunTransition(ValueError):
    """Raised when a run is asked to make an invalid lifecycle transition."""


def _now_utc_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _safe_result_metadata(response: AgentChatResponse) -> dict[str, object]:
    metadata: dict[str, object] = {
        "departments_used": response.departments_used[:10],
        "agents_involved": response.agents_involved[:10],
        "tools_used": response.tools_used[:20],
        "source_attribution": (
            response.source_attribution[:32]
            if response.source_attribution is not None
            else None
        ),
    }
    bounded = {
        key: [value[:100] for value in values if isinstance(value, str)]
        if isinstance(values, list)
        else values
        for key, values in metadata.items()
    }
    encoded = json.dumps(bounded, separators=(",", ":"), ensure_ascii=False)
    for key in ("tools_used", "agents_involved", "departments_used"):
        values = bounded[key]
        while len(encoded.encode("utf-8")) > MAX_RESULT_METADATA_BYTES and values:
            values.pop()
            encoded = json.dumps(bounded, separators=(",", ":"), ensure_ascii=False)
    if len(encoded.encode("utf-8")) > MAX_RESULT_METADATA_BYTES:
        raise ValueError("Agent run result metadata exceeds the configured limit.")
    return bounded


class AgentRunService:
    """Owns agent run persistence, transition validation, and owner-scoped queries."""

    @staticmethod
    def create_running(
        db: Session,
        *,
        user_id: int,
        conversation_id: int | None,
        agent_type: str = "supervisor_chat",
    ) -> AgentRun:
        """Create a run and atomically persist its PENDING-to-RUNNING transition."""
        run = AgentRun(
            id=str(uuid4()),
            user_id=user_id,
            conversation_id=conversation_id,
            agent_type=agent_type,
            status=AgentRunStatus.PENDING.value,
        )
        run_id = run.id
        try:
            db.add(run)
            db.flush()
            AgentRunService._transition(
                run,
                AgentRunStatus.RUNNING,
                started_at=_now_utc_naive(),
            )
            db.commit()
        except SQLAlchemyError:
            db.rollback()
            raise AgentRunPersistenceError(
                "Agent run tracking could not be persisted."
            ) from None

        try:
            db.refresh(run)
        except SQLAlchemyError:
            db.rollback()
            AgentRunService._fail_unreturned_run(db, run_id)
            raise AgentRunPersistenceError(
                "Agent run tracking could not be verified."
            ) from None
        return run

    @staticmethod
    def mark_completed(
        db: Session, run: AgentRun, response: AgentChatResponse
    ) -> AgentRun:
        metadata = _safe_result_metadata(response)
        AgentRunService._transition(
            run,
            AgentRunStatus.COMPLETED,
            completed_at=_now_utc_naive(),
        )
        run.result_metadata = metadata
        return AgentRunService._commit_transition(db, run)

    @staticmethod
    def mark_failed(
        db: Session, run: AgentRun, error_summary: str
    ) -> AgentRun:
        if not error_summary.strip():
            raise ValueError("A bounded error summary is required.")
        AgentRunService._transition(
            run,
            AgentRunStatus.FAILED,
            completed_at=_now_utc_naive(),
        )
        run.error_summary = error_summary.strip()[:250]
        return AgentRunService._commit_transition(db, run)

    @staticmethod
    def _transition(
        run: AgentRun,
        target: AgentRunStatus,
        *,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
    ) -> None:
        allowed = {
            AgentRunStatus.PENDING: {AgentRunStatus.RUNNING},
            AgentRunStatus.RUNNING: {
                AgentRunStatus.COMPLETED,
                AgentRunStatus.FAILED,
            },
            AgentRunStatus.COMPLETED: set(),
            AgentRunStatus.FAILED: set(),
        }
        try:
            current = AgentRunStatus(run.status)
        except ValueError:
            raise InvalidAgentRunTransition("Run has an unknown current status.") from None
        if target not in allowed[current]:
            raise InvalidAgentRunTransition(
                f"Run cannot transition from {current.value} to {target.value}."
            )
        run.status = target.value
        if started_at is not None:
            run.started_at = started_at
        if completed_at is not None:
            run.completed_at = completed_at

    @staticmethod
    def _commit_transition(db: Session, run: AgentRun) -> AgentRun:
        try:
            db.commit()
        except SQLAlchemyError:
            db.rollback()
            raise AgentRunPersistenceError(
                "Agent run tracking could not be persisted."
            ) from None
        try:
            db.refresh(run)
        except SQLAlchemyError:
            # The terminal state is already committed and must not be reclassified.
            logger.warning("Could not refresh committed agent run id=%s", run.id)
        return run

    @staticmethod
    def _fail_unreturned_run(db: Session, run_id: str) -> None:
        """Best-effort terminalize a committed run that cannot safely be returned."""
        try:
            db.execute(
                update(AgentRun)
                .where(
                    AgentRun.id == run_id,
                    AgentRun.status == AgentRunStatus.RUNNING.value,
                )
                .values(
                    status=AgentRunStatus.FAILED.value,
                    error_summary="Agent run could not be verified.",
                    completed_at=_now_utc_naive(),
                )
            )
            db.commit()
        except SQLAlchemyError:
            db.rollback()
            logger.error(
                "Could not terminalize unreturned agent run id=%s after refresh failure",
                run_id,
            )

    @staticmethod
    def list_for_user(
        db: Session,
        *,
        user_id: int,
        skip: int,
        limit: int,
        status_filter: AgentRunStatus | None,
    ) -> tuple[list[AgentRun], int]:
        conditions = [AgentRun.user_id == user_id]
        if status_filter is not None:
            conditions.append(AgentRun.status == status_filter.value)
        total = db.scalar(
            select(func.count()).select_from(AgentRun).where(*conditions)
        ) or 0
        runs = list(
            db.scalars(
                select(AgentRun)
                .where(*conditions)
                .order_by(AgentRun.created_at.desc(), AgentRun.id.desc())
                .offset(skip)
                .limit(limit)
            ).all()
        )
        return runs, total

    @staticmethod
    def get_for_user(
        db: Session, *, run_id: str, user_id: int
    ) -> AgentRun | None:
        return db.scalar(
            select(AgentRun).where(
                AgentRun.id == run_id,
                AgentRun.user_id == user_id,
            )
        )


agent_run_service = AgentRunService()
