"""Bridge to the exact solver engine.

Prefers the compiled native kernel (``native/oct_solver``) for speed and
falls back to the pure-Python implementation in :mod:`app.solver` when the
binary is unavailable.  Both implement the same exact integer min-cut
algorithm and the same residual ambiguity analysis.
"""

from __future__ import annotations

import os
import subprocess
import sys

from . import solver as py_solver

_HERE = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_BIN = os.path.join(_HERE, "..", "native", "oct_solver")
# A forbidden-free surface costs at most n_col * 1_000_000; give the native
# process ample room but never let a request hang the worker forever.
_NATIVE_TIMEOUT = float(os.environ.get("OCT_SOLVER_TIMEOUT", "120"))


class NativeError(RuntimeError):
    pass


def _native_path() -> str | None:
    path = os.environ.get("OCT_SOLVER_BIN", _DEFAULT_BIN)
    return path if os.path.isfile(path) and os.access(path, os.X_OK) else None


def solve_exact(
    width: int,
    height: int,
    depth: int,
    smoothness: int,
    costs: list[int],
    forbidden: list[tuple[int, int, int]],
) -> tuple[dict, str]:
    """Return (result dict, engine name)."""
    binary = _native_path()
    if binary is not None:
        try:
            return _run_native(binary, width, height, depth, smoothness, costs, forbidden), "native-cpp"
        except (NativeError, subprocess.TimeoutExpired, OSError):
            # Deterministic fallback keeps the service correct on any host.
            pass
    result = py_solver.solve(width, height, depth, smoothness, costs, forbidden)
    return result, "python"


def _run_native(binary, w, h, d, smoothness, costs, forbidden) -> dict:
    parts = [f"{w} {h} {d} {smoothness}", " ".join(str(v) for v in costs), str(len(forbidden))]
    parts.extend(f"{x} {y} {z}" for x, y, z in forbidden)
    payload = "\n".join(parts) + "\n"

    proc = subprocess.run(
        [binary],
        input=payload,
        capture_output=True,
        text=True,
        timeout=_NATIVE_TIMEOUT,
    )
    if proc.returncode != 0:
        raise NativeError(proc.stderr.strip() or f"native exit {proc.returncode}")

    lines = proc.stdout.splitlines()
    if not lines:
        raise NativeError("empty native output")
    if lines[0] == "INFEASIBLE":
        result = {
            "feasible": False,
            "total_cost": None,
            "canonical": None,
            "optional_depths": None,
            "unique": None,
            "min_violations": None,
            "witness": None,
        }
        if len(lines) >= 3:
            result["min_violations"] = int(lines[1])
            witness = [int(v) for v in lines[2].split()]
            if len(witness) == w * h:
                result["witness"] = witness
        return result
    if lines[0] != "OK" or len(lines) != w * h + 2:
        raise NativeError(f"malformed native output: {proc.stdout[:200]!r}")

    canonical: list[int] = []
    optional: list[list[int]] = []
    unique = True
    for i in range(1, 1 + w * h):
        z, mask = lines[i].split()
        z = int(z)
        depths = [zi for zi, ch in enumerate(mask) if ch == "1"]
        if not depths:  # pragma: no cover - cannot happen for a min cut
            raise NativeError("column with no attainable depth")
        canonical.append(z)
        optional.append(depths)
        if len(depths) != 1:
            unique = False
    total = int(lines[-1])
    return {
        "feasible": True,
        "total_cost": total,
        "canonical": canonical,
        "optional_depths": optional,
        "unique": unique,
    }


# Imported here so ``python -m app.native_bridge --selftest`` works without
# paying the cost otherwise.  (Kept tiny on purpose.)
if __name__ == "__main__":  # pragma: no cover
    r, engine = solve_exact(2, 1, 3, 1, [1, 0, 1, 0, 1, 0], [])
    print(engine, r)
    sys.exit(0)
