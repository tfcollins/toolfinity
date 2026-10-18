# toolfinity

A fork of [tracefinity/tracefinity](https://github.com/tracefinity/tracefinity) that uses Claude and Codex, through [HAL](https://github.com/tfcollins/hal), to check, name and size traced tools, and that lets you add extra reference photos per trace.

Upstream's README and docs still describe everything else. This file covers only what the fork adds and how to keep it in step with upstream.

## What it adds

- **`hal-assist` tracer.** Claude and Codex answer in text, so they can't draw a mask. Instead:
  - each local model in `TOOLFINITY_ASSIST_BASE_TRACERS` produces a candidate mask
  - every candidate is drawn as a numbered overlay
  - the model picks the best candidate, names each tool, and flags merged or missed tools in the logs
  - if HAL is down, the first candidate comes back with `tool N` labels, so a trace never fails because of the LLM
- **Reference photos.** Up to 6 extra photos per session: side view, another angle, or close-up. The paper-scaled photo stays the only geometry source. The reference photos go to the model alongside it.
- **Depth estimates.** Given a side view, the model estimates each tool's thickness:
  - estimates at or above `TOOLFINITY_DEPTH_MIN_CONFIDENCE` are stored as thickness + `TOOLFINITY_DEPTH_CLEARANCE_MM`
  - each stored estimate becomes the tool's default pocket depth (`PlacedTool.depth_override`) when the tool is first placed in a bin
  - the trace page lists the estimates, and you can still change the depth in the bin editor
- **`TOOL_LABEL_PROVIDER=hal`.** Names the tools from any tracer with one HAL call per tool.

HAL runs these calls through its tool-less `/v1/chat/completions` endpoint:
- Claude runs with no tools or MCP servers.
- Codex runs in a read-only sandbox with apps, shell and plugins off.

Text in a photo therefore can't make the model act on the HAL host. See [docs/fork/hal.md](docs/fork/hal.md).

## Setup

1. On HAL, set `HAL_VISION_API_KEY`. HAL needs the `/v1` endpoint (tfcollins/hal#299).
2. `cp deploy/toolfinity.env.example deploy/toolfinity.env` and fill in `TOOLFINITY_HAL_URL` and `TOOLFINITY_HAL_API_KEY`.
3. `docker compose -f docker-compose.yaml -f docker-compose.fork.yaml up -d`

Set `TRACERS` explicitly. List more than one tracer, so the trace step (where reference photos are added) appears before tracing starts. With a single tracer, upstream traces as soon as the corners are set.

## Layout

All fork code lives in new paths:

| Path | What |
|-|-|
| `backend/app/fork/` | settings (`TOOLFINITY_*`), HAL client, namer, `hal-assist` tracer, reference photo store, depth sidecar, `/api/fork` routes |
| `backend/app/fork/hooks.py` | the only names upstream modules import |
| `backend/tests/fork/` | backend tests |
| `frontend/src/fork/` | reference photo panel, depth estimates, fork API client, tests |
| `deploy/`, `docker-compose.fork.yaml` | fork deployment |
| `.github/workflows/upstream-sync.yml` | weekly upstream merge |
| `docs/fork/` | fork docs |

Storage:
- `<user>/processed/<session>_refs/`: reference photos plus their `refs.json` index. Deleted with the session.
- `<user>/fork/depth_estimates.json`: depth estimates, keyed by polygon id.

## Hooks into upstream files

Every line that touches an upstream file ends in `toolfinity`. To list them all, run `git grep -n toolfinity -- ':!backend/app/fork' ':!frontend/src/fork' ':!FORK.md' ':!docs/fork'`.

| File | Hook |
|-|-|
| `backend/app/services/tool_namer.py` | `provider == "hal"` branch in `create_tool_namer` |
| `backend/app/services/tracer_registry.py` | import plus `**FORK_TRACER_LABELS` in `TRACER_LABELS` |
| `backend/app/api/routes.py` | `from app.fork import hooks as fork`; fork tracer in `_get_tracer`; depth default in `_build_bin_from_tools`; reference photo cleanup in `delete_session` |
| `backend/app/main.py` | `include_router(fork_router)` |
| `frontend/src/app/trace/[id]/page.tsx` | `<ForkTracePanel …/>` and its import |
| `frontend/src/components/ToolBrowser.tsx` | `depth_override: await depthOverrideFor(tool.id)` and its import |
| `Dockerfile` | nginx `/api/` `proxy_read_timeout` raised from 120s to 300s |
| `.gitignore` | `deploy/toolfinity.env` |

## Syncing upstream

Branches:
- `upstream-main` mirrors `tracefinity/tracefinity@main` and never gets fork commits.
- `main` is upstream plus the fork. Upstream is merged into it, never rebased.

`upstream-sync.yml` runs every Monday, and can be started by hand. It refreshes `upstream-main` and then merges it into a `sync/upstream-<date>` branch:
- **Clean merge:** opens a PR, so CI runs on the result.
- **Conflict:** opens an issue listing the conflicting files, because a conflicted PR never triggers CI.

To resolve by hand:

```sh
git fetch upstream
git checkout -b sync/upstream-manual origin/main
git merge upstream/main          # conflicts should only be in hook lines above
git grep -n toolfinity           # check every hook survived
cd backend && python -m pytest && ruff check .
cd ../frontend && pnpm test && pnpm run lint && pnpm exec tsc --noEmit
git push -u origin sync/upstream-manual   # then open a PR against tfcollins/toolfinity main
```

If upstream renames `_get_tracer`, `create_tool_namer`, `_build_bin_from_tools` or the trace page sidebar, move the hook. Don't copy upstream code into `fork/`.
