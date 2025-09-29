import os
from typing import Any, Optional
import json
import logging
import difflib

import streamlit as st
import requests
from langchain_core.messages import HumanMessage, AIMessage
from langchain_openai import ChatOpenAI

from n8n_client import N8nClient
from agent import build_agent
from logging_config import setup_logging
"""
Chat UI renders assistant messages with fenced code blocks as copyable snippets,
so a separate JSON snippet generator panel is no longer needed.
"""


APP_TITLE = "n8n Copilot (MVP)"


def init_session_state() -> None:
    # App flow state
    st.session_state.setdefault("page", "connect")  # one of: connect, choose, chat

    # Chat state (multi-chat)
    st.session_state.setdefault("chats", [])  # list of {id, name, messages: [{role, content}]}
    st.session_state.setdefault("active_chat_id", None)

    # n8n connection
    st.session_state.setdefault("n8n_base_url", "")
    st.session_state.setdefault("n8n_api_key", "")
    st.session_state.setdefault("n8n_client", None)
    st.session_state.setdefault("workflows_cache", None)

    # OpenRouter config
    st.session_state.setdefault("openrouter_api_key", os.environ.get("OPENROUTER_API_KEY", ""))
    st.session_state.setdefault("openrouter_model", os.environ.get("OPENROUTER_MODEL", "openai/gpt-5-nano"))
    st.session_state.setdefault("openrouter_base_url", os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"))

    # Agent context (persistent until refreshed)
    st.session_state.setdefault("agent_workflow_id", None)
    st.session_state.setdefault("agent_workflow_json", None)
    st.session_state.setdefault("agent_workflow_diff", None)
    st.session_state.setdefault("agent_execution_json", None)


def _validate_openrouter_inline(base_url: str, api_key: str, model: str) -> None:
    url = (base_url or "https://openrouter.ai/api/v1").rstrip("/") + "/models"
    try:
        r = requests.get(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": "http://localhost",
                "X-Title": "n8n Copilot MVP",
            },
            timeout=15,
        )
        if r.status_code == 401:
            st.error("OpenRouter: 401 Unauthorized. Check API key.")
            return
        r.raise_for_status()
        data = r.json() or {}
        ids = []
        if isinstance(data, dict) and isinstance(data.get("data"), list):
            ids = [x.get("id") for x in data["data"] if isinstance(x, dict)]
        if model and ids and model not in ids:
            st.warning("Connected to OpenRouter, but model not found. Check model id.")
        st.success("OpenRouter connection OK")
    except Exception as exc:  # noqa: BLE001
        st.error(f"OpenRouter validation failed: {exc}")


def page_connect() -> None:
    st.header("Connect to n8n and OpenRouter")
    st.caption("Your keys are not persisted beyond the session.")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("n8n")
        st.session_state["n8n_base_url"] = st.text_input(
            "n8n Base URL",
            value=st.session_state.get("n8n_base_url", ""),
            placeholder="https://your-n8n.example.com",
        )
        st.session_state["n8n_api_key"] = st.text_input(
            "n8n API Key",
            value=st.session_state.get("n8n_api_key", ""),
            type="password",
            placeholder="Paste X-N8N-API-KEY",
        )
        if st.button("Validate n8n"):
            try:
                client = N8nClient(
                    base_url=st.session_state["n8n_base_url"].strip(),
                    api_key=st.session_state["n8n_api_key"].strip(),
                )
                client.test_connection()
                st.session_state["n8n_client"] = client
                st.session_state["workflows_cache"] = None
                st.success("n8n connection OK")
            except Exception as exc:  # noqa: BLE001
                st.session_state["n8n_client"] = None
                if isinstance(exc, requests.HTTPError) and getattr(exc, "response", None) is not None:
                    status = exc.response.status_code
                    if status == 401:
                        st.error(
                            "Connection failed: 401 Unauthorized.\n\n"
                            "Tips:\n- Create or verify an API Key under n8n Settings + API (Public API).\n"
                            "- Use header 'X-N8N-API-KEY' (the app sets this automatically).\n"
                            "- Use your instance root as Base URL (no /rest or /api/v1).\n"
                            "- Ensure Public API is enabled; the app auto-detects /api/v1 vs /rest."
                        )
                    else:
                        st.error(f"Connection failed: HTTP {status}")
                else:
                    st.error(f"Connection failed: {exc}")

    with col2:
        st.subheader("OpenRouter (LLM)")
        st.session_state["openrouter_api_key"] = st.text_input(
            "OpenRouter API Key",
            value=st.session_state.get("openrouter_api_key", ""),
            type="password",
            placeholder="sk-or-v1-...",
        )
        st.session_state["openrouter_model"] = st.text_input(
            "Model",
            value=st.session_state.get("openrouter_model", "openai/gpt-5-nano"),
            placeholder="openai/gpt-5-nano",
        )
        st.session_state["openrouter_base_url"] = st.text_input(
            "OpenRouter Base URL",
            value=st.session_state.get("openrouter_base_url", "https://openrouter.ai/api/v1"),
        )

        if st.button("Validate OpenRouter"):
            _validate_openrouter_inline(
                st.session_state.get("openrouter_base_url", ""),
                st.session_state.get("openrouter_api_key", ""),
                st.session_state.get("openrouter_model", ""),
            )

    ready = bool(st.session_state.get("n8n_client")) and bool((st.session_state.get("openrouter_api_key") or "").strip())
    st.divider()
    if st.button("Continue"):
        if not ready:
            st.warning("Please validate both n8n and OpenRouter first.")
        else:
            st.session_state["page"] = "choose"


