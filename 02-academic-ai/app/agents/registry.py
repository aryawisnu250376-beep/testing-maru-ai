from __future__ import annotations

from app.agents.base import AcademicAgent
from app.config import Settings
from app.providers.base import AIProvider


def create_subject_agents(
    settings: Settings,
    provider: AIProvider,
    subject_code: str,
) -> tuple[AcademicAgent, AcademicAgent, AcademicAgent]:
    subject = settings.subjects[subject_code]
    return (
        AcademicAgent(settings, provider, subject, "agent_a"),
        AcademicAgent(settings, provider, subject, "agent_b"),
        AcademicAgent(settings, provider, subject, "agent_c"),
    )
