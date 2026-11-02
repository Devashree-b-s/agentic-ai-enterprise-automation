"""Specialized department agents registry for multi-agent coordination."""

from app.agents.specialized.analytics_agent import AnalyticsAgent, analytics_agent
from app.agents.specialized.base import AgentExecutionResult, BaseSpecializedAgent
from app.agents.specialized.document_agent import (
    DocumentIntelligenceAgent,
    document_agent,
)
from app.agents.specialized.hr_agent import HRAgent, hr_agent
from app.agents.specialized.inventory_agent import InventoryAgent, inventory_agent
from app.agents.specialized.sales_agent import SalesAgent, sales_agent

SPECIALIZED_AGENTS: dict[str, BaseSpecializedAgent] = {
    "hr": hr_agent,
    "sales": sales_agent,
    "inventory": inventory_agent,
    "documents": document_agent,
    "analytics": analytics_agent,
}

__all__ = [
    "SPECIALIZED_AGENTS",
    "AgentExecutionResult",
    "AnalyticsAgent",
    "BaseSpecializedAgent",
    "DocumentIntelligenceAgent",
    "HRAgent",
    "InventoryAgent",
    "SalesAgent",
    "analytics_agent",
    "document_agent",
    "hr_agent",
    "inventory_agent",
    "sales_agent",
]
