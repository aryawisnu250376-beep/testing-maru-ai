from app.agents.registry import create_subject_agents


def create_agents(settings, provider):
    return create_subject_agents(settings, provider, "PA")
