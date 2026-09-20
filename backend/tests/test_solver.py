"""Independent brute-force cross-check for solver.py (tiny instances)."""

import itertools
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.solver import solve  # noqa: E402


def brute(w, h, d, S, costs, forbidden):
    """Enumerate every surface; return (opt, lexmin, optional, unique)."""
    forbidden_set = set(forbidden)
    best = None
    lexmin = None
    optional = [set() for _ in range(w * h)]
    n_opt = 0
    for surf in itertools.product(range(d), repeat=w * h):
        if any((c % w, c // w, z) in forbidden_set for c, z in enumerate(surf)):
            continue
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
        val = sum(costs[c * d + surf[c]] for c in range(w * h))
        if best is None or val <= best:
            if val == best:
                pass
            else:
                best = val
                lexmin = surf
                n_opt = 0
                optional = [set() for _ in range(w * h)]
            n_opt += 1
            for c, z in enumerate(surf):
                optional[c].add(z)
            if surf < lexmin:
                lexmin = surf
    if best is None:
        return None
    return best, list(lexmin), [sorted(s) for s in optional], n_opt == 1


def main():
    random.seed(20260920)
    cases = 0
    shapes = [(1, 2), (2, 1), (2, 2), (3, 2), (2, 3), (3, 3), (1, 4), (4, 1)]
    for w, h in shapes:
        for d in (2, 3, 4):
            if w * h * d > 18:  # keep enumeration tiny
                continue
            for S in (0, 1, 2, 5):
                if S >= d:
                    continue
                for trial in range(40):
                    costs = [random.randint(0, 5) for _ in range(w * h * d)]
                    forbidden = []
                    for v in range(w * h * d):
                        if random.random() < 0.12:
                            x, z = divmod(v, d)
                            forbidden.append((x % w, x // w, z))
                    expected = brute(w, h, d, S, costs, forbidden)
                    got = solve(w, h, d, S, costs, forbidden)
                    cases += 1
                    if expected is None:
                        assert got["feasible"] is False, (w, h, d, S, "should be infeasible")
                        continue
                    opt, lex, opts, uniq = expected
                    assert got["feasible"] is True
                    assert got["total_cost"] == opt, (w, h, d, S, opt, got)
                    assert got["canonical"] == lex, (w, h, d, S, lex, got["canonical"])
                    assert got["optional_depths"] == opts, (
                        w, h, d, S, opts, got["optional_depths"],
                    )
                    assert got["unique"] == uniq

    # Forbidden-only infeasibility: every depth of one column forbidden.
    w, h, d = 2, 2, 3
    costs = [0] * w * h * d
    forbidden = [(0, 0, z) for z in range(d)]
    assert solve(w, h, d, 1, costs, forbidden)["feasible"] is False

    # Smoothness-only infeasibility: two columns, S=0, disjoint allowed sets.
    w, h, d = 2, 1, 3
    costs = [0] * w * h * d
    forbidden = [(1, 0, 1), (1, 0, 2), (0, 0, 0)]
    r = solve(w, h, d, 0, costs, forbidden)
    assert r["feasible"] is False

    # All-zero 2x2x3, tight S: canonical is all-zero lex vector.
    r = solve(2, 2, 3, 0, [0] * 12, [])
    assert r["total_cost"] == 0 and r["canonical"] == [0, 0, 0, 0]
    assert r["optional_depths"] == [[0, 1, 2]] * 4 and r["unique"] is False

    # Larger random case: check feasibility and canonical/optional interval
    # consistency against an independent 1-row DP recomputation of optimum.
    for trial in range(20):
        w, d = 6, 7
        costs = [random.randint(0, 1_000_000) for _ in range(w * d)]
        S = random.randint(0, d)
        r = solve(w, 1, d, S, costs, [])
        # DP optimum for a chain
        inf = float("inf")
        dp = costs[:d]
        for c in range(1, w):
            ndp = [inf] * d
            for z in range(d):
                lo, hi = max(0, z - S), min(d, z + S + 1)
                ndp[z] = costs[c * d + z] + min(dp[lo:hi])
            dp = ndp
        assert r["total_cost"] == min(dp)
        # verify canonical surface itself realizes the optimum
        surf = r["canonical"]
        val = sum(costs[c * d + surf[c]] for c in range(w))
        assert val == r["total_cost"]
        for c in range(w - 1):
            assert abs(surf[c] - surf[c + 1]) <= S
        cases += 1

    print(f"all {cases} randomized/brute-force checks passed")


if __name__ == "__main__":
    main()
