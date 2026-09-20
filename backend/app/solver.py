"""Exact integer surface solver for OCT cost volumes.

Model
-----
For every lateral column c = (x, y) choose exactly one depth
z(c) in {0, ..., D-1} minimizing::

    sum_c cost[c][z(c)]

subject to::

    |z(c) - z(c')| <= S   for every 4-neighbour pair c, c'
    z(c) not in forbidden[c]

No general-purpose optimization solver is used: the problem is a binary
multi-label MRF with a convex (absolute-difference) pairwise term, solved
exactly as an integer s-t minimum cut (Ishikawa / ordered-labels
construction).  All capacities are non-negative integers and the bundled
Dinic implementation works in exact integer arithmetic.

Graph construction
------------------
Each column has D+1 ordered boolean nodes v(k), k = 0..D.  A finite cut
always places v(0) on the sink side and v(D) on the source side.  Infinite
order arcs v(k-1) -> v(k) make the source side an upper set, so each cut
has exactly one boundary per column::

    v(k) on source side  <=>  k >= z(c) + 1

* data arc v(k) -> v(k-1) (k = 1..D), capacity cost[c][k-1]; exactly one
  data arc per column crosses the cut (the chosen voxel), so cut cost
  equals surface cost.
* for each neighbour pair (a, b), arcs v_a(k) -> v_b(k+S), k = 0..D-S
  (plus symmetric ones) enforce |z(a) - z(b)| <= S.
* s -> v(D) and v(0) -> t are infinite boundary arcs.
* a forbidden voxel carries extra capacity B > n_col * MAX_COST on its
  data arc, so feasibility is read straight from the flow value.

Canonical optimum and ambiguity
-------------------------------
Minimum s-t cuts form a lattice under union/intersection.  The union
(join) of all optimal cuts moves every column boundary as shallow as
possible, which is exactly the lexicographically smallest row-major depth
vector among all optimal surfaces.

Whether depth z can occur at column c in SOME optimal surface is a
node-separation question on the residual graph of a maximum flow:
it requires a min cut with v_c(z+1) on the source side and v_c(z) on
the sink side.  Such a cut exists iff none of the following residual
paths exist (otherwise they would close an s->t residual path or an
infinite-arc crossing)::

    s  ->* v_c(z)     (v_c(z) forced source in every min cut)
    v_c(z+1) ->* t    (v_c(z+1) forced sink in every min cut)
    v_c(z+1) ->* v_c(z)

The first two are answered by residual BFS.  For the third, the
infinite order arc v_c(z) -> v_c(z+1) never saturates, so v_c(z) always
reaches v_c(z+1) in the residual graph; a reverse path exists exactly
when the two nodes belong to the same strongly connected component.
One Kosaraju pass over the residual graph answers every column.
Attainable depths need not form an interval (tight smoothness can couple
non-adjacent labels), so the SCC test is done per voxel rather than per
extreme cut.
"""

from __future__ import annotations

from array import array
from collections import deque
from typing import Sequence

MAX_COST = 1_000_000
INF = 10**18  # larger than any finite flow; fits in signed 64-bit


