// Exact integer minimum-cost OCT surface solver.
//
// Custom Dinic max-flow + residual reachability / SCC analysis for the
// ordered-label (Ishikawa) graph.  No general-purpose solver is used;
// all capacities and the resulting flow are 64-bit integers.
//
// Text protocol on stdin:
//   W H D S
//   <W*H*D cost integers, any whitespace>
//   NF
//   x y z            (NF forbidden voxels)
//
// On stdout:
//   line 1: "OK" or "INFEASIBLE"
//   on OK, then one line per column (row-major):
//     <canonical depth> <D-char 0/1 mask of depths attainable in an optimum>
//   last line: "<minimum total cost>"

#include <bits/stdc++.h>
using namespace std;

using int64 = long long;

struct Dinic {
    struct Edge { int to, rev; int64 cap; };
    int N;
    vector<vector<Edge>> g;
    vector<int> level, it;

    explicit Dinic(int n) : N(n), g(n), level(n), it(n) {}

    void add_edge(int from, int to, int64 cap) {
        Edge a{to, (int)g[to].size(), cap};
        Edge b{from, (int)g[from].size(), 0};
        g[from].push_back(a);
        g[to].push_back(b);
    }

    bool bfs(int s, int t) {
        fill(level.begin(), level.end(), -1);
        queue<int> q;
        level[s] = 0;
        q.push(s);
        while (!q.empty()) {
            int v = q.front(); q.pop();
            for (const auto &e : g[v]) {
                if (e.cap > 0 && level[e.to] < 0) {
                    level[e.to] = level[v] + 1;
                    q.push(e.to);
                }
            }
        }
        return level[t] >= 0;
    }

    // Iterative blocking-flow DFS (avoids deep recursion on big volumes).
    int64 blocking_flow(int s, int t) {
        int64 total = 0;
        // Path of (vertex, edge index used to enter that vertex).
        vector<int> pv, pe;
        pv.reserve(N);
        pe.reserve(N);
        pv.push_back(s);
        pe.push_back(-1);
        while (!pv.empty()) {
            int v = pv.back();
            if (v == t) {
                int64 f = (1LL << 62);
                for (size_t i = 1; i < pv.size(); ++i)
                    f = min(f, g[pv[i - 1]][pe[i]].cap);
                size_t cut = pv.size();
                for (size_t i = 1; i < pv.size(); ++i) {
                    Edge &e = g[pv[i - 1]][pe[i]];
                    e.cap -= f;
                    g[e.to][e.rev].cap += f;
                    if (e.cap == 0 && i < cut) cut = i;
                }
                total += f;
                pv.resize(cut);
                pe.resize(cut);
                continue;
            }
            int &i = it[v];
            bool advanced = false;
            while (i < (int)g[v].size()) {
                Edge &e = g[v][i];
                if (e.cap > 0 && level[e.to] == level[v] + 1) {
                    pv.push_back(e.to);
                    pe.push_back(i);
                    advanced = true;
                    ++i;
                    break;
                }
                ++i;
            }
            if (!advanced) {
                level[v] = -1; // prune dead vertex within this phase
                pv.pop_back();
                pe.pop_back();
            }
        }
        return total;
    }

    int64 max_flow(int s, int t) {
        int64 flow = 0;
        while (bfs(s, t)) {
            fill(it.begin(), it.end(), 0);
            flow += blocking_flow(s, t);
        }
        return flow;
    }

