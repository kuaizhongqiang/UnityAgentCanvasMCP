# CODEBUDDY.md

This file provides guidance to CodeBuddy Code when working with code in this repository.

## Project Status

📦 **M1 complete — Python CLI/MCP Server implemented.** All design docs are complete. The Python codebase in `CLI/` is fully written. Unity C# (`Assets/`) remains to be implemented (not in this repo).

## Architecture

```
Agent ← MCP (stdio) → MCP Server (Python) ← HTTP/WS :3748 → Unity (EmbedIO)
                              │
                         Embedding Engine (LM Studio + Qwen3-0.6B)
```

**Three-layer architecture:**
1. **Agent Layer** — LLM calls MCP tools via stdio
2. **MCP Layer** — Python MCP Server: command orchestration, Embedding search, receipt matching, retry
3. **Unity Layer** — `GlobalCLIMgr.cs` runs EmbedIO HTTP/WS on port 3748, dispatches commands to main thread

## Repository Structure

| Path | Content |
|:--|:--|
| `docs/` | 11 design documents (see Design Docs Reference below) |
| `CLI/` | **M1 complete** — Python source: `cli_core.py`, `mcp_server.py`, `embedding_client.py`, `main.py`, `build.py` |
| `Assets/` | **In MCV_Module submodule** — Unity C# code lives there, not here |

## Git Submodule Relationship

This repo is embedded as a submodule in MCV_Module at `MCV_Module/AgentCanvas/`.

| Content | Edit Here | Edit in MCV_Module |
|:--|:--:|:--:|
| Design docs (`docs/`) | ✅ | ❌ |
| Python CLI source (`CLI/`) | ✅ | ❌ |
| GlobalCLIMgr.cs (Unity C#) | ❌ | ✅ |

**Never** put `.cs` files in this repo. **Never** edit MCV_Module's submodule copy directly.

Sync command (run in MCV_Module root):
```bash
cd AgentCanvas && git pull origin main && cd .. && git add AgentCanvas && git commit -m "sync AgentCanvas"
```

## Key Design Decisions

1. **外挂架构**: CLI+MCP is an independent module. Does not migrate existing UGUI+MVC code. Both systems share only the DataBase data layer.
2. **Search-data decoupling**: `search.data` returns IDs + `knowledgeOriginal` anchors; `get.data` fetches full content by ID.
3. **Agent commands → Unity actions**: 5 command categories, 20 commands total. See `docs/Commands.md`.
4. **Template system**: 3 layouts × 10 element types, data-bound, no Agent-generated UI. See `docs/UI-Templates.md`.
5. **session renamed to dialog** to avoid confusion with LLM sessions.
6. **Interactive feedback**: Objective questions complete in one MCP round-trip via `result.show`; subjective questions require Agent evaluation. Interaction callbacks carry `correctAnswer` + `explanation`.
7. **Grading field**: `auto` for objective questions, `agent` for subjective questions.
8. **Full logging**: CLI sends/receives logged to `logs/dialog_{id}.jsonl`, feedable back to Embedding index.

## Build Process

```bash
cd CLI
pip install -r requirements.txt   # pyinstaller, mcp, httpx, websockets, numpy, python-dotenv, click
python build.py                   # outputs cli.exe + mcp.exe to Assets/StreamingAssets/CLI/
```

Unity Build automatically packs `Assets/StreamingAssets/CLI/` into build output.

CI (planned): GitHub Actions — Unity Build → CLI Build (setup-python, pip install, build.py) → artifact archive.

## Development Workflow

```bash
cd CLI
cp .env.example .env   # edit token to match Unity Inspector
python main.py help    # test CLI directly
python mcp_server.py   # start MCP Server (production entry point)
```

For Embedding: download Qwen3-Embedding-0.6B via LM Studio, start local service on `localhost:1234`.

`cli.exe` (from `main.py`) is the dev debug tool. `mcp.exe` (from `mcp_server.py`) is the production MCP Server Unity launches as a child process.

## Environment Config (`.env`)

```env
CLI_PORT=3748
CLI_TOKEN=your_secret_token
LM_STUDIO_HOST=localhost
LM_STUDIO_PORT=1234
EMBEDDING_MODEL=Qwen3-Embedding-0.6B
KNOWLEDGE_PATH=./knowledge_docs/
TOP_N=5
HTTP_TIMEOUT=5
COMMAND_TIMEOUT=30
LOG_LEVEL=INFO
```

Token is shared key between Unity Inspector (`[SerializeField] token`) and `.env`. Auth via `Authorization: Bearer` header (HTTP) or `?token=` query param (WebSocket). localhost-only security boundary.

## Testing Strategy

- **Unit**: pytest for Python (`cli_core`, `embedding_client`), Unity Test Framework (Edit Mode) for `GlobalCLIMgr`
- **Integration**: MCP Server ↔ Unity HTTP/WS, batch queue, reconnect
- **E2E**: Full Agent → MCP Server → Unity chain
- **Mock without LM Studio**: `search.data` degrades to keyword match
- **Mock without Unity**: Python HTTP mock server for `/cmd` and WS receipts

## Command Categories (5 categories, 20 commands)

| Category | Commands |
|:--|:--|
| Help | `help`, `docs` |
| Query | `whoami`, `dialog`, `page.list`, `list.templates`, `search.data`, `get.data`, `usage` |
| Page | `page.create`, `run`, `update`, `clear`, `result.show`, `page.delete`, `stop` |
| Queue | `queue` |
| Config | `init`, `restart` |

Page templates (Phase 1): `knowledge_card`, `step_guide`, `quiz`, `compare`, `explore` (3 planned for Phase 1).

## Design Docs Reference

| Doc | Content |
|:--|:--|
| `docs/README.md` | System overview, architecture, tech stack, doc index |
| `docs/Architecture.md` | Component diagram, thread model, GlobalCLIMgr lifecycle |
| `docs/Commands.md` | All 20 commands, params, error codes, page config JSON schema |
| `docs/MCP-Tools.md` | MCP tool schemas (snake_case versions of dot-notation commands) |
| `docs/Protocol.md` | HTTP API, WebSocket events, receipt matching, timeout/retry |
| `docs/Data-Model.md` | DataBase.description field, search response format, init config |
| `docs/UI-Templates.md` | 3 layouts, 10 element types, callback mechanism, USS pitfalls |
| `docs/Embedding.md` | RAG architecture, Qwen3-0.6B, LM Studio setup, index strategy |
| `docs/Build-Deploy.md` | PyInstaller config, Unity build integration, CI pipeline |
| `docs/Security.md` | Token auth, `.env` config, localhost-only security boundary |
| `docs/Testing.md` | Test pyramid, mock strategies, pytest + Unity Test Framework |
| `docs/Debugging.md` | Log levels, key log points, manual test commands, troubleshooting |
