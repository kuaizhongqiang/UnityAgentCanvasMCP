# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Status

📦 **M1 complete — Python CLI/MCP Server implemented.** All design docs are complete. The Python codebase in `CLI/` is fully written (2,350 lines across 6 files). Unity C# (`Assets/`) and the MCV_Module submodule remain to be implemented.

## What This Project Is

AgentCanvas is an MCP toolset that lets an AI Agent drive Unity UI Toolkit via natural language — search data, pick templates, compose pages, and render teaching content in real time.

```
Agent ← MCP (stdio) → MCP Server (Python) ← HTTP/WS :3748 → Unity (EmbedIO)
                              │
                         Embedding Engine (LM Studio + Qwen3-0.6B)
```

## Repository Structure

| Path | Content |
|:--|:--|
| `docs/` | 11 design documents covering all aspects of the system |
| `CLI/` | **M1 complete** — Python source: cli_core.py, mcp_server.py, embedding_client.py, main.py, build.py (2,350 lines) |
| `Assets/` | **In MCV_Module submodule** — Unity C# code lives there, not here |
| `CODEBUDDY.md` | Additional project guidance (keep in sync with this file) |

## ⚠️ Critical: Two-Project Awareness

**Every git operation in this repo must consider both projects simultaneously.** This repo is a git submodule embedded in [MCV_Module](https://github.com/kuaizhongqiang/MCV_Module) at `MCV_Module/AgentCanvas/`. Any change here has downstream consequences there.

### Editing Boundaries

| Content | Edit Here | Edit in MCV_Module |
|:--|:--:|:--:|
| Design docs (`docs/`) | ✅ | ❌ |
| Python CLI source (`CLI/`) | ✅ | ❌ |
| GlobalCLIMgr.cs (Unity C#) | ❌ | ✅ |
| `.cs` files of any kind | ❌🚫 | ✅ |

**Cardinal rule**: Never put `.cs` files in this repo. Never edit MCV_Module's submodule copy directly.

### Workflow: Two-Project Sync

```
You commit/push here (AgentCanvas)
  → MCV_Module must update its submodule pointer
    → cd MCV_Module/AgentCanvas && git pull origin main
      → cd MCV_Module && git add AgentCanvas && git commit -m "sync AgentCanvas"
        → git push MCV_Module
```

**Before pushing** to this repo, consider: does MCV_Module need the latest submodule pointer updated to match? If yes, the two-project sync must happen.

### Common Scenarios

| You do this... | ...then MCV_Module needs | When |
|:--|:--|:--|
| Push new docs or CLI code to `main` | Submodule pointer update | On next MCV_Module build |
| Create a branch here for experimental changes | No action needed | Branch not referenced |
| Tag a release here | Submodule pointer update + possibly pull new .exe artifacts | For consumption |

### Local Dev Tip

If you need to test changes in both repos simultaneously, clone them side-by-side (not as submodule) and symlink or copy. The submodule path is only for committed/pushed states.

## Three-Layer Architecture

1. **Agent Layer** — LLM calls MCP tools via stdio
2. **MCP Layer** — Python MCP Server: command orchestration, Embedding search, receipt matching, retry
3. **Unity Layer** — `GlobalCLIMgr.cs` runs EmbedIO HTTP/WS on port 3748, dispatches commands to main thread

Key architectural decisions:
- **外挂架构**: No migration of existing UGUI+MVC code. Two UI systems share only the DataBase data layer.
- **Search-data decoupling**: `search.data` returns IDs + `knowledgeOriginal` anchors; `get.data` fetches full content by ID.
- **Agent commands → Unity actions**: 5 command categories, 20 commands total (see `docs/Commands.md`).
- **Template system**: 3 layouts × 10 element types, data-bound, no Agent-generated UI (see `docs/UI-Templates.md`).
- **CLI debugging vs production**: `cli.exe` (from `main.py`) is the dev CLI; `mcp.exe` (from `mcp_server.py`) is the production MCP Server started by Unity.

## Build Process

### Python → PyInstaller
```bash
cd CLI
pip install -r requirements.txt
python build.py    # outputs cli.exe + mcp.exe to Assets/StreamingAssets/CLI/
```

Planned `requirements.txt` deps: `pyinstaller`, `mcp`, `httpx`, `websockets`, `numpy`, `python-dotenv`, `click`.

### Unity Build
Unity Build automatically packs `Assets/StreamingAssets/CLI/` into build output.

### CI (planned)
GitHub Actions: Unity Build → CLI Build (setup-python, pip install, build.py) → artifact archive.

## Development

```bash
# Local dev (no PyInstaller)
cd CLI
cp .env.example .env   # edit token
python main.py help    # test CLI directly
python mcp_server.py   # start MCP Server

# LM Studio for Embedding
# Download Qwen3-Embedding-0.6B, start local service on localhost:1234
```

## Key Design Docs

| Doc | What's In It |
|:--|:--|
| `docs/Architecture.md` | Component diagram, thread model, GlobalCLIMgr lifecycle |
| `docs/Commands.md` | All 20 commands, params, error codes, page config JSON schema |
| `docs/MCP-Tools.md` | MCP tool schemas (snake_case versions of dot-notation commands) |
| `docs/Protocol.md` | HTTP API, WebSocket events, receipt matching, timeout/retry |
| `docs/Data-Model.md` | DataBase.description field, search response format, page/init config |
| `docs/UI-Templates.md` | 3 layouts, 10 element types, callback mechanism, USS pitfalls |
| `docs/Embedding.md` | RAG architecture, Qwen3-0.6B, LM Studio setup, index strategy |
| `docs/Build-Deploy.md` | PyInstaller config, Unity build, CI pipeline, env setup |
| `docs/Security.md` | Token auth, `.env` config, localhost-only security boundary |
| `docs/Testing.md` | Test pyramid, mock strategies, pytest + Unity Test Framework |
| `docs/Debugging.md` | Log levels, key log points, manual test commands, troubleshooting |

## Testing Strategy (planned)

- **Unit**: pytest for Python (`cli_core`, `embedding_client`), Unity Test Framework (Edit Mode) for `GlobalCLIMgr`
- **Integration**: MCP Server ↔ Unity HTTP/WS, batch queue, reconnect
- **E2E**: Full Agent → MCP Server → Unity chain
- **Mock without LM Studio**: `search.data` degrades to keyword match
- **Mock without Unity**: Python uses HTTP mock server for `/cmd` and WS receipts

## Environment Config (`.env`)

```
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

Token is shared key between Unity Inspector and `.env`. Auth via `Authorization: Bearer` header (HTTP) or `?token=` query param (WebSocket).