    // Highest-label push-relabel with gap + periodic global relabel.
    // Faster than Dinic on the near-grid-level graphs produced by small
    // smoothness S; the caller picks the method.  Terminates with all
    // non-source/sink excess drained, so g is in a maximum-flow residual
    // state ready for reachability/SCC analysis.
    int64 push_relabel(int s, int t) {
        const int HSENT = 2 * N + 1; // "no admissible neighbour" sentinel
        const int HDRAIN = N + 1;    // height of nodes unable to reach t
        vector<int64> exc(N, 0);
        vector<int> h(N, HSENT), cur(N, 0);
        vector<int> cnt(HSENT + 2, 0);
        vector<vector<int>> buckets(HSENT + 2);

        auto rebuild_counts = [&]() {
            fill(cnt.begin(), cnt.end(), 0);
            for (int v = 0; v < N; ++v) cnt[h[v]]++;
        };

        auto global_relabel = [&]() {
            fill(h.begin(), h.end(), HSENT);
            h[t] = 0;
            queue<int> q;
            q.push(t);
            while (!q.empty()) {
                int v = q.front(); q.pop();
                for (const auto &e : g[v]) {
                    const Edge &r = g[e.to][e.rev]; // arc e.to -> v
                    if (r.cap > 0 && h[e.to] == HSENT) {
                        h[e.to] = h[v] + 1;
                        q.push(e.to);
                    }
                }
            }
            // Vertices unable to reach t start just above s; subsequent
            // relabels raise them as needed to drain excess back to s.
            for (int v = 0; v < N; ++v)
                if (h[v] == HSENT && v != s) h[v] = HDRAIN;
            h[s] = N;
            rebuild_counts();
        };

        auto rebuild_buckets = [&]() {
            for (auto &bk : buckets) bk.clear();
            for (int v = 0; v < N; ++v)
                if (v != s && v != t && exc[v] > 0)
                    buckets[h[v]].push_back(v);
        };

        auto enqueue = [&](int v) {
            if (v != s && v != t && exc[v] > 0) buckets[h[v]].push_back(v);
        };

        global_relabel();
        for (auto &e : g[s]) {
            int64 f = e.cap;
            if (f) {
                e.cap = 0;
                g[e.to][e.rev].cap += f;
                exc[e.to] += f;
            }
        }
        rebuild_buckets();

        int hi = HDRAIN;
        long long work = 0;
        while (hi > 0) {
            if (buckets[hi].empty()) { --hi; continue; }
            int u = buckets[hi].back();
            buckets[hi].pop_back();
            if (exc[u] == 0) continue; // duplicate/stale bucket entry

            bool restart = false;
            while (exc[u] > 0) {
                int &i = cur[u];
                while (i < (int)g[u].size()) {
                    Edge &e = g[u][i];
                    if (e.cap > 0 && h[u] == h[e.to] + 1) {
                        int64 f = min(exc[u], e.cap);
                        e.cap -= f;
                        g[e.to][e.rev].cap += f;
                        exc[u] -= f;
                        exc[e.to] += f;
                        enqueue(e.to);
                        if (exc[u] == 0) break;
                    }
                    ++i;
                }
                if (exc[u] == 0) break;

                int old = h[u];
                int nh = HSENT;
                for (const auto &e : g[u])
                    if (e.cap > 0) nh = min(nh, h[e.to] + 1);
                i = 0;
                cnt[old]--;
                if (old < N && cnt[old] == 0) {
                    // gap: nothing at height old can reach t
                    for (int x = 0; x < N; ++x) {
                        if (x != s && old < h[x] && h[x] < N) {
                            h[x] = HDRAIN;
                            cur[x] = 0;
                        }
                    }
                    h[u] = HDRAIN;
                    rebuild_counts();
                    rebuild_buckets();
                    hi = HDRAIN;
                    restart = true;
                    break;
                }
                h[u] = nh;
                cnt[nh]++;
                hi = max(hi, nh);

                if (++work % (4LL * N) == 0) {
                    global_relabel();
                    rebuild_buckets();
                    hi = HDRAIN;
                    restart = true;
                    break;
                }
            }
            // rebuild_buckets() (gap/relabel restart) already enqueued u;
            // otherwise re-enqueue here if it still holds excess.
            if (!restart && exc[u] > 0) buckets[h[u]].push_back(u);
        }
        return exc[t];
    }

