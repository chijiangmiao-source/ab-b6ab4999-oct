"""Strict input validation with precise, locatable error messages."""

from __future__ import annotations

from typing import Any

MIN_AXIS, MAX_AXIS = 2, 40
MIN_DEPTH, MAX_DEPTH = 2, 64
MIN_COST, MAX_COST = 0, 1_000_000
MAX_SMOOTHNESS = 1_000_000  # anything >= depth makes the constraint vacuous


class ValidationError(Exception):
    def __init__(self, errors: list[dict]):
        super().__init__("invalid request")
        self.errors = errors


def _err(errors: list[dict], loc: list[str], msg: str) -> None:
    errors.append({"loc": loc, "msg": msg})


def _is_int(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def validate_payload(payload: Any) -> dict:
    errors: list[dict] = []
    if not isinstance(payload, dict):
        raise ValidationError([{"loc": [], "msg": "请求体必须是 JSON 对象"}])

    dims: dict[str, int] = {}
    for name, lo, hi in (
        ("width", MIN_AXIS, MAX_AXIS),
        ("height", MIN_AXIS, MAX_AXIS),
        ("depth", MIN_DEPTH, MAX_DEPTH),
    ):
        v = payload.get(name)
        if not _is_int(v):
            _err(errors, [name], f"{name} 必须是整数")
        elif not lo <= v <= hi:
            _err(errors, [name], f"{name} 必须在 {lo} 到 {hi} 之间，当前为 {v}")
        else:
            dims[name] = v

    s = payload.get("smoothness")
    if not _is_int(s):
        _err(errors, ["smoothness"], "smoothness 必须是整数")
    elif not 0 <= s <= MAX_SMOOTHNESS:
        _err(
            errors,
            ["smoothness"],
            f"smoothness 必须在 0 到 {MAX_SMOOTHNESS} 之间，当前为 {s}",
        )

    if errors:
        raise ValidationError(errors)

    w, h, d = dims["width"], dims["height"], dims["depth"]
    n_col, expected = w * h, w * h * d

    raw_costs = payload.get("costs")
    costs: list[int] | None = None
    if not isinstance(raw_costs, list):
        _err(errors, ["costs"], "costs 必须是数组")
    else:
        if len(raw_costs) != expected:
            _err(
                errors,
                ["costs"],
                f"costs 长度必须为 width*height*depth = {expected}"
                f"（{w}×{h}×{d}），当前为 {len(raw_costs)}",
            )
        else:
            costs = [0] * expected
            for i, v in enumerate(raw_costs):
                if not _is_int(v):
                    _err(
                        errors,
                        ["costs", str(i)],
                        f"代价必须是整数，第 {i} 项为 {v!r}",
                    )
                elif not MIN_COST <= v <= MAX_COST:
                    x, z = divmod(i, d)
                    x, y = x % w, x // w
                    _err(
                        errors,
                        ["costs", str(i)],
                        f"代价必须在 {MIN_COST} 到 {MAX_COST} 之间；"
                        f"体素 (x={x}, y={y}, z={z}) = {v}",
                    )
                else:
                    costs[i] = v

    raw_forbidden = payload.get("forbidden", [])
    forbidden: list[tuple[int, int, int]] = []
    if not isinstance(raw_forbidden, list):
        _err(errors, ["forbidden"], "forbidden 必须是数组")
    else:
        seen: set[tuple[int, int, int]] = set()
        for i, item in enumerate(raw_forbidden):
            loc = ["forbidden", str(i)]
            if (
                not isinstance(item, list)
                or len(item) != 3
                or not all(_is_int(v) for v in item)
            ):
                _err(errors, loc, "禁用项必须是含 3 个整数的数组 [x, y, z]")
                continue
            x, y, z = item
            if not 0 <= x < w:
                _err(errors, loc + ["x"], f"x 必须在 0 到 {w - 1} 之间，当前为 {x}")
            if not 0 <= y < h:
                _err(errors, loc + ["y"], f"y 必须在 0 到 {h - 1} 之间，当前为 {y}")
            if not 0 <= z < d:
                _err(errors, loc + ["z"], f"z 必须在 0 到 {d - 1} 之间，当前为 {z}")
            if 0 <= x < w and 0 <= y < h and 0 <= z < d:
                key = (x, y, z)
                if key in seen:
                    _err(errors, loc, f"禁用体素 ({x}, {y}, {z}) 重复")
                seen.add(key)
                forbidden.append(key)

    if errors:
        raise ValidationError(errors)

    return {
        "width": w,
        "height": h,
        "depth": d,
        "smoothness": s,
        "costs": costs,
        "forbidden": forbidden,
    }