def page_choose_workflow() -> None:
    st.header("Choose a Workflow")
    client: Optional[N8nClient] = st.session_state.get("n8n_client")
    if not client:
        st.warning("Please connect to n8n first.")
        if st.button("Back"):
            st.session_state["page"] = "connect"
        return

    if st.session_state.get("workflows_cache") is None:
        try:
            st.session_state["workflows_cache"] = client.list_workflows()
        except Exception as exc:  # noqa: BLE001
            st.error(f"Failed to load workflows: {exc}")
            return

    if st.button("Reload Workflows"):
        try:
            st.session_state["workflows_cache"] = client.list_workflows()
        except Exception as exc:  # noqa: BLE001
            st.error(f"Failed to reload workflows: {exc}")
            return

    workflows = st.session_state.get("workflows_cache")
    workflow_options = []
    id_to_workflow: dict[str, Any] = {}
    payload = workflows.get("data", workflows) if isinstance(workflows, dict) else workflows
    for wf in payload:
        wf_id = str(wf.get("id"))
        name = wf.get("name", f"Workflow {wf_id}")
        label = f"{name} (ID: {wf_id})"
        workflow_options.append(label)
        id_to_workflow[label] = wf

    selection = st.selectbox("Select workflow", workflow_options)

    col_a, col_b = st.columns([0.25, 0.75])
    with col_a:
        if st.button("Use This Workflow") and selection:
            wf_id = str(id_to_workflow[selection].get("id"))
            try:
                wf_json = client.get_workflow(wf_id)
            except Exception as exc:  # noqa: BLE001
                st.error(f"Failed to load workflow: {exc}")
                return
            st.session_state["agent_workflow_id"] = wf_id
            st.session_state["agent_workflow_json"] = wf_json
            st.session_state["agent_workflow_diff"] = None
            st.session_state["agent_execution_json"] = None
            _ensure_active_chat()
            _reset_active_chat_messages()
            st.session_state["page"] = "chat"

    with col_b:
        wf = id_to_workflow.get(selection)
        if wf:
            st.json(wf)


def _minified_json(obj: Any) -> str:
    try:
        return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)
    except Exception:
        return json.dumps(obj)


def _unified_diff(old: Any, new: Any, context_lines: int = 3) -> str:
    try:
        old_s = json.dumps(old, indent=2, ensure_ascii=False).splitlines()
        new_s = json.dumps(new, indent=2, ensure_ascii=False).splitlines()
        diff = difflib.unified_diff(old_s, new_s, lineterm="", n=context_lines)
        return "\n".join(diff)
    except Exception:
        return ""