class _Dinic:
    """Dinic max flow on compact forward-star integer arrays.

    Edge e and e^1 are reverse arcs.  ``head`` chains outgoing arcs,
    ``head_rev`` chains incoming arcs; both are reused later for SCC and
    residual reachability.
    """

    def __init__(self, n: int):
        self.n = n
        self.head = array("i", [-1]) * n
        self.head_rev = array("i", [-1]) * n
        self.to = array("i")
        self.nxt = array("i")
        self.nxt_rev = array("i")
        self.cap = array("q")

    def add_edge(self, u: int, v: int, cap: int) -> None:
        e = len(self.to)
        self.to.append(v)
        self.to.append(u)
        self.cap.append(cap)
        self.cap.append(0)
        self.nxt.append(self.head[u])
        self.nxt.append(self.head[v])
        self.nxt_rev.append(self.head_rev[v])
        self.nxt_rev.append(self.head_rev[u])
        self.head[u] = e
        self.head_rev[v] = e
        self.head[v] = e + 1
        self.head_rev[u] = e + 1

    def max_flow(self, s: int, t: int) -> int:
        n = self.n
        head, to, nxt, cap = self.head, self.to, self.nxt, self.cap
        flow = 0
        level = array("i", [-1]) * n

        while True:
            # ----- BFS: build level graph -----
            for i in range(n):
                level[i] = -1
            level[s] = 0
            q = deque((s,))
            while q:
                u = q.popleft()
                lu = level[u] + 1
                e = head[u]
                while e != -1:
                    if cap[e] > 0 and level[to[e]] == -1:
                        level[to[e]] = lu
                        q.append(to[e])
                    e = nxt[e]
            if level[t] == -1:
                break

            ptr = array("i", head)  # current-arc pointer per vertex

            # ----- iterative DFS: push blocking flow -----
            path_v = [s]
            path_e: list[int] = []
            while path_v:
                u = path_v[-1]
                if u == t:
                    pushed = INF
                    for e in path_e:
                        c = cap[e]
                        if c < pushed:
                            pushed = c
                    cut_at = len(path_e)
                    for i, e in enumerate(path_e):
                        cap[e] -= pushed
                        cap[e ^ 1] += pushed
                        if cap[e] == 0 and i < cut_at:
                            cut_at = i
                    flow += pushed
                    del path_v[cut_at + 1 :]
                    del path_e[cut_at:]
                    continue

                e = ptr[u]
                advanced = False
                lu = level[u]
                while e != -1:
                    v = to[e]
                    if cap[e] > 0 and level[v] == lu + 1:
                        ptr[u] = e
                        path_e.append(e)
                        path_v.append(v)
                        advanced = True
                        break
                    e = nxt[e]
                    ptr[u] = e
                if not advanced:
                    level[u] = -1
                    path_v.pop()
                    if path_e:
                        path_e.pop()
        return flow

    # ------------------------------------------------------------------
    # residual-graph analysis (run after max_flow)
    # ------------------------------------------------------------------

    def bfs_forward(self, src: int) -> bytearray:
        """Vertices reachable from src over positive residual arcs."""
        seen = bytearray(self.n)
        seen[src] = 1
        q = deque((src,))
        while q:
            u = q.popleft()
            e = self.head[u]
            while e != -1:
                v = self.to[e]
                if self.cap[e] > 0 and not seen[v]:
                    seen[v] = 1
                    q.append(v)
                e = self.nxt[e]
        return seen

    def bfs_to(self, dst: int) -> bytearray:
        """Vertices that can reach dst over positive residual arcs."""
        seen = bytearray(self.n)
        seen[dst] = 1
        q = deque((dst,))
        while q:
            u = q.popleft()
            e = self.head_rev[u]
            while e != -1:
                if self.cap[e] > 0:
                    p = self.to[e ^ 1]
                    if not seen[p]:
                        seen[p] = 1
                        q.append(p)
                e = self.nxt_rev[e]
        return seen

    def residual_scc(self) -> array:
        """SCC ids of the positive-residual graph (iterative Kosaraju)."""
        n = self.n
        head, head_rev = self.head, self.head_rev
        to, nxt, nxt_rev, cap = self.to, self.nxt, self.nxt_rev, self.cap

        # Pass 1: finishing order on forward residual arcs.
        visited = bytearray(n)
        order: list[int] = []
        for root in range(n):
            if visited[root]:
                continue
            visited[root] = 1
            stack = [(root, head[root])]
            while stack:
                u, e = stack[-1]
                if e == -1:
                    order.append(u)
                    stack.pop()
                    continue
                stack[-1] = (u, nxt[e])
                if cap[e] > 0:
                    v = to[e]
                    if not visited[v]:
                        visited[v] = 1
                        stack.append((v, head[v]))

        # Pass 2: DFS on reverse residual arcs in reverse finish order.
        comp = array("i", [-1]) * n
        cid = 0
        for root in reversed(order):
            if comp[root] != -1:
                continue
            comp[root] = cid
            stack = [root]
            while stack:
                u = stack.pop()
                e = head_rev[u]
                while e != -1:
                    if cap[e] > 0:
                        p = to[e ^ 1]
                        if comp[p] == -1:
                            comp[p] = cid
                            stack.append(p)
                    e = nxt_rev[e]
            cid += 1
        return comp


