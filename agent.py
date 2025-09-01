from __future__ import annotations

import os
from typing import Any, Callable, List, Optional

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain.tools import StructuredTool
from langchain_openai import ChatOpenAI

from n8n_client import N8nClient


def _get_llm() -> ChatOpenAI:
    """Configure OpenRouter-backed OpenAI-compatible chat model.

    Env:
      - OPENROUTER_API_KEY (required)
      - OPENROUTER_BASE_URL (default https://openrouter.ai/api/v1)
      - OPENROUTER_MODEL (default openrouter/auto)
    """
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    base_url = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").strip()
    # Enable built-in web search by default using :online suffix per OpenRouter docs
    model_default = "openrouter/auto:online"
    model = os.environ.get("OPENROUTER_MODEL", model_default).strip()
    # temperature kept low for tool-use reliability
    return ChatOpenAI(
        model=model,
        temperature=0.2,
        openai_api_key=api_key,
        base_url=base_url,
    )


def _make_n8n_tools(client: N8nClient) -> List[StructuredTool]:
    def list_workflows() -> Any:
        return client.list_workflows()

    def get_workflow(workflow_id: str) -> Any:
        return client.get_workflow(workflow_id)

    def list_executions(workflow_id: Optional[str] = None, status: Optional[str] = None, limit: int = 20, offset: int = 0) -> Any:
        return client.list_executions(workflow_id=workflow_id, status=status, limit=limit, offset=offset)

    def get_execution(execution_id: str) -> Any:
        return client.get_execution(execution_id)

    return [
        StructuredTool.from_function(
            func=list_workflows,
            name="list_workflows",
            description="List available n8n workflows",
        ),
        StructuredTool.from_function(
            func=get_workflow,
            name="get_workflow",
            description="Get details for a specific n8n workflow by id",
        ),
        StructuredTool.from_function(
            func=list_executions,
            name="list_executions",
            description="List n8n executions, optionally filtered by workflow_id and status",
        ),
        StructuredTool.from_function(
            func=get_execution,
            name="get_execution",
            description="Get a specific execution by id",
        ),
    ]


# Web search is handled natively by OpenRouter using the :online model suffix; no extra tool needed


def build_agent(n8n_client: N8nClient) -> AgentExecutor:
    tools = _make_n8n_tools(n8n_client)

    system = (
        "You are an n8n copilot. You can read workflows and executions, analyze failures, "
        "and suggest JSON snippets for nodes/flows. DO NOT attempt to write or execute workflows. "
        "Use tools when needed. Be concise, prefer actionable, copyable JSON, and cite web sources using markdown links named by domain."
    )
    prompt = ChatPromptTemplate.from_messages([
        ("system", system),
        ("human", "{input}"),
        ("placeholder", "agent_scratchpad"),
    ])

    llm = _get_llm()
    agent = create_tool_calling_agent(llm, tools, prompt)
    return AgentExecutor(agent=agent, tools=tools, verbose=False)


__all__ = ["build_agent"]


