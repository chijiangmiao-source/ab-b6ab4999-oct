"""FastAPI application: exact OCT surface solver audit console."""

from __future__ import annotations

import os
import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .native_bridge import solve_exact
from .validation import ValidationError, validate_payload

app = FastAPI(
    title="OCT Surface Audit Console",
    description="Exact integer minimum-cost OCT surface with proof of optimality.",
    version="1.0.0",
)


@app.exception_handler(ValidationError)
async def validation_error_handler(_: Request, exc: ValidationError):
    return JSONResponse(
        status_code=422,
        content={"ok": False, "errors": exc.errors},
    )


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/solve")
async def api_solve(request: Request):
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse(
            status_code=422,
            content={
                "ok": False,
                "errors": [{"loc": [], "msg": "请求体不是合法的 JSON，请检查括号、逗号与引号"}],
            },
        )
    data = validate_payload(payload)

    started = time.perf_counter()
    result, engine = solve_exact(
        width=data["width"],
        height=data["height"],
        depth=data["depth"],
        smoothness=data["smoothness"],
        costs=data["costs"],
        forbidden=data["forbidden"],
    )
    elapsed_ms = round((time.perf_counter() - started) * 1000, 3)

    return {
        "ok": True,
        "feasible": result["feasible"],
        "total_cost": result["total_cost"],
        "canonical": result["canonical"],
        "optional_depths": result["optional_depths"],
        "unique": result["unique"],
        "dimensions": {
            "width": data["width"],
            "height": data["height"],
            "depth": data["depth"],
        },
        "smoothness": data["smoothness"],
        "forbidden_count": len(data["forbidden"]),
        "min_violations": result.get("min_violations"),
        "witness": result.get("witness"),
        "solver": "exact-integer-mincut",
        "engine": engine,
        "elapsed_ms": elapsed_ms,
    }


# Mounted last so API routes take precedence: serve the built UI at /.
_STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_STATIC_DIR):
    app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="static")
