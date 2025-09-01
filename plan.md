# n8n Copilot — MVP Plan

## Feature Checklist (Iterative, future‑proof)
- [ ] Config & onboarding
  - [ ] Enter and validate `N8N_BASE_URL` and `N8N_API_KEY` (header `X-N8N-API-KEY`)
  - [ ] Persist minimal session config (no long-term storage in MVP)
  - [ ] Select LLM via OpenRouter and set `OPENROUTER_API_KEY`
- [ ] Read-only n8n integration (MVP scope)
  - [ ] List workflows (GET `/rest/workflows`)
  - [ ] View workflow JSON/details (GET `/rest/workflows/{id}`)
  - [ ] List executions with filters (GET `/rest/executions?workflowId=...&status=...&limit=...`)
  - [ ] View execution detail incl. errors (GET `/rest/executions/{id}`)
- [ ] Streamlit UI/UX
  - [ ] Chat-style interface (`st.chat_message`, `st.chat_input`) with history
  - [ ] Side panel: instance status, workflow selector, filters, copy-to-clipboard actions
  - [ ] Read-only workflow diagram preview (JSON-to-graph render)
- [ ] Agentic assistant (read-only actions)
  - [ ] Tools: n8n API reader, RAG retriever, Web search
  - [ ] Summarize workflows, diagnose failed runs, suggest changes
  - [ ] Output copyable JSON snippets for nodes/flows (no write/execute in MVP)
- [ ] RAG over n8n docs
  - [ ] Ingest official n8n docs into a vector store
  - [ ] Source-cited answers and tool recommendations
- [ ] Observability
  - [ ] Basic client logging, error surfaces, and rate-limit handling
- [ ] Security & config
  - [ ] HTTPS-only hints, never log API keys, ephemeral storage
- [ ] Stretch (post-MVP, future‑proof)
  - [ ] Write/edit workflows (POST/PUT `/rest/workflows`)
  - [ ] Execute workflows (POST `/rest/workflows/{id}/run` or via executions endpoint)
  - [ ] Multi-user auth, role-based access, persistent org storage (Postgres)
  - [ ] Fine-grained change previews and diffs
  - [ ] Azure-native deployment hardening

## How It Works (Basic)
- User provides `N8N_BASE_URL` and `N8N_API_KEY`.
- The app validates with a lightweight request.
- Agent tools fetch workflows and executions, analyze errors, and propose JSON edits.
- RAG enriches answers with n8n docs; web search is used when docs lack specifics.
- User copies suggested JSON into n8n UI manually (MVP is read-only).

## Architecture (List)
- UI: Streamlit chat + sidebar for workflow context and controls
- Agent runtime: Python agent framework orchestrating tools
  - Tool: n8n REST client (requests/httpx)
  - Tool: RAG retriever (vector store over n8n docs)
  - Tool: Web search (pluggable: Bing/Brave/Tavily)
- Data
  - App state: in-memory/session; minimal local cache for MVP
  - Vectors: local store for MVP; plan PGVector for production
- Security
  - API key only in memory/session; redact in logs
  - HTTPS strongly recommended (Azure front door/App Service/Container Apps)
- Deployment
  - Local dev (Streamlit)
  - Future: containerize for Azure (self-hosted alongside n8n)

## Tech Stack
- Python 3.11+
- UI: Streamlit chat APIs (`st.chat_message`, `st.chat_input`)
  - Docs: [Streamlit Chat Elements](https://docs.streamlit.io/library/api-reference/chat)
- Agent framework: LangChain Agents (tools + RAG orchestration)
  - Alt: LlamaIndex Agents, CrewAI; choose LangChain for ecosystem maturity
- LLM: OpenRouter gateway (default; configurable to OpenAI/Azure/Anthropic)
  - Docs: [OpenRouter API](https://openrouter.ai/docs)
- HTTP: `httpx` (async) or `requests` (sync) for n8n API
- Vector store (MVP): Chroma (local, SQLite-backed)
  - Docs: [Chroma Usage Guide](https://docs.trychroma.com/usage-guide)
  - Production: Postgres + pgvector
  - Docs: [pgvector Extension](https://github.com/pgvector/pgvector)
- Database: SQLite stored locally for MVP testing; migrate to Postgres later
- Packaging: `poetry` or `pip-tools` (defer install to user preference)

## User Flow
- Open app → enter `N8N_BASE_URL` and `N8N_API_KEY`
- See workflows list → pick a workflow
- View workflow JSON/graph + recent executions
- Ask the copilot:
  - “Why is this failing?” → diagnoses from execution data
  - “How do I add X?” → suggests node(s) + copyable JSON
  - “What does this node do?” → RAG answer with doc citations
- Copy JSON → paste into n8n editor (read-only MVP)

## n8n REST API References
- Public API docs & playground: [n8n API](https://docs.n8n.io/api/)
- Authentication (header `X-N8N-API-KEY`): [Auth Docs](https://docs.n8n.io/api/authentication/)
- Using API playground: [Guide](https://docs.n8n.io/api/using-api-playground/)
- Workflows: `GET /rest/workflows`, `GET /rest/workflows/{id}`
- Executions: `GET /rest/executions`, `GET /rest/executions/{id}`
- Azure self-hosting reference: [Azure Setup](https://docs.n8n.io/hosting/installation/server-setups/azure/)

## Implementation TODO (MVP)
- [ ] Streamlit scaffold: `streamlit_app.py`, basic chat UI, sidebar
- [ ] Config forms: base URL + API key; ephemeral session storage
- [ ] Configure OpenRouter LLM provider (env, base URL `https://openrouter.ai/api/v1`)
- [ ] n8n client (read-only): workflows, workflow by id, executions, execution by id
- [ ] UI: workflows list + detail JSON/graph, executions list + detail view
- [ ] Agent: LangChain tools for n8n client, RAG retriever, web search
- [ ] RAG: ingest official n8n docs into local Chroma; cite sources
- [ ] Suggestions: generate copyable JSON for node/flow edits
- [ ] Observability: logging, error toasts, retry/backoff, rate-limit handling
- [ ] Security: key redaction, HTTPS guidance, no key in logs
- [ ] README and env example; requirements/poetry config
- [ ] Plan migration: Postgres + pgvector (production)
 - [ ] Use local SQLite file for MVP (e.g., `./data/app.db`)


