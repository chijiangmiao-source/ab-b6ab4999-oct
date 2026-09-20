# OCT 表面全局最优审计台

从 OCT 代价体（cost volume）的每个横向位置选出**同一层界面**，在满足四邻平滑
约束与禁用体素约束的前提下，给出**精确整数最小总代价**的规范表面，并输出每一列
在**任一最优表面**中可能出现的完整深度集合，供复核员证明“全局最优、可重算”。

本仓库不调用任何通用优化求解器：问题被建模为有序标号的整数 s–t 最小割
（Ishikawa 图），最大流由仓库自带的 Dinic / 最高标号预流推进实现完成，
全部容量与流量均为 64 位整数。

---

## 约束与输出

- 横向尺寸 `width, height ∈ [2, 40]`，深度 `depth ∈ [2, 64]`。
- 每个体素代价为 `[0, 1_000_000]` 的整数；每个横向列恰选一个深度。
- 四邻（上/下/左/右）所选深度差 `|Δz| ≤ S`（`S ≥ depth` 时该约束自然失效）。
- 被标记为禁用的体素不得被选中。
- **目标**：最小化所选体素代价之和。
- **规范解（canonical）**：所有最优表面中，按行主序（`c = y*width + x`）排列的
  深度向量取**字典序最小**者。
- **歧义范围**：对每一列给出能出现在某个最优表面中的**全部**深度（可能不连续）。
- 明确标注该最优表面是**唯一**还是**多解**。

---

## 算法（为什么结果可证明为全局最优）

### 1. 精确整数最小割

每一列建立 `D+1` 个有序布尔节点 `v(k)`。一个有限割必然把 `v(0)` 放在汇点侧、
`v(D)` 放在源点侧；容量为“硬容量”的顺序弧 `v(k-1) → v(k)` 强制源点侧为上闭集，
于是每列的割边恰好有一个分界，对应所选深度 `z(c)`。

- 数据弧 `v(k) → v(k-1)`，容量 = 该体素代价（禁用体素再加大惩罚 `BIG`）。
  每列恰好一条数据弧跨越割，因此**割值 = 表面总代价**。
- 相邻列之间加入硬弧 `v_a(k) → v_b(k+S)`（双向），精确编码 `|z(a)-z(b)| ≤ S`。
- 任意无禁用表面代价至多 `n_col · 10^6 = BIG - 1`，所以最大流值 `≥ BIG`
  当且仅当不存在可行表面，可行性直接由流值读出。

整数容量下最大流 = 最小割（整数定理），故返回值即**精确全局最小总代价**。

### 2. 字典序最小的规范解

最小 s–t 割在并/交运算下构成格。所有最优割的并（join）会在每一列同时取到最浅
分界，正是全部最优深度向量中行主序字典序最小者，可直接从某一最大流的残量网络读出
（“每个最小割中都在汇点侧”的节点）。

### 3. 每一列可出现的完整深度集合

深度 `z` 能出现在**某个**最优表面，等价于存在一个最小割使 `v(z+1)` 在源点侧、
`v(z)` 在汇点侧。其充要条件是残量图上：

1. `s` 到不了 `v(z)`（下层不被强制到源点侧）；
2. `v(z+1)` 到不了 `t`（上层不被强制到汇点侧）；
3. `v(z+1)` 到不了 `v(z)`。

顺序弧容量为硬容量、永不满载，故残量图中恒有 `v(z) → v(z+1)`，条件 3 等价于
两个节点**不属于同一个强连通分量**。前两条用两次残量 BFS，第三条用一次 Kosaraju
SCC——全部为近线性时间。由此得到的可选深度集合**不保证连续**（紧平滑约束会让
例如 `{0,2}` 可达而 `1` 不可达），这正是逐 voxel 判定而非仅取两端的原因。

### 4. 不可行诊断

当无可行表面时，再做一次最小割：把“选禁用体素”的权重设为 1、平滑/边界硬弧设为
`n_col+1`、原始代价忽略。得到的流值即**任何满足平滑约束的表面至少要触碰的禁用
体素数**，并输出一个达到该下界的见证表面及其具体禁用坐标，帮助定位冲突来源。

### 5. 两个精确引擎

- `backend/native/solver.cpp`：自带的 C++ 内核（Dinic 迭代阻塞流，以及带
  gap/global-relabel 的最高标号预流推进，按 `S` 自动选择；最大规模 40×40×64
  在参考机上亚秒至数秒）。
- `backend/app/solver.py`：算法完全相同的纯 Python 后备实现；编译产物缺失时
  自动接管，接口与输出一致。响应中的 `engine` 字段标明本次实际使用的引擎。