def page_chat() -> None:
    st.header(APP_TITLE)

    # Top actions bar
    col_a, col_b, col_c, col_d = st.columns(4)
    with col_a:
        if st.button("Back"):
            st.session_state["page"] = "choose"
            return
    with col_b:
        if st.button("Refresh Workflow JSON"):
            client: Optional[N8nClient] = st.session_state.get("n8n_client")
            wf_id = st.session_state.get("agent_workflow_id")
            if client and wf_id:
                try:
                    latest = client.get_workflow(wf_id)
                    prev = st.session_state.get("agent_workflow_json")
                    st.session_state["agent_workflow_diff"] = _unified_diff(prev, latest)
                    st.session_state["agent_workflow_json"] = latest
                    st.success("Workflow refreshed and diff computed.")
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Failed to refresh workflow: {exc}")
    with col_c:
        if st.button("Select Execution"):
            st.session_state["show_exec_picker"] = True
    with col_d:
        if st.button("Clear Execution Context"):
            st.session_state["agent_execution_json"] = None

    # Execution picker section
    if st.session_state.get("show_exec_picker"):
        st.subheader("Pick an execution to add to context")
        client: Optional[N8nClient] = st.session_state.get("n8n_client")
        wf_id = st.session_state.get("agent_workflow_id")
        col1, col2, col3 = st.columns(3)
        with col1:
            status = st.selectbox("Status", ["", "success", "error", "waiting", "running"], key="exec_status")
        with col2:
            limit = st.number_input("Limit", min_value=1, max_value=50, value=20, step=1, key="exec_limit")
        with col3:
            offset = st.number_input("Offset", min_value=0, value=0, step=1, key="exec_offset")

        if st.button("Load Executions", key="exec_load"):
            try:
                executions = client.list_executions(
                    workflow_id=wf_id, status=status or None, limit=int(limit), offset=int(offset)
                )
                st.session_state["exec_list_payload"] = executions
            except Exception as exc:  # noqa: BLE001
                st.error(f"Failed to load executions: {exc}")

        exec_payload = st.session_state.get("exec_list_payload")
        if exec_payload:
            items = exec_payload.get("data", exec_payload) if isinstance(exec_payload, dict) else exec_payload
            labels = []
            id_map = {}
            for ex in items:
                ex_id = str(ex.get("id"))
                estatus = ex.get("status")
                started = ex.get("startedAt") or ex.get("started_at")
                label = f"Execution {ex_id} [{estatus}] {started}"
                labels.append(label)
                id_map[label] = ex_id
            pick = st.selectbox("Choose execution", labels, key="exec_pick")
            if st.button("Use This Execution", key="exec_use") and pick:
                try:
                    ex_json = client.get_execution(id_map[pick])
                    st.session_state["agent_execution_json"] = ex_json
                    st.success("Execution added to chat context.")
                    st.session_state["show_exec_picker"] = False
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Failed to load execution: {exc}")

    # Context summary panel
    with st.expander("Current Agent Context", expanded=False):
        st.write({
            "workflow_id": st.session_state.get("agent_workflow_id"),
            "has_workflow_json": bool(st.session_state.get("agent_workflow_json")),
            "has_execution_json": bool(st.session_state.get("agent_execution_json")),
        })
        if st.session_state.get("agent_workflow_diff"):
            st.text_area("Workflow diff (unified)", st.session_state.get("agent_workflow_diff"), height=200)

    # Sidebar chat list
    with st.sidebar:
        st.subheader("Chats")
        _render_chat_sidebar()

    # Chat transcript for active chat
    chat = _ensure_active_chat()
    for msg in chat["messages"]:
        with st.chat_message(msg["role"]):
            _render_message_content(msg["content"], role=msg["role"]) 

    prompt = st.chat_input("Ask the copilot about this workflow...")
    if prompt:
        # Do not append the user message yet; stream assistant response first
        with st.chat_message("assistant"):
            try:
                client: Optional[N8nClient] = st.session_state.get("n8n_client")
                if not client:
                    reply = "Please connect to your n8n instance first."
                else:
                    or_api_key = (st.session_state.get("openrouter_api_key") or "").strip()
                    if not or_api_key:
                        reply = "Please provide your OpenRouter API Key on the Connect page."
                    else:
                        # Build augmented prompt with persistent context
                        wf_id = st.session_state.get("agent_workflow_id")
                        wf_json = st.session_state.get("agent_workflow_json")
                        wf_diff = st.session_state.get("agent_workflow_diff")
                        ex_json = st.session_state.get("agent_execution_json")

                        context_parts = []
                        if wf_id:
                            context_parts.append(f"Workflow ID: {wf_id}")
                        if wf_json:
                            context_parts.append(f"Workflow JSON: {_minified_json(wf_json)}")
                        if wf_diff:
                            context_parts.append(f"Workflow diff (unified):\n{wf_diff}")
                        if ex_json:
                            context_parts.append(f"Selected execution JSON: {_minified_json(ex_json)}")

                        context_block = ("\n\nContext:\n" + "\n\n".join(context_parts)) if context_parts else ""
                        augmented_prompt = f"{prompt}{context_block}"

                        agent = build_agent(
                            client,
                            model=st.session_state.get("openrouter_model"),
                            openrouter_api_key=st.session_state.get("openrouter_api_key"),
                            openrouter_base_url=st.session_state.get("openrouter_base_url"),
                        )
                        # Prepare chat history for the agent
                        history = _messages_to_langchain(_ensure_active_chat()["messages"])  # list of BaseMessage
                        # Stream tokens; fallback to non-streaming if needed
                        ph = st.empty()
                        full = ""
                        try:
                            for chunk in agent.stream({"input": augmented_prompt, "chat_history": history}, stream_mode="values"):
                                part = chunk.get("output", "") if isinstance(chunk, dict) else str(chunk)
                                if part:
                                    full += part
                                    ph.markdown(full)
                            reply = full or "(No response)"
                        except Exception:
                            result = agent.invoke({"input": augmented_prompt, "chat_history": history})
                            reply = result.get("output", "(No response)")
                            ph.markdown(reply)

                # Now persist both user and assistant messages
                chat = _ensure_active_chat()
                chat["messages"].append({"role": "user", "content": prompt})
                chat["messages"].append({"role": "assistant", "content": reply})
                # Auto-name chat on first exchange
                if not chat.get("name"):
                    chat["name"] = _generate_chat_title(prompt, reply)
            except Exception as exc:  # noqa: BLE001
                err_text = str(exc)
                if "401" in err_text and ("No auth credentials" in err_text or "Unauthorized" in err_text):
                    st.error(
                        "Agent error: 401 Unauthorized. No auth credentials found.\n\n"
                        "Tips:\n- Add a valid OpenRouter API Key on the Connect page.\n"
                        "- If using a custom base URL, ensure it is OpenAI-compatible and the key matches that provider.\n"
                        "- Use 'Validate OpenRouter' to confirm connectivity."
                    )
                else:
                    st.error(f"Agent error: {exc}")


