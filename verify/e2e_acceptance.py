#!/usr/bin/env python3
"""One-shot end-to-end acceptance for the OCT surface audit console.

Runs entirely over HTTP against the real FastAPI service (both directly and
through the web reverse proxy).  Exactness is cross-checked with an
independent brute-force enumerator on small random instances.

Exit code: 0 = all checks passed, 1 = at least one failure.
"""

from __future__ import annotations

import itertools
import os
import random
import sys
import time

import httpx

API_BASE = os.environ.get("API_BASE", "http://api:8000").rstrip("/")
WEB_BASE = os.environ.get("WEB_BASE", "http://web:80").rstrip("/")

failures: list[str] = []
checks = 0


def check(cond: bool, name: str, detail: str = "") -> None:
    global checks
    checks += 1
    if cond:
        print(f"  PASS  {name}")
    else:
        failures.append(f"{name}: {detail}")
        print(f"  FAIL  {name}  {detail}")


def section(title: str) -> None:
    print(f"\n=== {title} ===")


def brute(w, h, d, S, costs, forbidden):
    """Independent enumeration: optimum, lex-min surface, optional depths."""
    fset = set(map(tuple, forbidden))
    best, lexmin, optional, n_opt, min_viol = None, None, None, 0, None
    for surf in itertools.product(range(d), repeat=w * h):
        ok = True
        for y in range(h):
            for x in range(w):
                c = y * w + x
                if x + 1 < w and abs(surf[c] - surf[c + 1]) > S:
                    ok = False
                if y + 1 < h and abs(surf[c] - surf[c + w]) > S:
                    ok = False
        if not ok:
            continue
        hits = sum(1 for c, z in enumerate(surf) if (c % w, c // w, z) in fset)
        min_viol = hits if min_viol is None else min(min_viol, hits)
        if hits:
            continue
        val = sum(costs[c * d + surf[c]] for c in range(w * h))
        if best is None or val < best:
            best, lexmin, n_opt = val, list(surf), 0
            optional = [set() for _ in range(w * h)]
        if val == best:
            n_opt += 1
            for c, z in enumerate(surf):
                optional[c].add(z)
            if list(surf) < lexmin:
                lexmin = list(surf)
    if best is None:
        return None, min_viol
    return (best, lexmin, [sorted(s) for s in optional], n_opt == 1), min_viol


def post(base, payload, timeout=120.0):
    return httpx.post(f"{base}/api/solve", json=payload, timeout=timeout)


def wait_health(base: str, label: str, attempts: int = 30) -> bool:
    for i in range(attempts):
        try:
            r = httpx.get(f"{base}/health", timeout=5)
            if r.status_code == 200 and r.json().get("status") == "ok":
                print(f"  {label} healthy after {i + 1} attempt(s)")
                return True
        except httpx.HTTPError:
            pass
        time.sleep(2)
    return False


def main() -> int:
    section("1. health (direct API and through web proxy)")
    check(wait_health(API_BASE, "api"), "api /health reachable")
    check(wait_health(WEB_BASE, "web"), "web proxies /health to api")

    section("2. web serves the built SPA")
    r = httpx.get(WEB_BASE + "/", timeout=10)
    check(r.status_code == 200 and "OCT" in r.text, "GET / returns the audit UI", r.text[:120])
    asset = None
    for token in r.text.split('"'):
        if token.startswith("/assets/") and token.endswith(".js"):
            asset = token
            break
    check(asset is not None, "index.html references hashed JS asset")
    if asset:
        ra = httpx.get(WEB_BASE + asset, timeout=10)
        check(ra.status_code == 200 and len(ra.content) > 1000, "JS asset downloadable via web")

    section("3. exactness against brute force (random small instances)")
    rng = random.Random(20260920)
    shapes = [(2, 2), (3, 2), (2, 3), (3, 3), (4, 2), (2, 4)]
    compared = 0
    infeasible_seen = False
    for (w, h) in shapes:
        for d in (2, 3, 4):
            for S in (0, 1, 2):
                if S >= d:
                    continue
                for trial in range(6):
                    costs = [rng.randint(0, 6) for _ in range(w * h * d)]
                    forbidden = []
                    for v in range(w * h * d):
                        if rng.random() < 0.12:
                            x, z = divmod(v, d)
                            forbidden.append([x % w, x // w, z])
                    payload = dict(width=w, height=h, depth=d, smoothness=S,
                                   costs=costs, forbidden=forbidden)
                    resp = post(API_BASE, payload)
                    check(resp.status_code == 200, f"solve {w}x{h}x{d} S={S} HTTP 200",
                          resp.text[:200])
                    j = resp.json()
                    expected, min_viol = brute(w, h, d, S, costs, forbidden)
                    if expected is None:
                        infeasible_seen = True
                        check(j["feasible"] is False, f"{w}x{h}x{d} infeasible detected")
                        check(j.get("min_violations") == min_viol,
                              f"{w}x{h}x{d} min forbidden violations = {min_viol}",
                              f"got {j.get('min_violations')}")
                        wit = j.get("witness") or []
                        hits = sum(
                            1 for c, z in enumerate(wit)
                            if (c % w, c // w, z) in set(map(tuple, forbidden)))
                        check(hits == min_viol and len(wit) == w * h,
                              f"{w}x{h}x{d} witness surface hits exactly {min_viol} forbidden")
                        continue
                    best, lex, opts, unique = expected
                    check(j["feasible"] is True, f"{w}x{h}x{d} feasible")
                    check(j["total_cost"] == best, f"{w}x{h}x{d} optimal cost {best}",
                          f"got {j['total_cost']}")
                    check(j["canonical"] == lex, f"{w}x{h}x{d} lex-min canonical",
                          f"got {j['canonical']} want {lex}")
                    check(j["optional_depths"] == opts,
                          f"{w}x{h}x{d} full per-column optional-depth sets")
                    check(j["unique"] == unique, f"{w}x{h}x{d} uniqueness flag")
                    # Canonical surface must satisfy all constraints and its
                    # raw cost must equal the reported integer optimum.
                    surf = j["canonical"]
                    raw = sum(costs[c * d + surf[c]] for c in range(w * h))
                    smooth_ok = all(
                        abs(surf[y * w + x] - surf[y * w + x + 1]) <= S
                        for y in range(h) for x in range(w - 1)) and all(
                        abs(surf[y * w + x] - surf[(y + 1) * w + x]) <= S
                        for y in range(h - 1) for x in range(w))
                    forb_ok = all(
                        (c % w, c // w, z) not in set(map(tuple, forbidden))
                        for c, z in enumerate(surf))
                    check(raw == best and smooth_ok and forb_ok,
                          f"{w}x{h}x{d} canonical surface valid and cost-consistent")
                    compared += 1
    check(compared >= 100, f"at least 100 feasible brute comparisons (got {compared})")
    check(infeasible_seen, "random set included at least one infeasible instance")

    section("4. explicit non-contiguous ambiguity (tight S)")
    # Two columns, S=0: depths 0 and 2 both free, depth 1 costly -> optimal
    # depths {0,2} (NOT a contiguous interval).
    payload = dict(width=2, height=2, depth=3, smoothness=0,
                   costs=[0, 5, 0, 0, 5, 0, 0, 5, 0, 0, 5, 0], forbidden=[])
    j = post(API_BASE, payload).json()
    check(j["feasible"] and j["total_cost"] == 0, "S=0 optimum cost 0")
    check(all(o == [0, 2] for o in j["optional_depths"]),
          "optional depths are exactly {0,2} (non-contiguous)", str(j["optional_depths"]))
    check(j["canonical"] == [0, 0, 0, 0], "lex-min canonical is all zeros")
    check(j["unique"] is False, "reported as multiple optima")

    section("5. same request answered identically through the web proxy")
    rw = post(WEB_BASE, payload)
    check(rw.status_code == 200 and rw.json()["total_cost"] == 0,
          "web /api/solve reverse-proxies to FastAPI")

    section("6. invalid input is rejected with a locatable error")
    bad = post(API_BASE, dict(width=1, height=2, depth=3, smoothness=1, costs=[0] * 6))
    check(bad.status_code == 422, "out-of-range width -> 422")
    check(any(e.get("loc") == ["width"] for e in bad.json().get("errors", [])),
          "error locates the width field")
    bad2 = post(API_BASE, dict(width=2, height=2, depth=3, smoothness=1,
                               costs=[0] * 11))
    check(bad2.status_code == 422 and any("costs" in e["loc"] for e in bad2.json()["errors"]),
          "wrong cost count -> 422 locating costs")
    bad3 = httpx.post(API_BASE + "/api/solve", content=b"not-json",
                      headers={"Content-Type": "application/json"}, timeout=10)
    check(bad3.status_code == 422, "malformed JSON -> 422 (not 500)")

    section("7. maximum-size instance solves with exact integers")
    w = h = 40
    d = 64
    rng2 = random.Random(7)
    big_costs = [rng2.randint(0, 1_000_000) for _ in range(w * h * d)]
    t0 = time.time()
    rb = post(API_BASE, dict(width=w, height=h, depth=d, smoothness=3,
                             costs=big_costs, forbidden=[]), timeout=120)
    dt = time.time() - t0
    check(rb.status_code == 200 and rb.json()["feasible"], "40x40x64 solved", rb.text[:200])
    jb = rb.json()
    surf = jb["canonical"]
    check(len(surf) == w * h and all(0 <= z < d for z in surf), "full surface returned")
    check(sum(big_costs[c * d + surf[c]] for c in range(w * h)) == jb["total_cost"],
          "reported optimum equals canonical surface's integer cost")
    check(dt < 60, f"max instance under 60s ({dt:.2f}s)")

    print(f"\n{'='*60}")
    if failures:
        print(f"ACCEPTANCE FAILED: {len(failures)} of {checks} checks failed")
        for f in failures:
            print("  -", f)
        return 1
    print(f"ACCEPTANCE PASSED: all {checks} checks succeeded")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except httpx.HTTPError as e:
        print(f"ACCEPTANCE FAILED: HTTP error: {e}")
        sys.exit(1)
