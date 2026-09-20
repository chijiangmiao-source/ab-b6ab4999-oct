"""Cross-check the C++ kernel against full enumeration, mirroring the Python tests."""
import itertools, random, subprocess, sys, os

BIN = sys.argv[1] if len(sys.argv) > 1 else "/tmp/oct_solver"


def brute(w, h, d, S, costs, forbidden):
    """Return (feasible-result-or-None, minimum forbidden violations)."""
    fset = set(forbidden)
    best = None
    lexmin = None
    optional = [set() for _ in range(w * h)]
    n_opt = 0
    min_viol = None
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
            best, lexmin, n_opt = val, surf, 0
            optional = [set() for _ in range(w * h)]
        if val == best:
            n_opt += 1
            for c, z in enumerate(surf):
                optional[c].add(z)
            if surf < lexmin:
                lexmin = surf
    if best is None:
        return None, min_viol
    return (
        (best, list(lexmin), [sorted(s) for s in optional], n_opt == 1),
        min_viol,
    )


def run_native(w, h, d, S, costs, forb, method=None):
    data = f"{w} {h} {d} {S}\n"
    data += " ".join(map(str, costs)) + "\n"
    data += f"{len(forb)}\n"
    for x, y, z in forb:
        data += f"{x} {y} {z}\n"
    env = None
    if method:
        env = dict(os.environ, OCT_METHOD=method)
    out = subprocess.run(
        [BIN], input=data, capture_output=True, text=True, timeout=60, env=env
    )
    lines = out.stdout.strip().split("\n")
    if lines[0] == "INFEASIBLE":
        result = {"feasible": False, "min_violations": None, "witness": None}
        if len(lines) >= 3:
            result["min_violations"] = int(lines[1])
            result["witness"] = list(map(int, lines[2].split()))
        return result
    assert lines[0] == "OK", out.stdout + out.stderr
    canonical, optional = [], []
    for i in range(1, 1 + w * h):
        z, mask = lines[i].split()
        canonical.append(int(z))
        optional.append([i for i, ch in enumerate(mask) if ch == "1"])
    return {
        "feasible": True,
        "canonical": canonical,
        "optional_depths": optional,
        "total_cost": int(lines[-1]),
        "unique": all(len(o) == 1 for o in optional),
    }


def main():
    random.seed(4242)
    cases = 0
    shapes = [(1, 2), (2, 1), (2, 2), (3, 2), (2, 3), (3, 3), (1, 4), (4, 1)]
    for method in ("pr", "dinic"):
        for w, h in shapes:
            for d in (2, 3, 4):
                if w * h * d > 18:
                    continue
                for S in (0, 1, 2, 5):
                    if S >= d:
                        continue
                    for trial in range(40):
                        costs = [random.randint(0, 5) for _ in range(w * h * d)]
                        forb = []
                        for v in range(w * h * d):
                            if random.random() < 0.12:
                                x, z = divmod(v, d)
                                forb.append((x % w, x // w, z))
                        exp, min_viol = brute(w, h, d, S, costs, forb)
                        got = run_native(w, h, d, S, costs, forb, method=method)
                        cases += 1
                        if exp is None:
                            assert got["feasible"] is False, (method, w, h, d, S)
                            assert got["min_violations"] == min_viol, (
                                method, w, h, d, S, min_viol, got["min_violations"])
                            # witness must be smoothness-valid and hit that
                            # exact number of forbidden voxels
                            wit = got["witness"]
                            assert wit is not None and len(wit) == w * h
                            fset = set(map(tuple, forb))
                            hits = sum(
                                1 for c, z in enumerate(wit)
                                if (c % w, c // w, z) in fset)
                            assert hits == min_viol, (w, h, d, S)
                            for yy in range(h):
                                for xx in range(w):
                                    cc = yy * w + xx
                                    if xx + 1 < w:
                                        assert abs(wit[cc] - wit[cc + 1]) <= S
                                    if yy + 1 < h:
                                        assert abs(wit[cc] - wit[cc + w]) <= S
                            continue
                        assert got["feasible"], (method, w, h, d, S)
                        assert got["total_cost"] == exp[0], (method, w, h, d, S, exp[0], got)
                        assert got["canonical"] == exp[1], (method, w, h, d, S)
                        assert got["optional_depths"] == exp[2], (method, w, h, d, S)
                        assert got["unique"] == exp[3]
    print(f"all {cases} C++ brute-force checks passed (both algorithms)")

    # max-size timing
    import time, resource
    w = h = 40
    d = 64
    costs = [random.randint(0, 1_000_000) for _ in range(w * h * d)]
    forb = []
    for v in range(w * h * d):
        if random.random() < 0.02:
            x, z = divmod(v, d)
            forb.append((x % w, x // w, z))
    for S, fb in ((3, forb), (0, []), (1, []), (64, [])):
        t0 = time.perf_counter()
        r = run_native(w, h, d, S, costs, fb)
        dt = time.perf_counter() - t0
        mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        print("C++ S=%2d cost=%s uniq=%s %.3fs parentRss %.0fMB"
              % (S, r.get("total_cost"), r.get("unique"), dt, mb))


if __name__ == "__main__":
    main()
