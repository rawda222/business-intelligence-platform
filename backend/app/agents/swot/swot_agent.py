"""
SWOT Agent (Wrapper)

This module exposes the SWOTAgent class used by the AI service.

For now, it imports the actual implementation from the existing
swot_agent.py file located in app/agents/swot_agent.py.
The legacy production-grade v7 implementation is preserved in
_legacy_workflow.py and will be refactored into stages/ later.
"""
from app.agents.swot_agent import swot_agent

__all__ = ["swot_agent"]