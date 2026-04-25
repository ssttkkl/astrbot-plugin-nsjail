# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AstrBot plugin that provides secure code execution via nsjail sandboxing. Registers an `execute_shell` LLM tool so AI agents can run shell commands in isolated per-session sandboxes.

## Architecture

### Key Files

- `main.py` — Plugin entry point. Reads config, builds `SandboxConfig`, instantiates `SandboxManager`, registers `ExecuteShellTool` and helper LLM tools (`send_sandbox_image`, `send_sandbox_file`). Also hooks `on_llm_request` to strip the Computer Use notice from system prompts.
- `sandbox_config.py` — Pure dataclass holding all sandbox parameters. `skills_dir` property derives the AstrBot skills path from `data_dir`.
- `sandbox_manager.py` — Core logic. Manages per-session sandbox lifecycle (create/destroy), builds and executes nsjail commands, detects Cgroup V2 availability at init, cleans up stale sandboxes on startup.
- `pkg/Dockerfile` — The only active Dockerfile (root `Dockerfile` was removed). Used by GitHub Actions (`.github/workflows/`). Builds the AstrBot image with nsjail, ffmpeg, pipx, and Python tooling pre-installed.

### Sandbox Lifecycle

1. First `execute_in_sandbox(session_id, ...)` call creates a workspace dir and a session-isolated `/tmp` dir on the host.
2. nsjail is invoked with bindmounts: `/workspace` (rw), `/data` (configurable), `/tmp` (session-isolated), AstrBot temp dir (ro, for user-uploaded files), host `/usr` `/bin` `/lib` (ro).
3. `destroy_sandbox(session_id)` removes both dirs. `cleanup_all_sandboxes()` runs at startup.

### Timeout Layers

`LLM-supplied timeout` → capped by `tool.timeout_seconds` (= `max_timeout`) → passed to nsjail `--time_limit` → `asyncio.wait_for` with `timeout + 5s` buffer.  
`-1` means unlimited at every layer.

### Cgroup V2

`SandboxManager.__init__` calls `_check_cgroup()`. If unavailable, `memory_limit_mb` and `cpu_limit_percent` are reset to `-1` so nsjail doesn't attempt cgroup flags.

### Write Permissions

`data_write_permission` and `skills_write_permission` accept `"all"` / `"admin"` / `"none"`. Admin check uses `event.is_admin()` at call time, not at init.

## Development Notes

- No test runner is configured. Manual testing requires a running AstrBot instance with nsjail installed.
- Docker deployment requires `SYS_ADMIN` + `NET_ADMIN` caps and `/sys/fs/cgroup` mounted rw for Cgroup V2.
- Playwright/Chromium crashes inside nsjail (SIGTRAP) — not supported.
- The plugin suppresses AstrBot's built-in Computer Use notice via `on_llm_request` hook so the LLM doesn't see conflicting tool instructions.