def _render_message_content(content: str, *, role: str) -> None:
    """Render message text, showing fenced code blocks as copyable code.

    - Renders triple-backtick blocks (```lang\n...\n```) using st.code for copy button.
    - Renders the rest as markdown.
    """
    import re

    if not isinstance(content, str) or "```" not in content:
        st.markdown(content)
        return

    # Regex to find fenced code blocks with optional language; non-greedy match for content
    pattern = re.compile(r"```(\w+)?\n(.*?)```", re.DOTALL)
    last_end = 0
    for m in pattern.finditer(content):
        # Render any text before the code block
        pre = content[last_end:m.start()]
        if pre.strip():
            st.markdown(pre)
        lang = (m.group(1) or "").strip()
        code = m.group(2)
        st.code(code, language=lang or None)
        last_end = m.end()
    # Render any trailing text
    tail = content[last_end:]
    if tail.strip():
        st.markdown(tail)


def _ensure_active_chat() -> dict:
    """Ensure a chat exists and return the active chat dict."""
    chats = st.session_state.get("chats", [])
    if not chats:
        chat = {"id": "chat-1", "name": "", "messages": []}
        st.session_state["chats"] = [chat]
        st.session_state["active_chat_id"] = chat["id"]
        return chat
    active_id = st.session_state.get("active_chat_id") or chats[0]["id"]
    st.session_state["active_chat_id"] = active_id
    return next((c for c in chats if c["id"] == active_id), chats[0])


def _reset_active_chat_messages() -> None:
    chat = _ensure_active_chat()
    chat["messages"] = []


def _render_chat_sidebar() -> None:
    chats = st.session_state.get("chats", [])
    if not chats:
        _ensure_active_chat()
        chats = st.session_state["chats"]

    labels = [c.get("name") or f"Untitled {i+1}" for i, c in enumerate(chats)]
    ids = [c["id"] for c in chats]
    if ids:
        current_id = st.session_state.get("active_chat_id", ids[0])
        sel = st.radio(
            "Chats",
            options=ids,
            format_func=lambda cid: labels[ids.index(cid)],
            index=ids.index(current_id),
            label_visibility="collapsed",
        )
        if sel and sel != current_id:
            st.session_state["active_chat_id"] = sel

    if st.button("New Chat"):
        new_id = f"chat-{len(chats)+1}"
        chats.append({"id": new_id, "name": "", "messages": []})
        st.session_state["active_chat_id"] = new_id


def _messages_to_langchain(msgs: list[dict]) -> list:
    lc_msgs = []
    for m in msgs:
        role = m.get("role")
        content = m.get("content", "")
        if role == "user":
            lc_msgs.append(HumanMessage(content=content))
        elif role == "assistant":
            lc_msgs.append(AIMessage(content=content))
    return lc_msgs


def _generate_chat_title(user_text: str, assistant_text: str) -> str:
    try:
        llm = ChatOpenAI(
            model=(st.session_state.get("openrouter_model") or "openai/gpt-5-nano"),
            api_key=(st.session_state.get("openrouter_api_key") or "").strip(),
            base_url=(st.session_state.get("openrouter_base_url") or "https://openrouter.ai/api/v1").strip(),
            temperature=0.0,
        )
        prompt = (
            "You are naming a chat. Generate a concise 3-5 word title, "
            "no quotes, no punctuation, Title Case, based on this exchange.\n\n"
            f"User: {user_text}\nAssistant: {assistant_text}"
        )
        msg = llm.invoke([HumanMessage(content=prompt)])
        title = (getattr(msg, "content", "") or "").strip()
        title = title.replace("\n", " ").strip().strip("\"'")
        return title[:60] or "New Chat"
    except Exception:
        return "New Chat"


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    setup_logging()
    init_session_state()

    page = st.session_state.get("page", "connect")
    if page == "connect":
        page_connect()
    elif page == "choose":
        page_choose_workflow()
    elif page == "chat":
        page_chat()
    else:
        page_connect()


if __name__ == "__main__":
    main()
