# ai-home-assistant v0.1.5 — Deployment + UI Optimization Design

**Date**: 2026-06-03
**Status**: Design spec (brainstorming-derived 2026-06-03), awaiting user final approval
**Authors**: AI working session (per global `~/.claude/CLAUDE.md` §3.1 11-节 spec 铁律)
**Parent**: `docs/superpowers/specs/2026-06-02-ai-home-assistant-v010-listen-only-design.md` (v0.1.0 全景)
**Implements**: v0.1.5 (bundled minor — 一键部署 + UI 优化,Phase A 之后插入)
**Pre-requisite**: v0.1.0 GA tagged + verified on RK3588

---

## 目录(TOC)

- [§0 Roadmap 调整](#§0-roadmap-调整)
- [§1 目标定位](#§1-目标定位)
- [§2 范围边界](#§2-范围边界)
- [§3 架构数据流](#§3-架构数据流)
- [§4 模块边界](#§4-模块边界)
- [§5 API 契约](#§5-api-契约)
- [§6 扩展点](#§6-扩展点)
- [§7 错误 + 边界 case](#§7-错误--边界-case)
- [§8 成本契约](#§8-成本契约)
- [§9 测试矩阵](#§9-测试矩阵)
- [§10 向后兼容](#§10-向后兼容)
- [§11 风险登记](#§11-风险登记)
- [Appendix A: install.sh 详细流程](#appendix-a-installsh-详细流程)
- [Appendix B: Dashboard layout 规格](#appendix-b-dashboard-layout-规格)
- [Appendix C: i18n key 清单](#appendix-c-i18n-key-清单)
- [Appendix D: Acceptance gates G1-G8](#appendix-d-acceptance-gates-g1-g8)

---

## §0 Roadmap 调整

| Phase | 原 plan(2026-06-02 spec)| 调整(本 spec)|
|------|------|------|
| A.1 | v0.1.0 Listen-only | 不动,v0.1.0-rc.1 已 tag,GA 待 RK3588 验证 |
| **A.1.5** | (未规划)| **本 spec 插入:v0.1.5 Deploy + UI**(3.5 周)|
| A.2 | v0.2.0 Histogram | 后推 3.5 周,slot 名 + scope 不变 |
| A.3+ | v0.3-v1.0 | 串行后推 3.5 周 |

**总 v1.0 GA 时间影响**:原 19 周 → 22.5 周(+3.5 周)。

**v0.1.5 这 3.5 周值不值**:
- 一键部署门槛 -50% → Beta 用户数 + 易用 acceptance gate(per 全局 §8.1 上云项目"易用")
- Dashboard 让 v0.2 histogram 一上来就有可视化承载 → v0.2 工作量 -20%(不用再造 dashboard)
- 响应式 / i18n 让 GA 路线 mobile-friendly + 中文用户友好 — v1.0 之前必做,提前做更便宜

---

## §1 目标定位

### 1.1 v0.1.5 北极星

> 不懂 Docker 的人 30 分钟内装上 ai-home-assistant 并爱上首页。

两条腿:
- **A. 装得上**:一键 install.sh,30 min wall-clock 含 HA token 引导
- **B. 看得懂**:/dashboard 首页 C+B 合体(房间卡片 + 实时事件流)+ 移动端可用 + 中文翻译

### 1.2 衡量指标

| 维度 | 指标 | 目标 |
|------|------|------|
| 装机时长 | 从 curl 到看到 /dashboard | < 30 min(p95)|
| 装机失败率 | install.sh exit non-zero / 总尝试 | < 10% on Debian/Ubuntu LTS |
| Mobile 可用 | iPhone Safari + Android Chrome 5 页无 console error | 100% |
| i18n 完整 | zh-CN 翻译覆盖 | ≥ 95% UI strings |
| Live update p99 | room_state event 端到端 | < 100ms |
| Dashboard p99 | GET /api/v1/dashboard | < 300ms |

### 1.3 用户视角(per 全局 §2.2)

| 用户类型 | 现痛点(v0.1.0)| v0.1.5 改善 |
|---------|------------|-----------|
| 极客 self-hoster | 需手动 docker compose + token | install.sh 自动化,token 引导明示 |
| 准用户 / NAS 玩家 | 看不懂 docker compose 文件 | 一行 curl 命令 |
| 中文母语用户 | UI 全英 | zh-CN 翻译,nav 切换 |
| 移动端访问 | rooms grid 在手机上挤 | mobile-first 响应式 |
| 想随时看家 | rooms 静态,要刷新 | live update,自动更新 |

### 1.4 不直接服务北极星(写死)

- **v0.1.5 仍不学不答** — 与父 spec §1.3 同。一切 AI 留 v0.2+
- **v0.1.5 仍不动 HA** — read-only。soft-intention 留 v0.6

---

## §2 范围边界

### 2.1 做(6 件)

1. **`install.sh`**(repo root)+ README curl-pipe — Level 2 交互式 install
2. **`/dashboard`** 新页(C+B 合体)+ `/` redirect → /dashboard
3. **响应式 / Mobile-first** — 重写 app.css,3 关键页(/, /room/{id}, /timeline)适配 320/480/768/1100
4. **i18n** — Babel + gettext + zh-CN 翻译 + nav lang switcher
5. **Live update** — `EventBroadcaster` 新增 `room_state` 消息;rooms / room / dashboard 三页 JS 订阅
6. **`GET /api/v1/dashboard`** — 单 endpoint 聚合数据(给 dashboard.js 用 + initial SSR)

### 2.2 不做(写死)

- ❌ Web installer(install.ai-ha.io)— Level 3,推 v0.2+
- ❌ SBC OS image — Level 4,推 v0.3+
- ❌ Light/Dark toggle、Onboarding tour、搜索/过滤/排序 — 推 v0.2 或更晚
- ❌ React/Vue 重写 — 永远不(Jinja SSR 是产品 spec 北极星)
- ❌ 多用户、voice ID(per 父 spec § 2.2,留 v1.1)
- ❌ 写 HA(仍只读)

### 2.3 跨片承诺(给 v0.2+)

- **dashboard data shape** 设计为 v0.2 histogram 直接补字段(events_per_hour_by_dow)
- **i18n key 提取**为 gettext 标准,v0.2-v1.0 新页只加翻译不改架构
- **WS room_state 消息** 为 v0.4 fast-tier escalation 留扩展位(新增 message type 不改 protocol)
- **install.sh** 设计为可被 v0.3 Web installer 复用 underlying shell 函数

---

## §3 架构数据流

### 3.1 一键部署链路

```
USER PC                                目标主机 (RK3588 / NAS / VM)
─────                                  ────────────────────────────
                                       ┌─────────────────────────┐
1. curl install.sh | bash ─────────────▶│ install.sh              │
                                       │  ① prereq check        │
                                       │     docker / compose /  │
                                       │     ports 8123, 8124   │
                                       │  ② docker pull         │
                                       │     ha-core stable      │
                                       │     ai-home-assistant   │
                                       │  ③ docker compose up   │
                                       │     -d homeassistant    │
                                       │  ④ wait HA :8123 health│
                                       │     ≤ 60s, retry 6×    │
                                       └────────┬────────────────┘
                                                │ stdout 提示
2. 浏览器开 http://<host>:8123 ──◀───────────────┘ "Open <host>:8123, create
3. HA UI 注册 account                              account, then go to
4. HA Profile → Security                           Profile > Security >
   Create long-lived access token                  Create LL token"
5. 复制 token, 终端 stdin 贴 ───────────▶┌──────────────────────────┐
                                       │ install.sh               │
                                       │  ⑤ validate token       │
                                       │     curl -H Bearer ...  │
                                       │     GET /api/states     │
                                       │  ⑥ 写 .env (HA_TOKEN)  │
                                       │     0600                │
                                       │  ⑦ docker compose up   │
                                       │     -d ai-home-assistant│
                                       │  ⑧ wait /api/health 200│
                                       │  ⑨ 打印 banner:        │
                                       │     ─────────────────  │
                                       │     ai-ha is ready!     │
                                       │     URL: http://<h>:8124│
                                       │     admin token:        │
                                       │     <usWIqsi4...>       │
                                       │     ─────────────────  │
                                       └─────────────────────────┘

6. 浏览器开 http://<host>:8124 → /dashboard
```

**Idempotency** — install.sh 可重跑:
- 检测 container 已存在 → 重用
- HA token 已存在 .env → 跳过引导
- 重跑等于 "确认安装健康"

**Trap on abort** — Ctrl-C 触发 cleanup:
- 删未注册 container
- 不删用户数据(volumes / .env)
- 提示用户:"中途退出。重跑 install.sh 即可恢复"

### 3.2 UI 数据流(新增)

```
HA event (state_changed)
   │
   ▼
ingest.pipeline._commit_locked()
   │  既有路径不变
   ├──► events 表 insert
   ├──► entities upsert
   ├──► counters_per_area increment
   │
   │  新增路径
   └──► broadcaster.publish({
          "type": "room_state",
          "area_id": "<from event>",
          "last_seen_at": ts_ms,
          "active": True
        })
        │ 每 area 节流 1/sec(避免高频抖)
        ▼
   ┌──────────────────────────────┐
   │ EventBroadcaster (现有,扩展) │
   │   fanout to WS subscribers   │
   └────────┬─────────────────────┘
            │
   ┌────────┴────────────┐
   ▼                     ▼
WS /api/v1/stream/events   (浏览器订阅)
            │
            ▼
   ┌──────────────────────────────────────┐
   │ Browser: dashboard.js / rooms.js /   │
   │          room-live.js                │
   │  根据 msg type 路由:                  │
   │   - state_changed → live event 流    │
   │   - room_state    → 房间卡片状态更新 │
   │                                      │
   │  DOM 更新 ALL 用 textContent /        │
   │  createElement(per 父 spec §7 XSS)   │
   └──────────────────────────────────────┘
```

### 3.3 i18n 数据流

```
GET / (Jinja render)
   │
   ▼
locale_from_request(req):
   1. req.query["lang"] ("en" | "zh") → 写 cookie
   2. cookie "ai-ha-lang"
   3. req.headers["Accept-Language"]
   4. fallback "en"
   │
   ▼
gettext.translation("ai_ha", localedir, [locale]).gettext
   │
   ▼
Jinja env.install_gettext_translations(t)
   │
   ▼
模板 {% trans %}Rooms{% endtrans %}
   → "Rooms" (en) or "房间" (zh_CN)
```

### 3.4 Dashboard 数据流

```
GET /dashboard
   │ SSR initial render: rooms[] + last_50_events seed
   ▼
浏览器加载 → 启动 dashboard.js
   │
   ├─► fetch /api/v1/dashboard  ← initial JSON 数据(可重)
   │     {
   │       health: {...HealthMetrics snapshot},
   │       rooms: [{area_id, name, entity_count, device_class_distribution,
   │                last_seen, active}, ...],
   │       recent_events: [{ts, entity_id, event_type, area_id}, ...50]
   │     }
   │
   └─► WebSocket /api/v1/stream/events
         │
         ▼
   分流处理:
     - state_changed → 加到 live events 侧栏(top), > 50 行 drop oldest
     - room_state    → 找 area_id 对应卡片 → 更新 last_seen / active 状态
     - 健康指标 → 30s 一次 polled (HTTP GET /api/health)
```

---

## §4 模块边界

### 4.1 文件树(新增 / 改动,~1600 LOC)

```
# === 部署 ===
install.sh                              ~150 行  new
README.md                               +30 行   update(curl 命令置顶)
docker/docker-compose.with-ha.yml       +10 行   update(env_file 引用)
.env.example                            ~15 行   new

# === UI 后端 ===
src/ai_ha/web/routes/dashboard.py       ~80 行   new
src/ai_ha/web/routes/pages.py           +20 行   update(/ → /dashboard redirect + lang)
src/ai_ha/web/routes/stream.py          +30 行   update(room_state msg)
src/ai_ha/ingest/pipeline.py            +25 行   update(publish room_state in commit)
src/ai_ha/web/i18n/__init__.py          ~40 行   new(Babel wrapper)
src/ai_ha/web/i18n/babel.cfg            ~15 行   new(Babel config)
src/ai_ha/web/i18n/locales/en/LC_MESSAGES/ai_ha.po  auto-extracted
src/ai_ha/web/i18n/locales/zh_CN/LC_MESSAGES/ai_ha.po  ~150 entries
src/ai_ha/web/i18n/locales/zh_CN/LC_MESSAGES/ai_ha.mo  compiled(commit gitignored)

# === UI 前端 ===
src/ai_ha/web/templates/dashboard.html  ~120 行  new
src/ai_ha/web/templates/base.html       +15 行   update(lang switcher + viewport hook)
src/ai_ha/web/templates/rooms.html      +5 行    update(rooms.js 引入)
src/ai_ha/web/templates/room.html       +5 行    update(room-live.js 引入)
src/ai_ha/web/templates/_macros.html    ~30 行   new(共用宏:trans / room_card)
src/ai_ha/web/static/app.css            重写 ~250 行(mobile-first base + media-query layers)
src/ai_ha/web/static/dashboard.js       ~100 行  new
src/ai_ha/web/static/rooms.js           ~60 行   new
src/ai_ha/web/static/room-live.js       ~40 行   new

# === 测试 ===
tests/integration/test_install_script.py     ~80 行   new(bash mock + 假 HA)
tests/integration/test_dashboard.py          ~100 行  new
tests/integration/test_live_room_state.py    ~80 行   new(broadcaster + WS mock)
tests/integration/test_i18n_zh_cn.py         ~50 行   new(扩展现 test_i18n)
tests/unit/test_pipeline_room_state.py       ~50 行   new
tests/unit/test_dashboard_aggregator.py      ~60 行   new

# === 依赖 ===
requirements.txt                        +3:
  Babel==2.16.0
  Jinja2 already
  (no new runtime deps)
```

**LOC 总**:Python ~700 + Jinja ~170 + CSS/JS ~470 + Bash ~150 + i18n ~250 + tests ~420 ≈ **2160 LOC**(略超首估 1600,在 3.5 周吸收范围内)

### 4.2 依赖图(新增红色)

```
            ┌─────────┐
            │ config  │
            └────┬────┘
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
       │ +room_state pub │
       └────┬────────────┘
            ▼
           web ────────────┐
            │              │
            ▼              ▼
       routes/*       i18n (新,叶子)
        + dashboard.py
            ▲
            │
         main(顶层)
```

### 4.3 边界规则(新增)

- `i18n` 是叶子模块,纯 wrapper 包 Babel/gettext,无项目内依赖
- `dashboard.py` 是 read-only route,只依赖 store / health / snapshot_store
- `install.sh` 是独立 shell 脚本,**不引入任何 Python 依赖**(避免 chicken-egg)
- `room_state` publish 节流逻辑在 `ingest.pipeline` 内,**不上提到 broadcaster**(broadcaster 保持简单 fanout)

---

## §5 API 契约

### 5.1 HTTP 新增 / 改动

| Endpoint | Method | 描述 |
|----------|--------|------|
| `GET /` | GET | **改** — RedirectResponse 302 → /dashboard |
| `GET /dashboard` | GET | **新** — SSR 首页 + initial data 嵌入 |
| `GET /rooms` | GET | **不动** — 保留作次级 rooms grid 视图 |
| `GET /api/v1/dashboard` | GET | **新** — 单 endpoint 聚合 JSON |
| `GET /api/v1/locales` | GET | **新** — 返回支持的 locale 列表 `[{code, name}]` |
| `POST /api/v1/lang` | POST | **新** — 设置 cookie 切语言 `{lang: "zh"\|"en"}` |
| `GET /?lang=zh` query | GET | **新** — query 参数切语言,写 cookie |

### 5.2 `GET /api/v1/dashboard` 响应

```json
{
  "health": { ... HealthMetrics.snapshot() 全部字段 },
  "rooms": [
    {
      "area_id": "living",
      "name": "Living Room",
      "entity_count": 8,
      "device_class_distribution": {"light": 4, "sensor": 3, "climate": 1},
      "events_per_hour_24h": 142,
      "last_seen": 1717400000000,
      "active": true
    }
  ],
  "recent_events": [
    {
      "ts": 1717400000000,
      "entity_id": "light.living_main",
      "event_type": "state_changed",
      "area_id": "living",
      "old_state": "off",
      "new_state": "on"
    }
  ]
}
```

### 5.3 WS 消息类型(新增)

| Type | Payload | 频率 |
|------|---------|------|
| `state_changed` | (现有,不动)| HA push 即推 |
| **`room_state`**(新)| `{type:"room_state", area_id, last_seen_at, active, entity_count}` | 每 area 节流 1/sec |

### 5.4 i18n cookie

`Set-Cookie: ai-ha-lang=zh; Max-Age=31536000; SameSite=Lax; Path=/`

### 5.5 错误模型(新增 code)

| code | HTTP | 含义 |
|------|------|------|
| `dashboard-not-ready` | 503 | snapshot 还没建 |
| `invalid-locale` | 422 | POST /api/v1/lang 传未知 lang |

---

## §6 扩展点

**v0.1.5 不开放**新 plugin 协议。继承父 spec §6 (v0.2 BehaviorPlugin protocol 草案)。

**Locale 扩展点**(隐式):
- 新增语言:在 `src/ai_ha/web/i18n/locales/<lang>/LC_MESSAGES/` 加 .po 翻译
- `GET /api/v1/locales` 自动反映新增
- v0.1.5 ship `en` + `zh-CN`,v0.6+ 评估加 `ja`/`ko`

---

## §7 错误 + 边界 case

### 7.1 install.sh 错误(新 5 case)

| # | 场景 | 检测 | 处理 | exit code |
|---|------|------|------|---------|
| I1 | docker 不存在 | `command -v docker` | stderr "Install Docker first" + 装 link | 78 |
| I2 | docker compose plugin 缺 | `docker compose version` | stderr 提示 + link | 78 |
| I3 | 端口 8123 / 8124 已占 | `ss -tln`/`netstat` | stderr 指明 + 询问是否 abort | 78 |
| I4 | HA 60s 内未 health | curl /api/ 重试 6× | stderr "HA didn't start in 60s" + log tail | 70 |
| I5 | 用户贴的 token 无效 | curl bearer | stderr "Token invalid (401), check Profile > Security" + retry stdin | 78 |
| I6 | Ctrl-C 中途 abort | bash trap EXIT | cleanup unregistered containers,不删 volume,提示 re-run | 130 |

### 7.2 Dashboard 错误(新 2 case)

| # | 场景 | 处理 | code |
|---|------|------|------|
| D1 | snapshot 还没建(冷启动 < 30s)| GET /api/v1/dashboard 返 503 + retry 提示 | `dashboard-not-ready` |
| D2 | WS 断了 / dashboard.js 收不到 room_state | 改 polled 模式(每 10s GET /api/v1/dashboard)+ banner 提示 degraded | `ws-disconnected`(继承 v0.1.0)|

### 7.3 i18n 错误

| # | 场景 | 处理 |
|---|------|------|
| L1 | locale 不存在的 lang | fallback en + cookie not set |
| L2 | translation key 缺 | 直接渲染英文(gettext 默认行为)|
| L3 | POST /api/v1/lang 传未知 lang | 422 `invalid-locale` |

### 7.4 graceful degrade 总原则(继承 v0.1.0)

- WS 断 → dashboard polled fallback,不挂
- i18n 漏 key → 渲染英文不挂
- install.sh fail → 不残留 + 提示 re-run

---

## §8 成本契约

| Resource | v0.1.5 增量 | 累计(含 v0.1.0)|
|----------|----------:|---------:|
| Docker 镜像 | +5 MB(i18n .mo)| ~255 MB |
| RAM sustained | +10 MB(broadcaster fanout 队列 + i18n 缓存)| 160-310 MB |
| RAM peak | +20 MB | ~520 MB |
| CPU | +5%(room_state publish + i18n init)| < 1 core sustained |
| Network | 0(仍无 LLM,WS 仍本地)| 0 cloud |
| install.sh 装机时长 | — | 30 min p95(0 → /dashboard) |
| Disk | +200 KB(i18n .po + .mo + new JS/CSS)| 50-500 MB / yr 不动 |

---

## §9 测试矩阵

### 9.1 新增测试文件(6 文件)

```
tests/integration/test_install_script.py     ~80 行
tests/integration/test_dashboard.py          ~100 行
tests/integration/test_live_room_state.py    ~80 行
tests/integration/test_i18n_zh_cn.py         ~50 行
tests/unit/test_pipeline_room_state.py       ~50 行
tests/unit/test_dashboard_aggregator.py      ~60 行
```

### 9.2 6 类下限覆盖(v0.1.5 新增 case)

| 类 | v0.1.5 case |
|----|------|
| happy | install.sh full flow(mock HA → token → ai-ha 启)|
| edge | install.sh:token 含 `\n` / 空格 / 中文;空 lang query |
| error | I1-I6 + D1-D2 + L1-L3 |
| adversarial | install.sh stdin 注入 `; rm -rf /` 测 token 输入清洗;dashboard XSS via friendly_name(扩展 v0.1.0 test_adversarial)|
| 多 lang | en + zh-CN 切换 / cookie 持久 / fallback 链 |
| responsive | viewport 320/480/768/1100/1920 5 个 breakpoint 不挂 |
| degrade | WS 断 → dashboard polled fallback 工作 |

### 9.3 Acceptance gates G1-G8(v0.1.5 专属,继承 v0.1.0 G1-G17 全部不变)

详见 Appendix D。

### 9.4 Manual verification on real device

延续 v0.1.0 §9.5 模式:
- 真 RK3588 板 docker pull v0.1.5 image
- 跑 install.sh 30 min 计时
- iPhone Safari + Android Chrome 浏览 → 截图归 `docs/screenshots/v015-ga-verification/`
- 中文用户找一个母语者审 zh-CN 翻译

---

## §10 向后兼容

### 10.1 URL 兼容

- `/` 改 redirect → 旧浏览器收 302,无 breaking
- `/rooms` 保留 → 原 link 不死
- API `/api/v1/*` 全保留 + 新增(无删除)

### 10.2 config.toml 兼容

- 不新增 section
- 不删 / 改字段名
- 旧 v0.1.0 用户升级 v0.1.5 → config 0 改动

### 10.3 DB schema 兼容

- v0.1.5 不动 schema(无新 migration)
- 仍是 `001_initial.sql`,`kv_meta.schema_version = 1`

### 10.4 Docker volume / data 路径

- `/data/config.toml` 不动
- `/data/ai-ha.db` 不动
- `/data/events/` 不动
- `/data/.admin-token` 不动
- 新:`/data/.lang-cookie-key`(可选,用于 sign cookie;不存即每次随机)

### 10.5 install.sh 与 v0.1.0 现 docker-compose.with-ha.yml 关系

install.sh **使用** docker-compose.with-ha.yml 作 underlying。compose 文件本身被微调(env_file 引用)。手动 docker compose up 用户仍可用,install.sh 是糖衣。

---

## §11 风险登记

完整 12 条(v0.1.5 专属):

| # | 风险 | Severity | Mitigation |
|---|------|:---:|------|
| 1 | install.sh 在 Alpine/老 CentOS 报错 | S3 | 测 Debian/Ubuntu 12+;README 标"tested on Ubuntu 22+/Debian 12+";其它发行版 best-effort |
| 2 | HA Profile/Security 路径在 HA 不同版本漂移 | S3 | install.sh stdout 打印 HA version + 路径(Profile > Security > Long-Lived Access Tokens > Create Token)+ 截图 wiki link;每月人工 verify HA changelog |
| 3 | i18n Babel `extract_messages` 漏 Jinja 字符串 | S2 | CI 加校验:跑 extract + diff 现 .po,有新字符串 fail |
| 4 | live update 高频 broadcast 拖累 ingest p99 | S2 | room_state 每 area 节流 1/sec(`asyncio.Queue` 或简单 last_publish_ts dict);bench_ingest 加 assert p99 < 100ms 维持 |
| 5 | mobile breakpoint 在 iOS Safari ≠ Chrome | S3 | manual 真机测;不通过 not GA |
| 6 | install.sh 用户 abort 后残留 container | S2 | `trap EXIT cleanup`;cleanup 函数 idempotent;残留即视为 bug 处理 |
| 7 | install.sh stdin token 输入被中断字符干扰 | S2 | strip + validate(正则 ^[A-Za-z0-9._-]+$);非法字符 reject + retry |
| 8 | dashboard.js DOM 操作引发 XSS | S2 | 同 v0.1.0:textContent / createElement only,grep 0 innerHTML;test_adversarial 扩展 |
| 9 | i18n cookie 篡改影响其它 user | S3 | cookie 只控制 lang(无 auth bypass);篡改无危害 |
| 10 | dashboard 加载慢导致 LCP > 2s | S3 | SSR initial 数据嵌入 + critical CSS inline;bench_api 加 assert p99 < 300ms |
| 11 | Babel 编译 .mo 需运行时存在 → Docker image bloat | S3 | .mo 在 Docker build 时 compile + 打包(不增长 RAM,~50 KB disk)|
| 12 | "/" → /dashboard redirect 破坏 bookmark | S4 | 302 redirect 浏览器自动跟随;无破坏 |

**Top S2 关注**(4 项):3 (Babel 漏 key)/ 4 (live update p99)/ 6 (abort cleanup)/ 7 (stdin 注入)/ 8 (XSS)

**Runtime 监控新增**:
- `room_state_publish_total` / `room_state_throttle_drop_total` — broadcaster
- `i18n_translation_miss_total` per (lang, key) — gettext wrapper
- `install_invocation_total` — 暴露 in /api/health for fleet visibility(可选)

---

## Appendix A: install.sh 详细流程

```bash
#!/usr/bin/env bash
# ai-home-assistant install.sh
# Usage: curl -fsSL https://raw.githubusercontent.com/qiurui144/ai-home-assistant/main/install.sh | bash
# Or:    bash install.sh

set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/ai-ha}"
REPO_URL="https://github.com/qiurui144/ai-home-assistant.git"
HA_PORT="${HA_PORT:-8123}"
AIHA_PORT="${AIHA_PORT:-8124}"

cleanup() {
  local code=$?
  if [[ $code -ne 0 && -n "${INSTALL_INCOMPLETE:-}" ]]; then
    echo "❌ install aborted (exit $code). Cleaning up..."
    docker compose -f "$INSTALL_DIR/docker/docker-compose.with-ha.yml" down 2>/dev/null || true
  fi
}
trap cleanup EXIT

# Step 1: prereq check
check_prereq() {
  command -v docker >/dev/null || { echo "ERR: Docker missing. https://docs.docker.com/engine/install/"; exit 78; }
  docker compose version >/dev/null || { echo "ERR: docker compose plugin missing"; exit 78; }
  ! (ss -tlnp 2>/dev/null | grep -q ":${HA_PORT} ") || { echo "ERR: port $HA_PORT in use"; exit 78; }
  ! (ss -tlnp 2>/dev/null | grep -q ":${AIHA_PORT} ") || { echo "ERR: port $AIHA_PORT in use"; exit 78; }
  echo "✓ Prereqs OK"
}

# Step 2: clone / update repo
fetch_repo() {
  if [[ -d "$INSTALL_DIR/.git" ]]; then
    (cd "$INSTALL_DIR" && git pull --ff-only)
  else
    git clone --depth 1 "$REPO_URL" "$INSTALL_DIR"
  fi
}

# Step 3: pull images
pull_images() {
  echo "Pulling Docker images (5-10 min)..."
  docker pull ghcr.io/qiurui144/ai-home-assistant:0.1.5
  docker pull ghcr.io/home-assistant/home-assistant:stable
}

# Step 4: start HA
start_ha() {
  cd "$INSTALL_DIR/docker"
  INSTALL_INCOMPLETE=1
  docker compose -f docker-compose.with-ha.yml up -d homeassistant
  echo "Waiting HA to be healthy (max 60s)..."
  for i in {1..6}; do
    if curl -fsS "http://localhost:${HA_PORT}/" >/dev/null 2>&1; then
      echo "✓ HA ready at http://localhost:${HA_PORT}"
      return 0
    fi
    sleep 10
  done
  echo "ERR: HA didn't start in 60s. Logs:"
  docker compose -f docker-compose.with-ha.yml logs --tail=20 homeassistant
  exit 70
}

# Step 5: prompt user for token
prompt_token() {
  cat <<EOF

════════════════════════════════════════════════════════════
║ NEXT STEP — generate HA Long-Lived Access Token
║
║ 1. Open in browser:  http://localhost:${HA_PORT}
║ 2. Create your HA account (skip onboarding wizard or do it)
║ 3. Profile (bottom-left) → Security → Long-Lived Access Tokens
║ 4. Create Token: name = "ai-home-assistant"
║ 5. Paste the token below (it will be hidden):
════════════════════════════════════════════════════════════
EOF
  read -rs -p "HA token: " token; echo
  token=$(echo "$token" | tr -d '[:space:]')
  if [[ ! "$token" =~ ^[A-Za-z0-9._-]+$ ]]; then
    echo "ERR: token has invalid characters"; exit 78
  fi
  # Validate
  if ! curl -fsS -H "Authorization: Bearer $token" "http://localhost:${HA_PORT}/api/" >/dev/null; then
    echo "ERR: token invalid (HA returned non-200)"; exit 78
  fi
  echo "HA_TOKEN=$token" > "$INSTALL_DIR/docker/.env"
  chmod 600 "$INSTALL_DIR/docker/.env"
  echo "✓ Token saved to $INSTALL_DIR/docker/.env (0600)"
}

# Step 6: start ai-ha
start_aiha() {
  cd "$INSTALL_DIR/docker"
  docker compose -f docker-compose.with-ha.yml up -d ai-home-assistant
  echo "Waiting ai-ha to be healthy (max 30s)..."
  for i in {1..3}; do
    if curl -fsS "http://localhost:${AIHA_PORT}/api/health" >/dev/null; then
      INSTALL_INCOMPLETE=
      return 0
    fi
    sleep 10
  done
  echo "ERR: ai-ha didn't start. Logs:"
  docker compose -f docker-compose.with-ha.yml logs --tail=20 ai-home-assistant
  exit 70
}

# Step 7: print success banner
print_banner() {
  local admin_token
  admin_token=$(docker exec ai-home-assistant cat /data/.admin-token 2>/dev/null || echo "<check container logs>")
  cat <<EOF

════════════════════════════════════════════════════════════
║ ✓ ai-home-assistant is ready!
║
║ URL:           http://localhost:${AIHA_PORT}
║ admin user:    admin
║ admin token:   ${admin_token}
║ HA URL:        http://localhost:${HA_PORT}
║
║ Open the URL above and log in with admin / <token>.
║ Bookmark /dashboard for the main view.
════════════════════════════════════════════════════════════
EOF
}

main() {
  check_prereq
  fetch_repo
  pull_images
  start_ha
  prompt_token
  start_aiha
  print_banner
}

main "$@"
```

---

## Appendix B: Dashboard layout 规格

(See `dashboard-combo.html` 浏览器 mockup for visual)

### Desktop ≥ 1100px

- Header: nav(brand + 4 links + lang switcher 在右上)
- Banner row: 5 metric chips inline(ws / entities / events/24h / privacy_drops / uptime)
- Main grid: 2/3 width left(rooms grid 3 cols)+ 1/3 width right(live events feed)

### Tablet 768-1099px

- Header 同上
- Banner row 4 chips(uptime 折叠到 hover)
- Main grid: 2/3 + 1/3 不变,但 rooms grid 2 cols

### Mobile < 768px

- Header: brand + hamburger 折叠 nav
- Banner row: 2 chips per row(共 3 行)
- Main: 单列堆叠 — rooms grid 2 cols → live events 全宽(底部 sticky 收纳卡片可展开)

### Mobile small < 480px

- 同上,rooms grid 1 col

### CSS 实现策略

- mobile-first base styles(< 480px)
- `@media (min-width: 480px)` 加 tablet
- `@media (min-width: 768px)` 加 desktop split
- `@media (min-width: 1100px)` 加宽 grid

### Dashboard 数据更新策略

- Initial: SSR render with embedded JSON(避免一次 fetch)
- Subsequent: WS event 驱动 DOM partial update
- Fallback: WS 断 30s 后切 polled mode(GET /api/v1/dashboard 每 10s)

---

## Appendix C: i18n key 清单

完整 zh-CN 翻译表(~150 条),节选:

| key | en | zh-CN |
|-----|-----|-----|
| `nav.rooms` | Rooms | 房间 |
| `nav.entities` | Entities | 设备 |
| `nav.timeline` | Timeline | 时间线 |
| `nav.settings` | Settings | 设置 |
| `nav.dashboard` | Dashboard | 仪表盘 |
| `banner.listen_only` | v0.1.5 = Listen-only foundation. AI suggestions arrive in v0.4. | v0.1.5 监听阶段。AI 建议将在 v0.4 上线。 |
| `dashboard.title` | Dashboard | 仪表盘 |
| `dashboard.health.ws_connected` | WebSocket Connected | WebSocket 已连接 |
| `dashboard.health.entities` | Entities | 设备总数 |
| `dashboard.health.events_per_hour` | Events/24h | 24 小时事件 |
| `dashboard.health.privacy_drops` | Privacy Drops | 隐私丢弃 |
| `dashboard.health.uptime` | Uptime | 在线时长 |
| `dashboard.rooms.title` | Rooms | 房间 |
| `dashboard.events.title` | Live Events | 实时事件 |
| `room.entities_label` | Entities | 设备清单 |
| `room.recent_events` | Recent Events | 最近事件 |
| `entity.area_label` | Area | 所属房间 |
| `entity.device_class` | Device Class | 设备类型 |
| `entity.last_seen` | Last Seen | 最后活跃 |
| `settings.privacy.title` | Privacy Settings | 隐私设置 |
| `settings.privacy.hide_pattern_label` | Hide entity regex (one per line) | 隐藏 entity 正则(每行一条)|
| `settings.privacy.save` | Save | 保存 |
| `error.dashboard_not_ready` | Dashboard not ready — waiting for HA topology. | 仪表盘未就绪 — 等待 HA 拓扑加载。 |
| `error.ws_disconnected` | WS disconnected. Switching to polled mode. | WS 已断开,正切换轮询模式。 |

完整 .po 文件在 `src/ai_ha/web/i18n/locales/zh_CN/LC_MESSAGES/ai_ha.po`,实施时生成。

### Babel 抽取命令

```bash
pybabel extract -F src/ai_ha/web/i18n/babel.cfg -k _l -o src/ai_ha/web/i18n/messages.pot src/
pybabel init -i src/ai_ha/web/i18n/messages.pot -d src/ai_ha/web/i18n/locales -l zh_CN
# (人翻译 .po)
pybabel compile -d src/ai_ha/web/i18n/locales
```

### CI 校验

```bash
# .github/workflows/ci.yml 加 step:
pybabel extract -F src/ai_ha/web/i18n/babel.cfg -k _l -o /tmp/messages.pot src/
diff <(grep '^msgid' src/ai_ha/web/i18n/messages.pot) <(grep '^msgid' /tmp/messages.pot)
# 0 diff = 没漏 key
```

---

## Appendix D: Acceptance gates G1-G8

v0.1.5 GA 必须全过(继承 v0.1.0 G1-G17 不变 + 加 G1-G8 本节):

| # | 维度 | 量度 | 通过判据 | 视角 |
|---|------|------|---------|------|
| **vG1** | install.sh 装机时长 | 0 → /dashboard 显示 | < 30 min(p95)on Debian/Ubuntu LTS | 黑盒 |
| **vG2** | install.sh 4 error case | I1/I2/I4/I5 都 exit 正确 + 不残留 container | 4/4 PASS + cleanup verify | 灰盒 |
| **vG3** | Dashboard p99 | GET /api/v1/dashboard p99 | < 300ms | 灰盒 bench |
| **vG4** | Live update p99 | room_state 端到端(commit → DOM 更新)| < 100ms | 灰盒 |
| **vG5** | Mobile 浏览 | iPhone Safari + Android Chrome 5 页 console error | 0 / 0 | 黑盒 manual |
| **vG6** | i18n 完整 | zh-CN .po 翻译覆盖 | ≥ 95% UI strings + 0 missing key on common pages | grep + manual |
| **vG7** | 无 regression | v0.1.0 全 120 tests | 120/120 PASS | pytest |
| **vG8** | Coverage 维持 | line coverage | ≥ 80% | pytest --cov |

---

## Appendix E: 与 v0.1.0 父 spec 的差异

| 父 spec(2026-06-02)| 本 spec(v0.1.5)|
|------|------|
| v0.1.0 Listen-only 是 Phase A.1 | v0.1.5 是 Phase A.1.5,在 v0.1.0 GA 之后插入 |
| §1.4 北极星"v0.1.0 不直接服务'learns you'" | 本 spec 仍不学习,但回归"用户上手体验"近端北极星 |
| §2.1 #7 "Web UI: 5 页" | 本 spec 加第 6 页 /dashboard 作新首页 |
| §2.2 #「不做 LLM」 | 不动 — v0.1.5 仍不接 LLM |
| §3.1 WS endpoint | 加 room_state 消息类型 |
| §4 文件树 | 加 i18n/ / dashboard.py / install.sh / *.js |
| §10.3 HA API tested | 不动 + install.sh 加月度 verify HA changelog |
| Appendix C G1-G17 | 不动 + vG1-G8 新增 |

---

**End of v0.1.5 design spec.**
