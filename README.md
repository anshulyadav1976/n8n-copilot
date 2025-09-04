# n8n Copilot (MVP)

Streamlit-based AI copilot for n8n. MVP is read-only: connect to n8n, pick a workflow, chat with persistent context (workflow and optional execution), and generate copyable JSON snippets.

## Quickstart

1) Python 3.11+ recommended
2) Create a virtualenv and install requirements

```bash
pip install -r requirements.txt
```

3) Run the app

```bash
streamlit run streamlit_app.py
```

4) Connect page (no sidebar):
- Enter n8n Base URL (instance root, e.g., `https://your-n8n.example.com`) and n8n API Key (`X-N8N-API-KEY`).
- Enter OpenRouter API Key, Model (e.g., `openai/gpt-5-nano`), and Base URL (`https://openrouter.ai/api/v1`).
- Click “Validate n8n” and “Validate OpenRouter”. When both are OK, click “Continue”.

5) Choose Workflow page:
- Pick a workflow from the list (use “Reload Workflows” to refresh).
- Click “Use This Workflow” to start a new chat with that workflow preloaded.

6) Chat page:
- Persistent context: The agent keeps the selected Workflow JSON (and optionally an Execution) in context; it won’t refresh unless you tell it to.
- Top buttons:
  - “Refresh Workflow JSON” refetches the workflow and computes a unified diff with the previous version, adding the diff to the agent context.
  - “Select Execution” lets you choose a recent execution to add to the agent context for debugging.
  - “Clear Execution Context” removes the execution from the current agent context.
- “Current Agent Context” expander shows what’s currently included (IDs, presence of JSON, and any diff).

## LLM via OpenRouter
- Default provider: OpenRouter (OpenAI-compatible API)
- Set `OPENROUTER_API_KEY` (preferred) or `OPENAI_API_KEY`. The app uses an OpenAI-compatible client.
- Optionally set `OPENROUTER_BASE_URL=https://openrouter.ai/api/v1` (default).
- Configure model with `OPENROUTER_MODEL` or via the Connect page. Default: `openai/gpt-5-nano`.
- To enable built-in web search, use models with web search capability (e.g., `openrouter/auto:online`).
- Docs: https://openrouter.ai/docs/features/web-search

## Features
- Persistent chat context per selected workflow (and optional execution).
- Manual refresh and diff for workflow JSON to avoid slow automatic reruns.
- Execution picker to add/remove an execution to the agent context on demand.
- JSON snippet generator (HTTP Request, Set, IF, and a mini flow) with download buttons.

## References
- n8n Public API: https://docs.n8n.io/api/
- Auth: https://docs.n8n.io/api/authentication/
- Streamlit Chat: https://docs.streamlit.io/library/api-reference/chat
- OpenRouter API: https://openrouter.ai/docs

## Notes
- Provide the instance root as Base URL (not `/rest` or `/api/v1`). The app auto-detects Public API (`/api/v1`) vs legacy REST (`/rest`).
- Ensure Public API is enabled and an API Key is created under Settings → API. 401 Unauthorized typically means the key is invalid/missing or the wrong endpoint is used.
- Keys are not persisted beyond the Streamlit session in this MVP.
- Writing/executing workflows is intentionally disabled in this MVP.
