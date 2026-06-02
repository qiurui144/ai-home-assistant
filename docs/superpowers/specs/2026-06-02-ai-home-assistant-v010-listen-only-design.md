# ai-home-assistant v0.1.0 — Listen-only Foundation Design

**Date**: 2026-06-02
**Status**: Design spec (brainstorming-derived), awaiting user final approval
**Authors**: AI working session (per global `~/.claude/CLAUDE.md` §3.1 11-节 spec 铁律)
**Parent**: `docs/specs/2026-05-25-ai-home-assistant-architecture.md` (v1.0 全景架构 spec)
**Implements**: v0.1.0 (Phase A 首切,per §0 roadmap)
**Roadmap reaches**: v2.5.0 受限全自动 GA;v3.0.0+ advanced

---

## 目录(TOC)

- [§0 Roadmap 上下文(v0.1 → v2.5 → v3+)](#§0-roadmap-上下文v01--v25--v3)
- [§1 目标定位](#§1-目标定位)
- [§2 范围边界](#§2-范围边界)
- [§3 架构数据流](#§3-架构数据流)
- [§4 模块边界](#§4-模块边界)
- [§5 API 契约](#§5-api-契约)
- [§6 扩展点 / 插件接口](#§6-扩展点--插件接口)
- [§7 错误 + 边界 case](#§7-错误--边界-case)
- [§8 成本契约](#§8-成本契约)
- [§9 测试矩阵](#§9-测试矩阵)
- [§10 向后兼容](#§10-向后兼容)
- [§11 风险登记](#§11-风险登记)
- [Appendix A: SQLite 完整 DDL](#appendix-a-sqlite-完整-ddl)
- [Appendix B: error code 集合](#appendix-b-error-code-集合)
- [Appendix C: Acceptance gates G1-G17](#appendix-c-acceptance-gates-g1-g17)
- [Appendix D: 与父 spec 的差异 / 修订](#appendix-d-与父-spec-的差异--修订)

---

## §0 Roadmap 上下文(v0.1 → v2.5 → v3+)

本 v0.1.0 是大 roadmap 的首切。完整切片表如下,**v1.0 ≠ 全自动**,v2.5 才是受限全自动 GA。

| Phase | 版本 | 主题 | 估时 | 累计 |
|-------|------|------|------|------|
| **A: Semi-auto base** | v0.1.0 | **Listen-only foundation(本文档)** | 3w | 3w |
|  | v0.2.0 | Histogram behavior model | 2w | 5w |
|  | v0.3.0 | Digest + LLM Q&A(cloud-only)| 3w | 8w |
|  | v0.4.0 | Fast-tier(RKLLM/Ollama)+ escalation | 3w | 11w |
|  | v0.5.0 | Time-curve + sequence-miner | 2w | 13w |
|  | v0.6.0 | Intent-router + soft-intention + Audit hash-chain | 3w | 16w |
|  | v0.7.0 | MQTT bridge + smoke | 2w | 18w |
|  | v1.0.0 | RC + GA | 1w | 19w |
| **B: 原 spec §2.3** | v1.1 | 多用户 voice ID | 3w | 22w |
|  | v1.2 | P2P sync | 3w | 25w |
|  | v1.3 | Federation | 3w | 28w |
| **C: Floorplan advisor** | v1.5 | JSON ingest + rule 库 v1 + 报告 | 4w | 32w |
|  | v1.6 | LLM 个性化层 | 2w | 34w |
|  | v1.7 | SVG/DXF 矢量 ingest | 3w | 37w |
| **D: 全自动 5 层** | v2.0 | `occupancy_tracker`(多模态融合)| 4w | 41w |
|  | v2.1 | `intent_classifier`(LLM-driven 意图层)| 4w | 45w |
|  | v2.2 | `action_cost_policy` | 3w | 48w |
|  | v2.3 | `active_query` + feedback retrain | 3w | 51w |
|  | v2.4 | 可解释执行(reason + undo)| 2w | 53w |
|  | v2.5 | **受限全自动 GA**(白名单)| 3w | 56w |
| **E: Advanced(defer)** | v3.0+ | floorplan image / vision agent | TBD | — |

**Positioning 锁死**:
- v1.0 = semi-auto(LLM 提议 + 用户 approve);不承诺全自动
- v2.5 = 受限全自动(白名单内 auto-execute)
- 永远 require user:门锁 / 报警 / 阀门 / 大功率开关(产品红线)

**并行性**:Phase B 与 Phase C 可在不同 worktree 并行;Phase D 必须串行(intent→occupancy→cost→query→explain);Phase D 启动前 A+B GA 落定。

---

## §1 目标定位

### 1.1 v0.1.0 北极星

> 7 天 soak 不掉线 + 用户能用浏览器看到自家 HA 事件流(按**房间**而非按 entity_id)+ 隐私设置可见可改。

### 1.2 为什么是 Listen-only 而不是其它

- **行为模型**(v0.2 histogram)、**Q&A**(v0.3 digest+LLM)、**suggestion**(v0.4 intent-router)都依赖 *稳定的事件 ingest 链路* 和 *正确的拓扑富化*。v0.1.0 不验证这两件,所有上层都会构建在沙地上
- 父 spec §12 timeline 6 周 v0.1.0 一刀切 6 个子系统,违反全局 §7.1 "每个 minor = distinct deliverable" — 本设计拆为 7 个 minor 至 v1.0.0
- **不写 LLM 路径不做学习**是有意为之的克制:Listen-only 失败 = 重写 ha_adapter;Listen+LLM 失败 = LLM 兜底 / 拓扑 / ingest 哪个挂?三选一无从下手

### 1.3 v0.1.0 北极星检查

按 CLAUDE.md `## Privacy is the headline feature`,v0.1.0 的:
- ✅ 没有 LLM 调用,默认零数据外发
- ✅ privacy hide_pattern 在 ingest 即丢,无任何痕迹(不在 DB / jsonl / log)
- ✅ 完全只读 HA,不动设备
- ⚠️ 不"学习"(不学是 v0.1.0 故意,v0.2 开始);Web UI 首页 banner 明示

按 CLAUDE.md `## Project north star "learns you"`:
- ⚠️ v0.1.0 **不**直接服务"learns you" — 它服务"先证 WS 稳 / 先正确富化"
- 允许这一片离北极星;**v0.2 必须回归**

### 1.4 用户视角(per 全局 §2.2)

- 普通用户视角:在家用浏览器 http://nas:8124 看见自家**房间网格**;点客厅看最近事件;觉得某 entity 涉私 → 设置页加 hide 规则
- 已有 HA 用户视角:**不**取代我现有 HA;ai-ha 容器跑在边上,我现有 Lovelace 不受影响
- 隐私敏感用户视角:看 Web UI 设置页能立刻看到 `allow_cloud_llm_with_digest = false` 默认值,放心

### 1.5 解决的痛点 / 不解决的痛点

| 痛点 | v0.1.0 |
|------|------|
| HA 事件流难溯源(entity_id 字典级)| ✅ 房间维度 UI + denormalize 富化 |
| 不知"卧室上次活跃在何时" | ✅ entities.last_seen + areas.is_active |
| 不知哪个 entity 没归类到房间 | ✅ orphan_detector + Web UI 红点 |
| 拓扑改了之后查不到老事件 | ✅ snapshot 版本化 + events.snapshot_id |
| 想要 AI 主动建议自动化 | ❌(v0.4)|
| 想 AI 回答"客厅温度多少" | ❌(v0.3)|
| 想要"我说一句话 AI 替我做事" | ❌(v0.4 之后,且 v2.5 之前仍 semi-auto)|

---

## §2 范围边界

### 2.1 v0.1.0 做(11 件)

1. **ha-adapter**:WS subscribe_events firehose;断连指数退避 1→60s;ping 30s;buffer maxlen=1000
2. **拓扑 ingest**:启动拉 area/device/entity registry 三 list;订阅 `*_registry_updated` 触发 re-snapshot;diff vs 上一版本;snapshot 版本化存储
3. **事件富化**:每条 HAEvent 入库前 join `entity_id → device_id / area_id / device_class`
4. **静态自动分析 4 件**:per-area events_per_hour_24h / per-area device_class 分布 / 房间 is_active / orphan entity 检出
5. **持久化**:SQLite WAL(events / areas / devices / entities / snapshots / counters / privacy_drops / kv_meta);按天 rotate JSONL cold archive
6. **privacy**:hide_pattern 在 enrich 之后、写入之前匹配 → drop;privacy_drops 仅记数不留 entity_id;**默认** `allow_cloud_llm_with_digest = false`
7. **Web UI**:5 页(rooms 网格 / room 详情 / entities / timeline / settings);Jinja2 SSR + < 4 KB CSS + 1 个 timeline.js 动态片;basic auth + signed cookie
8. **配置热更**:watchfiles 监听 `/data/config.toml`,改 privacy / web 不重启
9. **健康 metric**:`/api/health` 返回 6 + 字段(ws_connected/events_per_hour/db_size_mb/uptime_seconds/hidden_event_count/current_topology_snapshot_id 等)
10. **Docker**:沿用现 multi-arch Dockerfile(amd64/arm64/riscv64);CI 同现状 build 3 arch + test amd64
11. **测试 + 文档**:见 §9 / §7.6 RC Gate 1

### 2.2 v0.1.0 不做(写死)

- ❌ 任何 LLM 调用(包括 fast/capable 抽象)
- ❌ Behavior model(histogram / time-curve / sequence-miner)
- ❌ Digest builder
- ❌ Intent router / soft-intention queue
- ❌ Audit hash-chain(留 v0.6 与 intent-router 同步)
- ❌ MQTT bridge(留 v0.7)
- ❌ 多用户 / voiceprint(留 v1.1)
- ❌ HA service_call(完全只读)
- ❌ 自托管 GitHub Actions arm64/riscv64 runner(留 v0.6 接 NPU 时评估)

### 2.3 跨片承诺(给 v0.2+ 的)

- **entities / events 表 schema** 设计为 v0.2 histogram 直接 `GROUP BY entity_id, hour_of_day` 不改表
- **topology snapshot 版本化** 让 v0.5 sequence-miner 能区分"用户改名"前后数据
- **events 富化 area_id** 让 v0.2/v0.5 直接 GROUP BY 房间,无 JOIN
- **不引入第三方 native binding**(避免 v0.2+ 想换 SQLite → DuckDB / RocksDB 时的迁移阻力)

---

## §3 架构数据流

### 3.1 High-level diagram

```
┌────────────────────────────────────────────────────┐
│ Home Assistant Core  :8123                         │
│   ├─ REST  /api/states                             │
│   └─ WS    auth → subscribe_events                 │
│            + config/area_registry/list             │
│            + config/device_registry/list           │
│            + config/entity_registry/list           │
│            + area/device/entity_registry_updated   │
└──────────┬─────────────────────────────────────────┘
           │
           │ 启动:① snapshot 三 registry → ② initial states → ③ subscribe_events
           │ 运行:WS push (state_changed / *_registry_updated)
           ▼
┌────────────────────────────────────────────────────┐
│ ai_ha.ha_adapter                                   │
│   ├─ HAClient            REST 拉 states            │
│   ├─ HAWSClient          单 WS 多 subscription      │
│   └─ TopologyFetcher     拉 + 订阅 registry 增量     │
└──┬─────────────────────────────────────────────┬───┘
   │                                             │
   │ TopologySnapshot                            │ HAEvent(raw)
   │ {snapshot_id, ts, areas[], devices[],       │
   │   entities[]}                               │
   ▼                                             ▼
┌─────────────────────────┐         ┌──────────────────────────┐
│ ai_ha.topology          │         │ ai_ha.ingest             │
│   ├─ store snapshot      │ ◀───── │  step 1 enrich            │
│   │   (versioned, hash) │  join   │   join entity→device→area │
│   ├─ diff vs prev        │  cache │  step 2 privacy filter    │
│   ├─ entity_index cache  │         │  step 3 entity upsert     │
│   └─ orphan detector     │         │  step 4 event insert      │
└──────────┬──────────────┘         │  step 5 per-area counter  │
           │                         └────────┬─────────────────┘
           │                                  │
           ▼                                  ▼
┌────────────────────────────────────────────────────┐
│ SQLite  /data/ai-ha.db (WAL)                       │
│   ├─ topology_snapshots                            │
│   ├─ areas / devices / entities (current state)    │
│   ├─ events (denormalized + snapshot_id)           │
│   ├─ counters_per_area (24h ring)                  │
│   ├─ privacy_drops (count only)                    │
│   └─ kv_meta                                       │
└──────────┬─────────────────────────────────────────┘
           │
           ▼                                ▲
┌──────────────────────┐         ┌─────────┴────────────┐
│ /data/events/        │         │ ai_ha.web FastAPI    │
│  YYYY-MM-DD.jsonl.gz │         │  pages:              │
│  (cold archive)      │         │    /          房间网格 │
│                      │         │    /room/<id> 房间详情 │
│                      │         │    /entities  二级    │
│                      │         │    /timeline  全屋时间 │
│                      │         │    /settings  privacy │
│                      │         │  api:                │
│                      │         │   /api/health        │
│                      │         │   /api/v1/{topology, │
│                      │         │      areas, entities,│
│                      │         │      events, settings│
│                      │         │      /privacy}       │
│                      │         │  ws:                 │
│                      │         │   /api/v1/stream/    │
│                      │         │      events          │
└──────────────────────┘         └──────────────────────┘

watchfiles → /data/config.toml hot-reload (privacy / web)
```

### 3.2 关键 3 条数据流

1. **冷启动**:容器启 → entrypoint seed config → `ai_ha.main` lifespan startup → `ha_adapter.HAClient.authenticate()` → `TopologyFetcher.snapshot()` 拉三 registry → `topology.snapshot_store.insert(payload)` → `entity_index.rebuild()` → `HAClient.fetch_states()` snapshot → entities.last_seen filled → `HAWSClient.subscribe_events()` 起 → 启 ingest pipeline
2. **正常事件**:HA push state_changed → `HAWSClient.on_event(msg)` → 转 `HAEvent` → ingest 5 步流水(enrich `entity_index.lookup()` → privacy filter → entities upsert → events insert → counters_per_area + entities.event_count_24h 增) → 批 100 条或 1 s 任一触发 commit
3. **拓扑变更**:HA push `area_registry_updated` → `TopologyFetcher.refetch_areas()` → diff vs current → 若不同:`snapshot_store.insert(new_payload)` 拿新 snapshot_id → `entity_index.rebuild()` → log "topology changed: <diff_summary>"

### 3.3 数据存储(详见 Appendix A)

| Store | 路径 | 保留 | 备份 |
|-------|------|------|------|
| SQLite | `/data/ai-ha.db`(+ -wal/-shm)| events 30d / 其它永久 | jsonl + 周日 VACUUM |
| Cold archive | `/data/events/YYYY-MM-DD.jsonl.gz` | `archive.retention_days`(默认 365)| — |
| Token | `/data/.admin-token`(0600)| 重置 API 替换 | — |
| Config | `/data/config.toml` | watch + 热更 | — |
| Logs | stdout(Docker)| 由 host 处理 | — |

### 3.4 关键设计选择

- **registry snapshot 版本化** — 不覆盖旧 snapshot;每个 event 记 `snapshot_id` → 老事件永远 join 得回当时的 area
- **enrich at ingest, not at query** — 入库就富化 area_id;查询无需 JOIN;v0.2 histogram 受益
- **privacy 过滤在 enrich 之后** — hidden entity 的 area 算过但不写入 events / log;privacy_drops 仅 count
- **orphan detector** — entity 无 area_id 是产品 affordance,不是错误
- **拓扑变更不重写历史** — version snapshot 思想

### 3.5 异步选型

全栈 asyncio(`httpx.AsyncClient` / `websockets` / `aiosqlite` / `FastAPI`);单 event loop;避免 thread pool。`TopologyFetcher` 与 ingest 共享 WS,通过 message `id` 字段路由。

---

## §4 模块边界

### 4.1 文件树(LOC 预算 < 3500 行 Python)

```
src/ai_ha/
├── __init__.py                     # __version__ = "0.1.0"
├── __main__.py                     # 启动入口
├── main.py                         # async wire-up + lifespan
├── config/
│   ├── __init__.py                 # AppConfig (pydantic-settings)
│   ├── loader.py                   # tomli + env override
│   └── watcher.py                  # watchfiles → reload callback
├── ha_adapter/
│   ├── __init__.py
│   ├── client.py                   # HAClient (REST, httpx)
│   ├── ws_client.py                # HAWSClient (auth/ping/reconnect)
│   └── topology_fetcher.py         # registry pull + diff
├── topology/
│   ├── __init__.py
│   ├── snapshot_store.py
│   ├── entity_index.py
│   └── orphan_detector.py
├── privacy/
│   ├── __init__.py
│   └── hide_matcher.py
├── ingest/
│   ├── __init__.py
│   ├── pipeline.py                 # process(event) 5 步
│   └── counters.py                 # ring buffer / hour bucket
├── store/
│   ├── __init__.py
│   ├── db.py                       # aiosqlite + lifespan + migrations runner
│   ├── migrations/
│   │   └── 001_initial.sql
│   └── dao.py
├── archive/
│   ├── __init__.py
│   └── jsonl_writer.py
├── health/
│   ├── __init__.py
│   └── metrics.py
└── web/
    ├── __init__.py
    ├── app.py
    ├── auth.py
    ├── routes/
    │   ├── health.py
    │   ├── areas.py
    │   ├── entities.py
    │   ├── events.py
    │   ├── topology.py
    │   └── settings.py
    ├── templates/                  # Jinja2 SSR
    │   ├── base.html
    │   ├── rooms.html
    │   ├── room.html
    │   ├── entities.html
    │   ├── timeline.html
    │   └── settings.html
    └── static/
        ├── app.css
        └── timeline.js
```

### 4.2 依赖图(无环)

```
              config(所有人依赖)
                 │
   ┌─────────────┼─────────────┐
   ▼             ▼             ▼
privacy       store         archive
                 │
            ┌────┴───────┐
            ▼            ▼
        topology      health
            │            │
       ┌────┴───┐        │
       ▼        ▼        │
    ingest ◀ ha_adapter  │
       │                 │
       └─────┬───────────┘
             ▼
            web
             ▲
             │
          main(顶层 wire)
```

**边界规则**:
- `privacy` / `archive` 叶子,零项目内依赖
- `store` 接受 dataclass(`EventRow` / `EntityRow`),不知事件来自 HA
- `topology.entity_index` 是**唯一**进程内可变共享状态;rebuild 取整锁,查询无锁(read-only dict 替换)
- `ingest` 不直接调 ha_adapter;接受 `HAEvent` 入参 → 可单测
- `web` 不调 ingest / ha_adapter;只读 `store` 和 `health.metrics`
- `health.metrics` 反向注入收集器到 ingest / ha_adapter(单向依赖)

### 4.3 跨仓边界

- **不**依赖 KVM 仓代码(v0.3 LLM provider 抽象时 vendor 迷你子模块,不引仓)
- **不**fork home-assistant
- Docker base `python:3.11-slim`,**未**切到 `kvm-build-env`(v0.6 RKLLM 接入时再评估)

---

## §5 API 契约

### 5.1 HTTP REST(base `/api/v1`)

| Endpoint | Method | 描述 |
|----------|--------|------|
| `/api/health` | GET | liveness + 6 健康指标 |
| `/api/v1/topology` | GET | 当前 snapshot 摘要 |
| `/api/v1/topology/snapshots` | GET | 历史 snapshot 列表(分页)|
| `/api/v1/topology/snapshots/{id}` | GET | snapshot 全 payload |
| `/api/v1/areas` | GET | 所有房间 + 静态分析 4 件 |
| `/api/v1/areas/{id}` | GET | 单房间详情 + entities + recent events |
| `/api/v1/areas/{id}/entities` | GET | 房间内 entities |
| `/api/v1/entities` | GET | filter `?area_id=` `?orphan=true` `?device_class=` cursor 分页 |
| `/api/v1/entities/{id}/events` | GET | entity 历史事件(分页)|
| `/api/v1/events` | GET | firehose;`?since` `?until` `?area_id` `?entity_id` `?limit` `?cursor` |
| `/api/v1/settings/privacy` | GET | 当前 privacy 配置 |
| `/api/v1/settings/privacy` | POST | 更新(写 config.toml + 热更)|

**v0.1.0 不含**:`/api/v1/ask`(v0.3)/ `/preferences`(v0.2)/ `/suggestions`(v0.4)/ `/audit`(v0.6)/ 任何写 HA 的 endpoint。

### 5.2 WebSocket

| Endpoint | 描述 |
|----------|------|
| `/api/v1/stream/events` | server → client 单向 push;客户端订阅 filter 一次;断了重连;无 ack;reconnect 时 `since_cursor` 拉漏掉的近 N 条 |

### 5.3 Web 页面(Jinja SSR)

| 路径 | 描述 |
|------|------|
| `GET /` | 房间网格首页 |
| `GET /room/{area_id}` | 房间详情 + timeline |
| `GET /entities` | entity 列表 |
| `GET /timeline` | 全屋事件 timeline |
| `GET /settings` | privacy 设置 |
| `GET /login` | token 输入 |

### 5.4 Auth

- **首启**:容器生成 32 byte random token → 写 `/data/.admin-token`(0600)+ stdout 单次显示(红框包围)
- **用户登入**:`GET /login` 输入 token → POST 验证 → 签 `ai-ha-session` cookie(7d 有效)
- **API 直调**:HTTP Basic(`admin:<token>`)或 cookie
- **`web.require_auth = false`**:仅在 trusted reverse proxy 后允许;启动时 stdout 红字 warn

### 5.5 错误模型

```json
{
  "error": "ha-unreachable",
  "detail": "Cannot connect to http://homeassistant.local:8123 after 5 retries",
  "trace_id": "req-2026-...-abc123"
}
```

error code 完整集合见 Appendix B。

### 5.6 Graceful degradation

HA WS 断时,API 仍返回**最后已知 state** + header `X-AI-HA-Stale: true` + body 加 `"stale_seconds": N`。/api/health `status` 字段从 "healthy" → "degraded"。

---

## §6 扩展点 / 插件接口

**v0.1.0 不开放**外部 plugin contract — behavior plugin 协议(`BehaviorPlugin` 类)在 v0.2 才需要,推到那时定义。

**v0.1.0 仅做**:
- 启动期日志:`[ai-ha] plugins: 0 loaded (extension API arrives in v0.2)`
- `/data/plugins/` 目录预留(entrypoint 创建)
- `kv_meta` 表为后续 plugin metadata 预留(暂不写)

**v0.2 锁定的 plugin contract 草案**(放在这里仅为告知,v0.1.0 不实现):

```python
class BehaviorPlugin(Protocol):
    name: str
    version: str
    def observe(self, event: HAEvent, ctx: BehaviorContext) -> None: ...
    def query(self, prompt_context: dict) -> Optional[PreferenceContribution]: ...
```

drop `*.py` 进 `/data/plugins/` → v0.2 启动期 importlib 装载。

---

## §7 错误 + 边界 case

14 case + 启动 self-check 12 步 + 退出码,本节自包含。

简要总览:

| 类 | case 数 | 详见 brainstorming §6 |
|----|:---:|------|
| HA 连接 | 4 | ha-unreachable / ha-auth-invalid / ws-disconnected / topology-refresh-failed |
| 配置 | 3 | config-invalid / hide-pattern-invalid / env-missing |
| SQLite | 3 | db-busy / disk-full / db-corrupted |
| Backpressure | 1 | ingest-backpressure |
| 时钟时序 | 1 | clock-skew |
| 容器生命周期 | 1 | SIGTERM graceful shutdown |
| Web 安全 | 1 | XSS / CSRF |

**graceful degrade 总原则**(per 全局 §4.5):
- HA 断 → 服务不挂,返 stale + header 标记
- DB 慢 → in-mem buffer,不丢
- 配置坏 → 启动期 fail-fast / 运行期 ignore
- privacy 编译失败 → 旧 pattern 继续生效
- DB 损坏 → rename + 新建空 DB,服务连续(数据连续让位)

**禁止 silent failure**(per 全局 §5.2): `except: pass` 全文 grep 0;每个 `try` 块至少一个 `logger.error` / `logger.warning`。

### 7.1 启动 self-check 12 步

```
1. load config (fail → exit 78)
2. compile privacy regex (fail → exit 78)
3. open DB + apply migrations (fail → exit 70)
4. integrity check (fail → rename + new DB, log critical)
5. start health metrics collector
6. start ha_adapter (REST snapshot try once;fail OK,后台重试)
7. start topology fetcher (fail OK,后台重试)
8. start ingest pipeline
9. start jsonl writer
10. start watchfiles on /data/config.toml
11. start FastAPI / web
12. log "ai-ha started, schema_version=N, topology=<snapshot_id|pending>"
```

1-3 失败 → exit non-zero(docker restart 拉起)。4 之后失败 → degraded 跑,等 Web UI 介入。

### 7.2 退出码

| code | 含义 |
|------|------|
| 0 | normal SIGTERM |
| 70 | DB unrecoverable |
| 78 | config error |
| 64 | usage error |
| 130 | SIGINT |

---

## §8 成本契约

修订父 spec §8(容量上调,反映真传感重度家庭):

| Resource | v0.1.0 量 |
|----------|----------:|
| Docker 镜像 | ~250 MB(uncompressed,multi-arch)|
| RAM sustained | 150-300 MB |
| RAM peak(snapshot rebuild / batch flush)| 500 MB |
| Disk DB | 50-500 MB / yr(普通家庭 30d 保留)|
| Disk jsonl archive | **100 MB-5 GB / yr**(取决于事件率,gzip 后)|
| Network 外发 | 0(默认无 LLM)|
| CPU sustained | 1 core(主要在 ingest pipeline + asyncio loop)|
| CPU peak | 2 cores(snapshot rebuild + batch + Web 并发查询)|

**Cost target**:**0** cloud cost in default config(v0.1.0 无 LLM)。v0.3+ 接 LLM 后按 provider 计费。

**首次部署 prereq**:
- Docker / docker compose
- 一个已运行的 HA Core(任意 2025.x+ 版)
- HA long-lived access token(用户在 HA Profile → Security 生成)
- 500 MB free 给容器 + 持久数据
- 任意 amd64 / arm64 主机(riscv64 仅 buildx 验过,无 native 运行测)

---

## §9 测试矩阵

本节自包含。结构 + acceptance gates 数量,详见 Appendix C。

### 9.1 测试代码 layout

```
tests/
├── TEST_PLAN.md
├── MANUAL_TEST_CHECKLIST.md
├── conftest.py
├── unit/           # 7 个文件,~30 用例
├── integration/    # ~14 个文件,~60 用例,启 mock HA WS
├── perf/           # 3 bench(criterion-like)
└── soak/           # 7 d 真程序运行 harness
```

### 9.2 6 类下限对应(per 全局 §6.1)

| 类 | v0.1.0 用例 |
|----|------|
| happy path | 100 条 state_changed → 全落盘 + UI |
| edge case | empty state / 256 char name / 中文 emoji / orphan / ts=0 |
| error case | §7 全 14 case → 14 独立测 |
| adversarial | XSS / regex DoS / oversized limit / cookie tamper |
| 多并发 | 100 并发 GET + 100 evt/s ingest |
| 资源耗尽 | disk-full / db-lock storm / OOM |
| i18n | 中文 entity / area 名 |
| 降级 | HA WS 断 30s → stale header 验证 |

### 9.3 Acceptance gate G1-G17

17 个量化 gate,GA 必须 17/17(无例外)。详见 Appendix C。

**G1 7 d soak 不可 mock**(per 全局 §6.3 baseline SOP):必须真镜像 + 真 HA(或 long-running mock + 模拟 5 次随机断线)+ 真 wallclock 168 h。

### 9.4 RC 4 Gate(per 全局 §7.2)

| Gate | v0.1.0 落实 |
|------|------|
| Gate 1 文档 | README / DEVELOP / RELEASE / spec 与代码无漂移 |
| Gate 2 代码 | pytest --cov 80%/60% + ruff + mypy --strict;0 skip;0 WIP/TODO/FIXME-CRITICAL |
| Gate 3 功能预期 | 每条 Highlight 真跑过 + 截图 `docs/screenshots/v010-ga-verification/` |
| Gate 4 缺口 | RELEASE 明示 "v0.1.0 = Listen-only foundation;不学不答不动;riscv64 仅构建无运行测" |

### 9.5 Release 本机部署验证(per 全局 §7.3)

GA tag 前:
1. GH Actions release.yml 出 v0.1.0 GHCR image
2. 真 RK3588 板(primary target)拉镜像 docker run + 真 HA + 真 token
3. 真浏览器走 G5/G6/G7/G8/G9 五个 acceptance
4. 截图 / log / journal → `docs/screenshots/v010-ga-verification/`
5. 证据进 RELEASE.md v0.1.0 节 "verification evidence"

dev `python -m ai_ha` ≠ ship-ready 验证(per 全局 §7.3 红线)。

---

## §10 向后兼容

### 10.1 SQLite schema 版本

- v0.1.x 内只**加表 / 加列**,不删 / 不改类型
- v0.1 → v0.2 加 histograms 表 → `002_*.sql`(不动 001)
- v0.x → v1.x:评估是否 major bump;若 schema 兼容,minor migration;若 break,v1.0 release 提供 export-import CLI
- migration framework 强约束:每个 `NNN_*.sql` 一个 transaction;`kv_meta.schema_version` 与 migration 同 transaction 更新;失败 → 回滚 + 启动失败

### 10.2 配置文件兼容

- v0.1.x 内新增 `[section]` 不破坏旧 config;新增字段必有默认值
- v0.1 → v0.2 删除某 section / 字段 → entrypoint 升级期跑 `config_migrator.py` 提示用户

### 10.3 HA API 版本

- v0.1.0 **tested against**:HA 2025.x(每月 release)+ HA 2026.x(到本 spec 日期)
- 启动期探测 HA version → `kv_meta.ha_version_seen`
- 不识别字段 → log warning 不挂
- `*_registry_updated` 在 HA < 2024 不存在 → fall back 60s 轮询 list(degraded 模式)
- 每月人工 watch HA changelog(进 RELEASE.md "tested HA versions" 节)

### 10.4 Docker image

- `:latest` = bleeding edge,生产**不**用
- 生产 pin `:v0.1.0` 精确 tag
- v0.1.x 内不破坏 env var 名 / volume mount / port

---

## §11 风险登记

15 条风险 + severity + mitigation + §7 兜底映射 + acceptance 影响。Top 5 列于下表,完整 15 条见 §11.1。

**Top 5 关注**(severity S1-S2):

| # | 风险 | Severity | Mitigation 摘要 |
|---|------|:---:|------|
| 7 | HA token 泄漏(若用户复制 docker log 到 issue)| **S1** | 强制 env 注入;严禁写 config.toml;entrypoint 检测拒绝 |
| 1 | HA WS API 兼容性变化 | S2 | 探测 ha_version;每月 watch changelog;CI 加 mock-against-version 矩阵 |
| 3 | privacy regex catastrophic backtracking | S2 | re2 fallback + 复杂度 heuristic + POST 时拒绝 |
| 4 | SQLite WAL 损坏(容器突死)| S2 | 启动期 integrity_check;case 10 rename + 新建;soak 必含 3× SIGKILL |
| 9 | 高事件率家庭 → SQLite IOPS 顶不住 | S2 | retention 默认 30d;ingest batch 自适应;v0.2+ 评估 RocksDB |
| 15 | UX disappointment("AI 在哪")| S2 | UI 首页 banner "v0.1.0 = Listen-only foundation;suggestions arrive in v0.4" |

**Runtime 监控**:`ha_version_seen / ha_registry_event_mode / privacy_regex_compile_fail_total / wal_recovery_count / config_reload_fail_total` 暴露 `/api/health`;非零 → Web UI 健康卡 yellow。

**推后到后续 minor 的风险**:
- 高 event rate → RocksDB / Postgres → v0.2+
- LLM rate limit → v0.3+
- audit tamper → v0.6+
- 传感器布置盲区 → v1.5+ floorplan advisor

### 11.1 完整 15 条风险登记

| # | 风险 | Severity | Mitigation | §7 兜底 | 影响 G |
|---|------|:---:|------|:---:|:---:|
| 1 | HA WS API 兼容性变化 | S2 | 启动期探测 ha_version → kv_meta;不识别字段 log warn 不挂;月 watch HA changelog;CI 加 mock-against-HA-version 矩阵 | case 1 | G5, G6 |
| 2 | `*_registry_updated` 在 HA < 2024 不存在 | S3 | fall back 到 60s 轮询;启动 log 显式;Web UI 横幅 | — | G6 |
| 3 | Privacy regex catastrophic backtracking | S2 | re2 fallback + POST 时复杂度 heuristic 拒绝 | case 6 | G7 |
| 4 | SQLite WAL 损坏(SIGKILL 突死)| S2 | 启动期 integrity_check;case 10 走 rename + 新建;soak 必含 ≥ 3× SIGKILL 验证 | case 10 | G1, G12 |
| 5 | arm64/riscv64 wheel 缺失 | S3 | CI buildx 3 arch 已验;锁版本 + 月 wheel 巡检;RELEASE 附 SBOM | — | G17 |
| 6 | admin token 从 stdout 泄漏 | S2 | first-run 红框 ASCII art;`/data/.admin-token`(0600)是 SSOT;Web UI 重置 token | — | — |
| 7 | HA token 泄漏 | **S1** | **强制 env 注入**;严禁写 config.toml;entrypoint 检测拒绝 | — | — |
| 8 | watchfiles 读 config.toml 半文件 | S3 | sleep 50ms 再读;读失败保旧配 + warn | case 6 | G8 |
| 9 | 高 event rate(智能家)IOPS 顶不住 | S2 | retention 默认 30d;batch 自适应;RELEASE Known Limitations 注上限 ~5k evt/h on eMMC;v0.2+ 评估 RocksDB | case 11 | G11, G12 |
| 10 | python:3.11-slim base CVE | S2 | release.yml 加 trivy/grype scan;月底 rebuild latest | — | — |
| 11 | SIGKILL → 内存 deque 1000 事件丢 | S3 | RELEASE 标 "不保证 SIGKILL 期间 buffer 不丢";可调 buffer;v0.6+ 评估 WAL 落盘 buffer | case 13 退化 | G4 |
| 12 | HA system clock 错 → event ts 倒退 | S3 | 以 received_at 为聚合主键;Web UI 健康卡显示 skew | case 12 | G3 |
| 13 | JSONL cold archive 累积 → 1 GB+/yr | S3 | `archive.retention_days`(默认 365)+ `archive.compress = true`;RELEASE 容量预估 | — | — |
| 14 | Schema migration mid-version 失败 | S2 | 每 migration 单 tx;`schema_version` 与 tx 同提交;migration 跑前 `cp ai-ha.db ai-ha.db.pre-migration-NNN`;失败 stderr 指明回滚 | case 10 邻居 | — |
| 15 | UX disappointment(用户期 "AI" 见 "Listen") | S2 | Web UI 首页 banner "v0.1.0 = Listen-only foundation;suggestions arrive in v0.4";RELEASE.md "What this is NOT yet" 节 | — | — |

### 11.2 Runtime 风险监控

`/api/health` 暴露 metric:
- `ha_version_seen`
- `ha_registry_event_mode`(push|poll)
- `privacy_regex_compile_fail_total`
- `wal_recovery_count`
- `config_reload_fail_total`

非零 → Web UI 健康卡 yellow;持续 5 min → log error。

---

## Appendix A: SQLite 完整 DDL

文件 `src/ai_ha/store/migrations/001_initial.sql`。

PRAGMA(连接初始化):

```sql
PRAGMA foreign_keys = OFF;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA temp_store = MEMORY;
PRAGMA mmap_size = 268435456;
PRAGMA busy_timeout = 5000;
PRAGMA cache_size = -32000;
```

表 DDL(8 张表 + 索引):

```sql
-- 元数据
CREATE TABLE kv_meta (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_at  INTEGER NOT NULL
) WITHOUT ROWID;

-- 拓扑 snapshot(append-only)
CREATE TABLE topology_snapshots (
    snapshot_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    ts           INTEGER NOT NULL,
    payload_hash TEXT    NOT NULL,
    payload      TEXT    NOT NULL,
    diff_summary TEXT,
    UNIQUE(payload_hash)
);
CREATE INDEX idx_topology_ts ON topology_snapshots(ts DESC);

-- areas
CREATE TABLE areas (
    area_id        TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    floor_id       TEXT,
    icon           TEXT,
    aliases        TEXT,
    snapshot_id    INTEGER NOT NULL,
    first_seen_at  INTEGER NOT NULL,
    last_seen_at   INTEGER NOT NULL
) WITHOUT ROWID;
CREATE INDEX idx_areas_floor ON areas(floor_id);
CREATE INDEX idx_areas_snapshot ON areas(snapshot_id);

-- devices
CREATE TABLE devices (
    device_id      TEXT PRIMARY KEY,
    name           TEXT,
    manufacturer   TEXT,
    model          TEXT,
    area_id        TEXT,
    sw_version     TEXT,
    snapshot_id    INTEGER NOT NULL,
    first_seen_at  INTEGER NOT NULL,
    last_seen_at   INTEGER NOT NULL
) WITHOUT ROWID;
CREATE INDEX idx_devices_area ON devices(area_id);
CREATE INDEX idx_devices_snapshot ON devices(snapshot_id);

-- entities
CREATE TABLE entities (
    entity_id          TEXT PRIMARY KEY,
    friendly_name      TEXT,
    domain             TEXT NOT NULL,
    device_class       TEXT,
    device_id          TEXT,
    area_id            TEXT,
    disabled           INTEGER NOT NULL DEFAULT 0,
    snapshot_id        INTEGER NOT NULL,
    first_seen_at      INTEGER NOT NULL,
    last_seen_at       INTEGER NOT NULL,
    event_count_24h    INTEGER NOT NULL DEFAULT 0,
    total_event_count  INTEGER NOT NULL DEFAULT 0
) WITHOUT ROWID;
CREATE INDEX idx_entities_area ON entities(area_id);
CREATE INDEX idx_entities_device ON entities(device_id);
CREATE INDEX idx_entities_class ON entities(device_class);
CREATE INDEX idx_entities_domain ON entities(domain);
CREATE INDEX idx_entities_snapshot ON entities(snapshot_id);
CREATE INDEX idx_entities_orphan ON entities(area_id) WHERE area_id IS NULL;

-- events
CREATE TABLE events (
    event_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts                INTEGER NOT NULL,
    received_at       INTEGER NOT NULL,
    entity_id         TEXT NOT NULL,
    event_type        TEXT NOT NULL,
    old_state         TEXT,
    new_state         TEXT,
    context_user_id   TEXT,
    context_parent_id TEXT,
    area_id           TEXT,
    device_id         TEXT,
    device_class      TEXT,
    snapshot_id       INTEGER NOT NULL
);
CREATE INDEX idx_events_ts ON events(ts DESC);
CREATE INDEX idx_events_entity_ts ON events(entity_id, ts DESC);
CREATE INDEX idx_events_area_ts ON events(area_id, ts DESC);
CREATE INDEX idx_events_received ON events(received_at DESC);

-- per-area 小时聚合(24h ring)
CREATE TABLE counters_per_area (
    area_id          TEXT NOT NULL,
    hour_bucket_utc  INTEGER NOT NULL,
    event_count      INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (area_id, hour_bucket_utc)
) WITHOUT ROWID;
CREATE INDEX idx_counters_bucket ON counters_per_area(hour_bucket_utc DESC);

-- privacy 丢弃 metric
CREATE TABLE privacy_drops (
    hour_bucket_utc  INTEGER PRIMARY KEY,
    drop_count       INTEGER NOT NULL
) WITHOUT ROWID;
```

容量预估(per 普通 vs 高传感家庭):

| 项 | 普通 | 高传感 |
|----|------|------|
| entities | 30-50 | 200-500 |
| events / day | 500-2000 | 10k-50k |
| events 表 30d | 5-30 MB | 100-500 MB |
| jsonl 30d(gzip)| 10-50 MB | 200 MB-1 GB |

---

## Appendix B: error code 集合

kebab-case。HTTP code 在括号内。

| code | HTTP | 含义 |
|------|------|------|
| `ha-unreachable` | 503 | HA REST/WS 持续连不上 |
| `ha-auth-invalid` | — | HA token 错(log only,非 HTTP)|
| `ws-disconnected` | 503 | WS 暂断,重连中(degraded 但可读 stale)|
| `topology-not-ready` | 503 | 首次 snapshot 未完成(< 30 s after start)|
| `topology-refresh-failed` | — | registry 刷新失败(log only)|
| `config-invalid` | 422 | TOML 解析 / pydantic 校验失败 |
| `hide-pattern-invalid` | 422 | hide_entities_pattern regex 编译失败 |
| `env-missing` | — | HA_URL/HA_TOKEN 等必需 env 缺失(启动 stderr)|
| `db-busy` | 503 | SQLite lock > timeout |
| `disk-full` | 507 | 磁盘满 |
| `db-corrupted` | — | DB integrity check 失败(log critical)|
| `ingest-backpressure` | — | metric only |
| `clock-skew` | — | metric only / warning |
| `auth-required` | 401 | 缺 token / cookie |
| `auth-invalid` | 401 | token 错 |
| `csrf-fail` | 422 | POST 缺 Origin/Referer |
| `not-found` | 404 | id 不存在 |
| `bad-cursor` | 400 | cursor 解析失败 |
| `payload-too-large` | 413 | limit > 1000 |

---

## Appendix C: Acceptance gates G1-G17

| # | 维度 | 量度 | 通过判据 | 视角 |
|---|------|------|---------|------|
| G1 | WS 稳定 | 7d soak uptime | ≥ 99.5% | 黑盒(真 HA / 真 wallclock)|
| G2 | 断线恢复 | reconnect | 中位 < 5s, p95 < 30s | 灰盒 |
| G3 | Ingest 吞吐 | 入库 p99 | < 100 ms | 灰盒 |
| G4 | 事件不丢(在线)| HA 推 N ↔ DB 落 N | diff = 0 | 黑盒 |
| G5 | 拓扑一致 | count 匹配 HA UI | 100% | 黑盒 |
| G6 | 拓扑变更感知 | 改 entity → 新 snapshot | ≤ 5s | 黑盒 |
| G7 | Privacy 真生效 | hide 100 命中 → 0/0/0 | 0 in DB / 0 in jsonl / 0 in log | 黑盒(grep)|
| G8 | Privacy 热更 | POST → 生效 | < 5s | 黑盒 |
| G9 | Web UI | 3 浏览器 × 移动 viewport | 0 console error | 黑盒 |
| G10 | API 响应 | /health p99, /areas p99 | < 50ms / < 200ms | 灰盒 |
| G11 | 资源占用 | sustained / peak RAM | < 300 / < 500 MB | 灰盒 |
| G12 | DB 增长 | 每 1k events | < 50 MB(含 WAL)| 灰盒 |
| G13 | 单元覆盖 | line / branch | ≥ 80% / ≥ 60% | 白盒 |
| G14 | 集成覆盖 | endpoint + WS | 14/14 PASS | 灰盒 |
| G15 | 无 silent failure | except: pass count | 0 | 白盒 |
| G16 | 文档同步 | manual checklist | 100% | 黑盒 |
| G17 | 多 arch 可启 | amd64 native test PASS + amd64/arm64/riscv64 buildx PASS + **真 RK3588 板** manual `/api/health` 200 | 3 builds + 1 真机 PASS;riscv64 仅 buildx 无 runtime(用户授权"暂只做 3588")| 黑盒 |

GA 必须 17/17。

---

## Appendix D: 与父 spec 的差异 / 修订

本 v0.1.0 sub-spec 相对于 `docs/specs/2026-05-25-ai-home-assistant-architecture.md`:

| 父 spec | 本设计 | 备注 |
|---------|--------|------|
| §0.5 K3 RISC-V CI from day one | 推到 K3 硬件到位再说 | 用户授权;真硬件 > qemu 幻影 |
| §2.1 v1.0 必须 6 子系统 | 拆为 v0.1-v0.7 共 7 个 minor | 全局 §7.1 版本拆解 |
| §2.3 v1.0+ roadmap 只到 v2.0 vision agent | 补 Phase C(floorplan advisor)+ Phase D(全自动 5 层 v2.0-v2.5)| 用户授权 |
| §8 容量"100-500 MB / yr" | "DB 50-500 MB + jsonl 100 MB - 5 GB / yr" | 高传感场景修正 |
| §11 风险 12 条 | 扩为 15 条 + 添加 severity / §6 兜底映射 | 全局 §3.1 节 11 加强 |
| §12 timeline 6 周 v0.1.0 一刀切 | 19 周到 v1.0 GA(7 minor + RC)| 不允许跳 minor |
| §13 open question 5 | 全部回答(Python / vanilla JS / slim / HA STT / RK3588 only)| 用户授权,锁定 |

**未在本设计修订的**:父 spec §1 / §3 / §4 / §5 / §6 / §7 / §9 / §10 仍有效作为 v1.0 全景。本设计**只 scope to v0.1.0**。

---

**End of v0.1.0 design spec.**
