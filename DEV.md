# Development Server Guide

## Quick Start

Both servers must be started from their respective directories. Use `setsid` + `exec`
so processes survive the parent shell — `nohup` does **not** work in this Termux environment.

### Backend (FastAPI, port 8000)

```bash
setsid bash -c 'cd /root/LotteryIntelligencePlatform/backend && exec .venv/bin/uvicorn backend.app.main:create_app --factory --host 127.0.0.1 --port 8000 > /tmp/opencode/backend.log 2>&1' &
```

- Uses the project's own `.venv` inside `backend/` — **not** the system Python.
- The `uvicorn` binary in `backend/.venv/bin/` has a broken shebang (`python3.13`); always use `.venv/bin/uvicorn` (the wrapper script), or invoke via `python -m uvicorn` from within the venv.
- API docs: `http://127.0.0.1:8000/docs`
- Logs: `/tmp/opencode/backend.log`

### Frontend (Vite, port 5173)

```bash
setsid bash -c 'cd /root/LotteryIntelligencePlatform/frontend && exec npm run dev > /tmp/opencode/frontend.log 2>&1' &
```

- Logs: `/tmp/opencode/frontend.log`

## Check Status

```bash
curl -s -o /dev/null -w "Backend → %{http_code}\n" http://127.0.0.1:8000/docs
curl -s -o /dev/null -w "Frontend → %{http_code}\n" http://localhost:5173
pgrep -fa "uvicorn backend.app.main"
pgrep -fa "vite"
```

## Stop Servers

**Do not use `pkill -f`** — it hangs in this Termux environment. Use `kill` with PIDs:

```bash
kill $(pgrep -f "uvicorn backend.app.main")
kill $(pgrep -f "vite")
```

If a process doesn't die, use `-9`:

```bash
kill -9 $(pgrep -f "uvicorn backend.app.main")
kill -9 $(pgrep -f "vite")
```

## Known Issues

| Issue | Detail | Workaround |
|-------|--------|------------|
| `pkill -f` hangs | Termux `pkill` matches its own shell and blocks indefinitely | Use `pgrep` to list PIDs, then `kill <pid>` |
| `nohup ... &` dies | Background processes are killed when the parent shell exits | Use `setsid bash -c 'exec ...' &` to detach into a new session |
| `uvicorn` binary shebang | `backend/.venv/bin/uvicorn` shebang points to `python3.13` which may not exist at `/data/data/com.termux/files/usr/bin/python3.13` | Use the wrapper script directly: `.venv/bin/uvicorn` (not the raw binary) or `python -m uvicorn` |
| Backend import delay | First import of `backend.app.main` can take 5–10s (torch, scikit-learn) | Normal; give uvicorn 8–10s after launch before checking |