    // Vertices reachable from src through positive residual capacity.
    vector<char> reach_forward(int src) const {
        vector<char> seen(N, 0);
        queue<int> q;
        seen[src] = 1;
        q.push(src);
        while (!q.empty()) {
            int v = q.front(); q.pop();
            for (const auto &e : g[v])
                if (e.cap > 0 && !seen[e.to]) {
                    seen[e.to] = 1;
                    q.push(e.to);
                }
        }
        return seen;
    }

    // Vertices that can reach dst through positive residual capacity.
    vector<char> reach_to(int dst) const {
        vector<char> seen(N, 0);
        queue<int> q;
        seen[dst] = 1;
        q.push(dst);
        while (!q.empty()) {
            int v = q.front(); q.pop();
            for (const auto &e : g[v]) {
                // reverse residual of arc e.to -> v
                const Edge &r = g[e.to][e.rev];
                if (r.cap > 0 && !seen[e.to]) {
                    seen[e.to] = 1;
                    q.push(e.to);
                }
            }
        }
        return seen;
    }

    // SCCs of the positive-residual graph (iterative Kosaraju).
    vector<int> residual_scc() const {
        int n = N;
        vector<char> vis(n, 0);
        vector<int> order;
        order.reserve(n);

        for (int root = 0; root < n; ++root) {
            if (vis[root]) continue;
            // pairs (vertex, next edge index)
            vector<pair<int,int>> st;
            st.reserve(n);
            vis[root] = 1;
            st.push_back({root, 0});
            while (!st.empty()) {
                auto &[v, idx] = st.back();
                if (idx < (int)g[v].size()) {
                    const Edge &e = g[v][idx++];
                    if (e.cap > 0 && !vis[e.to]) {
                        vis[e.to] = 1;
                        st.push_back({e.to, 0});
                    }
                } else {
                    order.push_back(v);
                    st.pop_back();
                }
            }
        }

        // reverse adjacency over residual arcs
        vector<vector<int>> radj(n);
        for (int v = 0; v < n; ++v)
            for (const auto &e : g[v])
                if (e.cap > 0) radj[e.to].push_back(v);

        vector<int> comp(n, -1);
        int cid = 0;
        for (int ii = n - 1; ii >= 0; --ii) {
            int root = order[ii];
            if (comp[root] != -1) continue;
            vector<int> st{root};
            comp[root] = cid;
            while (!st.empty()) {
                int v = st.back(); st.pop_back();
                for (int p : radj[v])
                    if (comp[p] == -1) {
                        comp[p] = cid;
                        st.push_back(p);
                    }
            }
            ++cid;
        }
        return comp;
    }
};

// Build the ordered-label graph.
//   hard_cap       capacity of boundary/order/smoothing arcs
//   use_raw_cost   include the original integer voxel cost in data arcs
//   forbid_penalty extra data-arc capacity for forbidden voxels
static unique_ptr<Dinic> build_graph(
    int W, int H, int D, int S, int s, int t,
    const vector<int64> &cost, const vector<vector<char>> &forbidden,
    int64 hard_cap, bool use_raw_cost, int64 forbid_penalty) {
    int ncol = W * H;
    int K = D + 1;
    auto node = [&](int c, int lvl) { return 2 + c * K + lvl; };
    auto g = make_unique<Dinic>(2 + ncol * K);

    for (int c = 0; c < ncol; ++c) {
        g->add_edge(s, node(c, D), hard_cap);
        g->add_edge(node(c, 0), t, hard_cap);
        for (int lvl = 1; lvl <= D; ++lvl) {
            int z = lvl - 1;
            g->add_edge(node(c, lvl - 1), node(c, lvl), hard_cap);
            int64 cap = use_raw_cost ? cost[c * D + z] : 0;
            if (forbidden[c][z]) cap += forbid_penalty;
            g->add_edge(node(c, lvl), node(c, lvl - 1), cap);
        }
    }

    if (0 <= S && S < D) {
        for (int y = 0; y < H; ++y) {
            for (int x = 0; x < W; ++x) {
                int c = y * W + x;
                int neigh[2] = {-1, -1};
                int nn = 0;
                if (x + 1 < W) neigh[nn++] = c + 1;
                if (y + 1 < H) neigh[nn++] = c + W;
                for (int q = 0; q < nn; ++q) {
                    int cb = neigh[q];
                    for (int k = 0; k <= D - S; ++k) {
                        g->add_edge(node(c, k), node(cb, k + S), hard_cap);
                        g->add_edge(node(cb, k), node(c, k + S), hard_cap);
                    }
                }
            }
        }
    }
    return g;
}