def _build_graph(w, h, d, smoothness, costs, forbidden, hard, use_cost, penalty):
    n_col = w * h
    k = d + 1
    s, t = 0, 1

    def node(c: int, level: int) -> int:
        return 2 + c * k + level

    g = _Dinic(2 + n_col * k)
    forbidden_set = set(forbidden)
    for c in range(n_col):
        base = c * d
        g.add_edge(s, node(c, d), hard)
        g.add_edge(node(c, 0), t, hard)
        for level in range(1, k):
            z = level - 1
            g.add_edge(node(c, level - 1), node(c, level), hard)
            cap = costs[base + z] if use_cost else 0
            if (c % w, c // w, z) in forbidden_set:
                cap += penalty
            g.add_edge(node(c, level), node(c, level - 1), cap)

    if 0 <= smoothness < d:
        last_k = d - smoothness
        for y in range(h):
            row = y * w
            for x in range(w):
                c = row + x
                if x + 1 < w:
                    _add_smoothing_arcs(g, c, c + 1, node, hard, smoothness, last_k)
                if y + 1 < h:
                    _add_smoothing_arcs(g, c, c + w, node, hard, smoothness, last_k)
    return g, s, t, node


def _cut_surface(g, s, node, n_col, d):
    src = g.bfs_forward(s)
    surf = [d - 1] * n_col
    for c in range(n_col):
        for level in range(1, d + 1):
            if src[node(c, level)]:
                surf[c] = level - 1
                break
    return surf


def _infeasible_diagnosis(w, h, d, smoothness, costs, forbidden):
    """Minimum number of forbidden voxels any smoothness-valid surface
    must use, plus one such witness surface."""
    n_col = w * h
    g, s, t, node = _build_graph(
        w, h, d, smoothness, costs, forbidden,
        hard=n_col + 1, use_cost=False, penalty=1,
    )
    min_violations = g.max_flow(s, t)
    witness = _cut_surface(g, s, node, n_col, d)
    return min_violations, witness


def solve(
    width: int,
    height: int,
    depth: int,
    smoothness: int,
    costs: Sequence[int],
    forbidden: Sequence[tuple[int, int, int]] = (),
) -> dict:
    """Exact optimum and per-column ambiguity information.

    Depths in the output are 0-based.  Columns use row-major order,
    column c = (x, y) has index y * width + x.
    """
    w, h, d = width, height, depth
    n_col = w * h
    k = d + 1

    # Any forbidden-free surface costs at most n_col * MAX_COST = big - 1.
    big = n_col * MAX_COST + 1
    g, s, t, node = _build_graph(
        w, h, d, smoothness, costs, forbidden,
        hard=big, use_cost=True, penalty=big,
    )

    flow = g.max_flow(s, t)
    if flow >= big:
        min_violations, witness = _infeasible_diagnosis(
            w, h, d, smoothness, costs, forbidden
        )
        return {
            "feasible": False,
            "total_cost": None,
            "canonical": None,
            "optional_depths": None,
            "unique": None,
            "min_violations": min_violations,
            "witness": witness,
        }

    # Forced-side sets: vertices reachable from s are source side in
    # EVERY min cut; vertices that can reach t are sink side in every one.
    forced_source = g.bfs_forward(s)
    can_reach_t = g.bfs_to(t)

    # Within a column, order arcs never saturate so v(z) always reaches
    # v(z+1) in the residual graph; a reverse path v(z+1) ->* v(z) exists
    # exactly when the two nodes share an SCC.
    comp = g.residual_scc()

    canonical = [0] * n_col
    optional: list[list[int]] = []
    unique = True
    for c in range(n_col):
        # Lexicographically smallest optimum = join of all min cuts:
        # boundary at the first level whose node is not forced sink.
        z0 = 0
        for level in range(1, k):
            if not can_reach_t[node(c, level)]:
                z0 = level - 1
                break
        else:  # pragma: no cover - v(D) can never be forced sink
            z0 = d - 1
        canonical[c] = z0

        depths: list[int] = []
        for z in range(d):
            upper = node(c, z + 1)  # must be source side
            lower = node(c, z)  # must be sink side
            if (
                not can_reach_t[upper]  # upper not forced sink
                and not forced_source[lower]  # lower not forced source
                and comp[upper] != comp[lower]  # no residual path upper -> lower
            ):
                depths.append(z)
        optional.append(depths)
        if len(depths) != 1:
            unique = False

    return {
        "feasible": True,
        "total_cost": flow,
        "canonical": canonical,
        "optional_depths": optional,
        "unique": unique,
    }


def _add_smoothing_arcs(g, ca, cb, node, hard, sm, last_k):
    # v_a(k) source => v_b(k+S) source, enforcing z(b) <= z(a) + S;
    # the symmetric arcs enforce the other inequality.
    for kk in range(last_k + 1):
        g.add_edge(node(ca, kk), node(cb, kk + sm), hard)
        g.add_edge(node(cb, kk), node(ca, kk + sm), hard)
