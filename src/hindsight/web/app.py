"""FastAPI app for hindsight serve.

Routes:
    GET  /                              browse traces under --root
    GET  /show?path=<rel>                tree + stats
    GET  /diff                           picker form
    GET  /diff/result?a=&b=&strict=     diff page
    GET  /replay?path=<rel>              replay form
    POST /replay                         execute (mock) → redirect to /show
    GET  /api/run?path=<rel>             JSON canonical
    GET  /api/stats?path=<rel>           JSON stats
    GET  /api/diff?a=&b=&strict=        JSON diff
    GET  /static/style.css              served by StaticFiles

In-memory `_REPLAY_CACHE: dict[token -> jsonl_text]` lets /show render
replayed runs without writing to disk. The `:replay:<token>` path
prefix routes around the filesystem-resolution path.
"""

from __future__ import annotations

import json
import secrets
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ..base import auto_ingest
from ..canonical import TraceRun
from ..diff import diff as diff_runs
from ..replay import MockProvider, replay
from ..stats import stats as compute_stats
from .render import render_tree

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_STATIC_DIR = Path(__file__).parent / "static"

_REPLAY_CACHE: dict[str, str] = {}
_REPLAY_PREFIX = ":replay:"


def _resolve_in_root(root: Path, rel: str) -> Path:
    """Resolve `rel` against `root`; reject anything that escapes."""
    if not rel:
        raise HTTPException(400, "path is required")
    candidate = (root / rel).resolve()
    root_resolved = root.resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise HTTPException(400, f"path escapes root: {rel!r}") from exc
    if not candidate.is_file():
        raise HTTPException(404, f"not found: {rel!r}")
    return candidate


def _load_run(root: Path, rel: str) -> TraceRun:
    """Resolve `rel` to a TraceRun. Handles both filesystem paths
    (bounded by `root`) and `:replay:<token>` in-memory tokens.
    """
    if rel.startswith(_REPLAY_PREFIX):
        token = rel[len(_REPLAY_PREFIX):]
        text = _REPLAY_CACHE.get(token)
        if text is None:
            raise HTTPException(404, f"replay token expired or unknown: {token!r}")
        return TraceRun.from_jsonl(text)
    return auto_ingest(_resolve_in_root(root, rel))


def _list_trace_files(root: Path) -> list[str]:
    """Return relative paths of all .jsonl/.json files under root."""
    out: list[str] = []
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.suffix in {".jsonl", ".json"}:
            out.append(str(p.relative_to(root)))
    return out


def create_app(root: Path) -> FastAPI:
    """Build a FastAPI app bound to `root` (the trace browse directory)."""
    root = root.resolve()
    if not root.is_dir():
        raise ValueError(f"--root must be a directory: {root}")

    app = FastAPI(title="Hindsight", docs_url=None, redoc_url=None)
    templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    # ----- HTML routes ------------------------------------------------

    @app.get("/", response_class=HTMLResponse)
    def browse(request: Request) -> Any:
        return templates.TemplateResponse(
            request, "browse.html",
            {"files": _list_trace_files(root), "root": str(root)},
        )

    @app.get("/show", response_class=HTMLResponse)
    def show(request: Request, path: str) -> Any:
        run = _load_run(root, path)
        return templates.TemplateResponse(
            request, "show.html",
            {
                "path": path,
                "tree_html": render_tree(run),
                "stats": compute_stats(run),
                "is_replay": path.startswith(_REPLAY_PREFIX),
                "step_ids": [s.id for s in run.steps],
            },
        )

    @app.get("/diff", response_class=HTMLResponse)
    def diff_picker(request: Request) -> Any:
        return templates.TemplateResponse(
            request, "diff_picker.html",
            {"files": _list_trace_files(root)},
        )

    @app.get("/diff/result", response_class=HTMLResponse)
    def diff_result(request: Request, a: str, b: str, strict: bool = False) -> Any:
        run_a = _load_run(root, a)
        run_b = _load_run(root, b)
        d = diff_runs(run_a, run_b, strict=strict)
        # Pre-compute the diverged field's value from each side so the
        # template doesn't have to do attribute access on TraceStep objects.
        a_val = b_val = None
        if d.first_divergent_field:
            if d.first_divergent_a is not None:
                a_val = getattr(d.first_divergent_a, d.first_divergent_field, None)
            if d.first_divergent_b is not None:
                b_val = getattr(d.first_divergent_b, d.first_divergent_field, None)
        a_val_json = json.dumps(a_val, indent=2, sort_keys=True, default=str) if a_val is not None else None
        b_val_json = json.dumps(b_val, indent=2, sort_keys=True, default=str) if b_val is not None else None
        return templates.TemplateResponse(
            request, "diff_result.html",
            {
                "a": a, "b": b, "strict": strict, "d": d,
                "a_val_json": a_val_json, "b_val_json": b_val_json,
            },
        )

    @app.get("/replay", response_class=HTMLResponse)
    def replay_picker(request: Request, path: str) -> Any:
        run = _load_run(root, path)
        steps = [(s.id, s.name, s.kind.value) for s in run.steps]
        return templates.TemplateResponse(
            request, "replay_picker.html",
            {"path": path, "steps": steps},
        )

    @app.post("/replay")
    def replay_post(
        path: str = Form(...),
        from_step: str = Form(...),
        model: str = Form(""),
    ) -> Any:
        run = _load_run(root, path)
        # Mock-only on the web path. Live providers stay CLI-only for now.
        model_override = model.strip() or None
        replayed = replay(
            run,
            from_step,
            provider=MockProvider(),
            model=model_override,
        )
        token = secrets.token_urlsafe(8)
        _REPLAY_CACHE[token] = replayed.to_jsonl()
        return RedirectResponse(
            url=f"/show?path={_REPLAY_PREFIX}{token}", status_code=303
        )

    # ----- JSON routes ------------------------------------------------

    @app.get("/api/run")
    def api_run(path: str) -> Any:
        run = _load_run(root, path)
        # to_jsonl is the canonical wire format; re-parse for a JSON
        # response so the client gets a structured array.
        return JSONResponse(
            [json.loads(line) for line in run.to_jsonl().splitlines() if line.strip()]
        )

    @app.get("/api/stats")
    def api_stats(path: str) -> Any:
        return JSONResponse(compute_stats(_load_run(root, path)))

    @app.get("/api/diff")
    def api_diff(a: str, b: str, strict: bool = False) -> Any:
        d = diff_runs(_load_run(root, a), _load_run(root, b), strict=strict)
        return JSONResponse(d.to_dict())

    return app