static bool prefer_pr(int S, int D) {
    const char *forced = getenv("OCT_METHOD");
    if (forced && forced[0]) return forced[0] == 'p';
    return 0 <= S && S < D && S <= 10;
}

// Surface encoded by one cut side: boundary depth per column.
static vector<int> cut_surface(const Dinic &g, int s, int W, int H, int D) {
    int ncol = W * H, K = D + 1;
    auto node = [&](int c, int lvl) { return 2 + c * K + lvl; };
    vector<char> src_side = g.reach_forward(s);
    vector<int> surf(ncol, D - 1);
    for (int c = 0; c < ncol; ++c) {
        for (int lvl = 1; lvl <= D; ++lvl) {
            if (src_side[node(c, lvl)]) { surf[c] = lvl - 1; break; }
        }
    }
    return surf;
}

int main() {
    ios::sync_with_stdio(false);
    cin.tie(nullptr);

    int W, H, D, S;
    if (!(cin >> W >> H >> D >> S)) return 2;

    int ncol = W * H;
    int total = ncol * D;
    vector<int64> cost(total);
    for (int i = 0; i < total; ++i) cin >> cost[i];

    int nf;
    cin >> nf;
    vector<vector<char>> forbidden(ncol, vector<char>(D, 0));
    for (int i = 0; i < nf; ++i) {
        int x, y, z;
        cin >> x >> y >> z;
        forbidden[y * W + x][z] = 1;
    }

    const int64 MAXC = 1'000'000LL;
    // Any forbidden-free surface costs at most ncol*MAXC = BIG-1.
    const int64 BIG = (int64)ncol * MAXC + 1;

    int s = 0, t = 1;
    bool use_pr = prefer_pr(S, D);

    auto g = build_graph(W, H, D, S, s, t, cost, forbidden, BIG, true, BIG);
    int64 flow = use_pr ? g->push_relabel(s, t) : g->max_flow(s, t);
    if (flow >= BIG) {
        // Diagnosis pass: minimize the NUMBER of forbidden voxels hit by a
        // smoothness-valid surface (raw costs ignored).  Hard arcs cost
        // ncol+1, so any smoothness-valid cut stays below one hard arc.
        auto dg = build_graph(W, H, D, S, s, t, cost, forbidden,
                              ncol + 1, false, 1);
        int64 min_violations =
            use_pr ? dg->push_relabel(s, t) : dg->max_flow(s, t);
        vector<int> witness = cut_surface(*dg, s, W, H, D);
        cout << "INFEASIBLE\n";
        cout << min_violations << '\n';
        for (int c = 0; c < ncol; ++c)
            cout << witness[c] << (c + 1 == ncol ? '\n' : ' ');
        return 0;
    }

    vector<char> from_s = g->reach_forward(s);
    vector<char> to_t = g->reach_to(t);
    vector<int> comp = g->residual_scc();

    int K = D + 1;
    auto node = [&](int c, int lvl) { return 2 + c * K + lvl; };

    cout << "OK\n";
    for (int c = 0; c < ncol; ++c) {
        int canonical = D - 1;
        for (int lvl = 1; lvl <= D; ++lvl) {
            if (!to_t[node(c, lvl)]) { canonical = lvl - 1; break; }
        }
        string mask(D, '0');
        for (int z = 0; z < D; ++z) {
            int upper = node(c, z + 1);
            int lower = node(c, z);
            if (!to_t[upper] && !from_s[lower] && comp[upper] != comp[lower])
                mask[z] = '1';
        }
        cout << canonical << ' ' << mask << '\n';
    }
    cout << flow << '\n';
    return 0;
}