两套引擎（含 C++ 的两种最大流算法）都通过了独立的全枚举暴力交叉验证。

---

## 仓库结构

```
backend/
  app/
    solver.py          # 纯 Python 精确内核（Dinic + 残量 BFS/SCC）
    native_bridge.py   # 优先调用 C++ 二进制，缺失时回退 Python
    validation.py      # 严格输入校验（错误带 loc，可定位）
    main.py            # FastAPI：/health、/api/solve、静态托管前端
    static/            # 构建产物（由前端 build 生成，已 gitignore）
  native/solver.cpp    # 自带 C++ 最大流/SCC 内核与文本协议
  tests/               # 对两套引擎的全枚举暴力交叉验证
  requirements.txt
frontend/
  src/                 # React 页面、切片/俯视图、列复核、解析校验
  tests/               # 解析单测、组件 SSR 冒烟、jsdom 交互测试
verify/
  e2e_acceptance.py    # Compose verify 一次性端到端验收（退出码报告）
docker/nginx.conf      # Web 边缘：静态 SPA + 反代 /api、/health
Dockerfile             # 多阶段：前端 / C++ / API / verify / web
docker-compose.yml     # api、web、verify 三服务
```

---

## HTTP 接口

`GET /health` → `{"status":"ok"}`

`POST /api/solve`，请求体：

```json
{
  "width": 4, "height": 3, "depth": 5,
  "smoothness": 1,
  "costs": [ ... 共 width*height*depth 个整数，列行主序、深度内连续 ... ],
  "forbidden": [[0, 1, 2]]
}
```

成功：`ok / feasible / total_cost / canonical[] / optional_depths[][] / unique /
dimensions / engine / min_violations / witness / elapsed_ms`。
非法输入返回 `422` 与带 `loc` 的错误列表；无可行表面返回 `200` 且
`feasible=false`，并附 `min_violations` 与 `witness`。

---

## 用 Docker Compose 运行

宿主机端口可用 `.env` 或环境变量配置（`WEB_PORT` 默认 8080，`API_PORT`
默认 8000）：

```bash
cp .env.example .env        # 按需修改 WEB_PORT / API_PORT
docker compose build
docker compose up -d
# 浏览器打开 http://localhost:${WEB_PORT:-8080}
curl -s http://localhost:${API_PORT:-8000}/health
```

`api` 与 `web` 都带健康检查；`web`/`verify` 通过
`depends_on: condition: service_healthy` 等待 API 就绪。

### 一次性端到端验收

```bash
docker compose run --rm verify
echo "exit=$?"             # 0 = 全部通过；非 0 = 有失败项
```

`verify` 是一次性服务：通过真实 HTTP（直连 API 且经 web 反代）执行健康检查、
静态资源、对随机小例的独立全枚举核对（最优值/字典序规范解/完整可选深度集/
唯一性/不可行诊断）、非连续歧义专项、非法输入定位、以及 40×40×64 最大规模
整数求解；运行结束自行退出并以退出码报告结果。

---

## 本地开发（不用 Docker）

```bash
# 后端
python3 -m venv .venv && . .venv/bin/activate
pip install -r backend/requirements.txt
g++ -O2 -std=c++17 -o backend/native/oct_solver backend/native/solver.cpp
cd backend && uvicorn app.main:app --reload --port 8000

# 前端（可选，开发服务器会把 /api、/health 代理到后端）
cd frontend && npm install && npm run dev
```

测试：

```bash
( cd backend && python tests/test_solver.py && \
  g++ -O2 -std=c++17 -o native/oct_solver native/solver.cpp && \
  python tests/test_native.py native/oct_solver )
( cd frontend && npm test )
```

---

## 前端使用

- 直接粘贴代价体：JSON 数组，或以空格/逗号/分号/换行分隔的整数；禁用体素可用
  每行 `x y z` 或 JSON 三元组数组。参数与文本实时保存在浏览器 `localStorage`，
  **求解失败或输入非法时草稿原样保留**，并逐条给出可定位的原因。
- 成功后：顶部声明唯一/多解与最小总代价；**俯视图**每格为一列（颜色=规范深度，
  斜纹=该列多解）；两个方向的**切片图**以代价灰度为底，红点为规范表面、橙色空心
  点为其他最优深度、折线连接规范面、`×` 为禁用体素。
- **点击任意一列**弹出复核面板：逐深度对照“规范解 / 可出现在某最优表面 /
  不出现 / 禁用”、各深度代价与相对差，并可四邻跳转。
