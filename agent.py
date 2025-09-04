from __future__ import annotations

import os
from typing import Any, Callable, List, Optional

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.tools import StructuredTool
from langchain_openai import ChatOpenAI

from n8n_client import N8nClient


def _get_llm(
    *,
    model_override: str | None = None,
    api_key_override: str | None = None,
    base_url_override: str | None = None,
) -> ChatOpenAI:
    """Configure OpenRouter-backed OpenAI-compatible chat model.

    Supports either environment variables or explicit overrides.

    Env:
      - OPENROUTER_API_KEY (preferred) or OPENAI_API_KEY
      - OPENROUTER_BASE_URL (default https://openrouter.ai/api/v1)
      - OPENROUTER_MODEL (default openai/gpt-5-nano)
    """
    api_key = (api_key_override or os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise ValueError("Missing OpenRouter API key. Set OPENROUTER_API_KEY (preferred) or OPENAI_API_KEY.")

    base_url = (base_url_override or os.environ.get("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1").strip()
    # Default to OpenRouter’s OpenAI model namespace
    model_default = "openai/gpt-5-nano"
    model = (model_override or os.environ.get("OPENROUTER_MODEL") or model_default).strip()

    # Also set env vars for the OpenAI SDK, which langchain-openai uses under the hood
    os.environ["OPENAI_API_KEY"] = api_key
    os.environ["OPENAI_BASE_URL"] = base_url

    # langchain_openai expects `api_key`, not `openai_api_key` (and honors OPENAI_API_KEY)
    return ChatOpenAI(
        model=model,
        temperature=0.2,
        api_key=api_key,
        base_url=base_url,
        default_headers={
            # Recommended by OpenRouter (helps with rate limits/attribution). Optional for auth.
            "HTTP-Referer": "http://localhost",
            "X-Title": "n8n Copilot MVP",
        },
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


def build_agent(
    n8n_client: N8nClient,
    *,
    model: str | None = None,
    openrouter_api_key: str | None = None,
    openrouter_base_url: str | None = None,
) -> AgentExecutor:
    tools = _make_n8n_tools(n8n_client)

    system = (
        "You are an n8n copilot. You can read workflows and executions, analyze failures, "
        "and suggest JSON snippets for nodes/flows. DO NOT attempt to write or execute workflows. "
        "Use tools when needed. Be concise. When providing JSON, ALWAYS put it in a fenced markdown code block "
        "with language 'json' like:\n\n"
        # Escape curly braces so ChatPromptTemplate doesn't treat them as variables
        "```json\n{{ \"nodes\": [] }}\n```\n\n"
        "If relevant, add a one-line label before the code block. Cite web sources using markdown links named by domain."
    )
    prompt = ChatPromptTemplate.from_messages([
        ("system", system),
        # Optional chat history injected by the UI as a list of BaseMessage
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])

    llm = _get_llm(model_override=model, api_key_override=openrouter_api_key, base_url_override=openrouter_base_url)
    agent = create_tool_calling_agent(llm, tools, prompt)
    return AgentExecutor(agent=agent, tools=tools, verbose=False)


__all__ = ["build_agent"]


