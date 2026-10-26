# Day 3 带读教案：从入队到图谱

> 用途：上课用的教案，不是复习资料。承接 `docs/Day2-带读教案.md`，Day2 停在"切片完成、任务入队"。
> 行号基于当前 `backend/` 源码（2026-10），路径相对 `backend/app/`。

---

## 一、这门课怎么上

每节固定三步：

| 步骤 | 我做什么 | 你做什么 |
| --- | --- | --- |
| ① 说麻烦 | 三句话：这一步在防什么坑 | 听 |
| ② 给证据 | 一段能跑的结果，或不超过 12 行的代码 | 看 |
| ③ 出题 | 一道不靠这一步就答不对的题 | 答 |

规则三条：

- **你答对或说"懂了"才进下一节。** 进度由你决定，我不替你宣布过关。
- 说"不懂"不丢人，换一种说法重讲同一节，不往前推。
- 每节控制在 15 行以内；一节塞不下就劈成两半。

---

## 二、Day 3 到底在讲什么

两句话：

- Day2 收官时，MySQL 的 `graph_build_tasks` 表里躺着一条 `pending` 任务，payload 是切好的块。
- Day3 讲这条任务怎么被 worker 拿走、正文怎么被 LLM 抽成实体和关系、这些东西怎么写进 Neo4j、删了之后怎么清干净。

中间那条界线是 **`graph_build_tasks` 表**。Day2 在 `create_task` 那一行放手，Day3 从表里接手。

---

## 三、课程表

| 节 | 主题 | 解决的麻烦 | 状态 |
| --- | --- | --- | --- |
| 1 | 谁在跑：轮询 worker | `create_task` 火完就没人管，进程重启任务还在吗 | ⬜ |
| 2 | 认领与 `run_token` | 抽取要几十秒，这期间用户又改了 | ⬜ |
| 3 | 一条任务的一生 | 重试、强抽、判重混在一起，状态会卡死 | ⬜ |
| 4 | LLM 抽什么 | 自由文本变结构化，模型会带前言、超量、类型乱写 | ⬜ |
| 5 | 写图谱六步 | 重抽一次，实体和边会不会翻倍 | ⬜ |
| 6 | Chunk 怎么落库 | 接 Day2 的断点；id 怎么定、跨用户怎么隔离 | ⬜ |
| 7 | 删除与孤儿清扫 | 删了笔记，实体还挂在图上，检索还会返回它 | ⬜ |
| 8 | 事件推送 | 后台抽取，前端怎么知道好了 | ⬜ |

第 3 节内容最多，讲的时候拆成两半：前半 `_ensure_extract_log` 的判重，后半 `process_task` 的状态机。

---

## 四、各节教案

### 第 1 节 · 谁在跑：轮询 worker

- **麻烦**：Day2 最后一行是 `asyncio.create_task(...)`，那个 task 对象活在内存里，进程一重启就没了。用户传完文件，任务就这么丢了？
- **结论**：任务不在内存里，在 MySQL 的 `graph_build_tasks` 表里，payload 一起落库。应用内起一个 asyncio 循环，每 2 秒捞一条 `pending`；启动时先把上次遗留的 `running` 全部拨回 `pending`。
- **看哪**：`graph/services/graph_worker.py:21-34`（启动恢复）、`:90-107`（循环 + `POLL_INTERVAL=2.0`）、`core/background_init.py:183-189`（挂到应用启动）、`models/graph.py` 的 `GraphBuildTask`
- **检查题**：`create_task` 之后立刻 `kill -9`，这条任务会丢吗？

### 第 2 节 · 认领与 `run_token`

- **麻烦**：一条 20 页文档要抽几十秒。这期间用户改了笔记又保存，会再入队一次。如果第一次的结果晚到，就把新内容覆盖了。
- **结论**：乐观认领 + 令牌。`_claim_next_task` 用 `UPDATE ... WHERE status='pending'` 置 `running` 并写入新 `run_token`；执行方在三处校验令牌——开始前、写图谱前、回写状态前。任一处发现令牌变了，就自愿放弃。
- **看哪**：`graph_worker.py:37-57`、`graph_service.py:351-356`、`:362-368`（`claim_check`）、`:406-415`
- **检查题**：放弃时为什么不把任务标成 `failed`？

### 第 3 节 · 一条任务的一生

- **麻烦**：反复保存、失败重试、手动强抽三件事混在一条任务上，状态很容易卡在中间。
- **结论**：状态机 `pending → running → completed / failed`，`attempts` 上限 3（`graph_service.py:33`）。判重只看"抽取日志 `success` 且 `content_hash` 相同"；`pending` / `failed` 必须继续抽。`force=True` 跳过判重，并把日志打回 `pending`。
- **看哪**：`graph_service.py:339-434`、`_ensure_extract_log:58-99`
- **检查题**：如果 `pending` 状态也被判重跳过，界面会怎样？

### 第 4 节 · LLM 抽什么

- **麻烦**：让模型从正文里抽实体和关系，它会带前言、包 markdown 代码块、抽五十个、类型乱写。
- **结论**：prompt 里写死约束——只输出 JSON、最多 20 个实体、类型七个枚举、每个实体要带 `mentions` 原文片段。解析三层：`json_object` → 普通调用 → 正则从 `[[...]]` 兜底。正文截 6000 字。
- **看哪**：`graph/extraction/entity_extractor.py:33-65`、`prompt/entity_extraction_prompt.md`
- **检查题**：模型返回 ```json 包起来的内容，会直接解析失败吗？

### 第 5 节 · 写图谱六步

- **麻烦**：同一篇笔记重抽一次，不能越抽越多；关系要能按来源撤销；同一个实体叫了两种名字要能并上。
- **结论**：① 实体 upsert（按名去重，名不中再按别名，别名取并集、`confidence` 取 max）② 按来源先删后插 `RELATES_TO` ③ 来源级 `MENTIONS` 先删后插 ④ 写 `Chunk` + `Chunk` 级 `MENTIONS`（规则匹配，不打 LLM）⑤ 孤儿清扫 ⑥ 笔记双链 `WIKI`。
- **看哪**：`graph_service.py:162-225`、`neo4j_graph_store.py:96-141`、`:587-644`
- **检查题**：同一篇笔记抽两次，实体和边会不会翻倍？

### 第 6 节 · Chunk 怎么落库

- **麻烦**：Day2 讲"入队"，块其实还没进库。真正写的时候 id 怎么定？两个用户传同一份 PDF（md5 相同）会不会互相覆盖？
- **结论**：`id = {source_type}:{source_id}:{chunk_index}`，`MERGE` 键是 `(id, user_id)`，所以跨用户同 id 是不同节点。`kind` 就取 `source_type`，正好对上 Day2 检索里的 `kinds`。`embedding` 在 worker 里算好一起写进节点。
- **看哪**：`neo4j_graph_store.py:555-579`、`graph_service.py:195-210`
- **检查题**：两个用户传同一份 PDF，`Chunk` 的 id 会撞吗？

### 第 7 节 · 删除与孤儿清扫

- **麻烦**：删了笔记，它抽出来的实体还挂在图上，检索时还会被当成证据返回。
- **结论**：`clear_source_data` 删源节点、`Chunk`、该来源的溯源边，返回"曾关联的实体 id"；`sweep_orphan_entities` 先从 `source_note_ids` 摘掉这个来源，只有"引用清零且没有任何 `MENTIONS` 边"才删实体。Neo4j 不可用时只跳过图谱清理，MySQL 侧照删。
- **看哪**：`neo4j_graph_store.py:747-780`、`graph_service.py:437-476`
- **检查题**：为什么不能直接把它关联的实体一起删掉？

### 第 8 节 · 事件推送

- **麻烦**：抽取在后台跑几十秒，前端画布怎么知道该刷新。
- **结论**：进程内 per-user 事件总线，`publish` 在成功和失败两处；`/api/graph/events` 是 SSE 长连接，15 秒没事件发一条 `ping`。无订阅者时 `publish` 静默丢弃。
- **看哪**：`graph/services/event_bus.py`、`graph/routers/graph_router.py:256-273`、`graph_service.py:242-244`、`:258-260`
- **检查题**：为什么用长连接，不让前端轮询数据库？

---

## 附录 A：Day2 → Day3 的接缝

| Day2 停在哪 | Day3 从这里接 |
| --- | --- |
| `processor.py:219` 的 `create_task(maybe_schedule_doc_extraction(...))` | `graph_service.py:300-319` 写 `graph_docs` 行并入队 |
| payload 里的 `chunks`（含 `page` / `image_paths`） | 原样存进 `graph_build_tasks.payload`，worker 直接用，不再重切 |
| 检索里的 `(:Chunk)` 节点 | 由 `upsert_chunks`（`neo4j_graph_store.py:555`）写入 |
| 检索时的 `kinds` 过滤 | 就是 `Chunk.kind`，值取自 `source_type`（`note` / `doc`） |

同一套切分参数：`chunk_matcher.py:13-22` 的 `_get_splitter()` 读的还是 `document.yaml`，和 Day2 第 1 节同一个配置。

---

## 附录 B：检查题答案

**第 1 节**：不丢。内存里的 `asyncio.Task` 没了，但 payload 早就写进 `graph_build_tasks`。下次启动 `recover_stale_tasks` 把 `running` 拨回 `pending`，循环两秒后接着消费。

**第 2 节**：因为任务已经被新触发打回 `pending` 了，标 `failed` 会误伤新任务。旧执行方只是作废，终态由新认领者写。

**第 3 节**：界面会永久显示"解析中"。被中断的任务（重新入队、进程重启）日志停在 `pending`，任务却被置 `completed`，再也没有人把它改成 `success`。所以 `:71` 只在 `status == "success"` 且哈希相同时才跳过。

**第 4 节**：不会直接失败。`_extract_json`（`:10-20`）先剥 ``` 前后缀，再截 `{` 到 `}`；剥完还解析不了才落到下一层，最后是正则兜底。

**第 5 节**：不会翻倍。实体按名/别名 upsert；`MENTIONS` 和 `RELATES_TO` 都是"先删该来源的旧边再插"；`Chunk` 用 `MERGE` 覆盖。手动建的实体和关系没有 `source_id`，不在这套清理范围内。

**第 6 节**：id 会撞，节点不会。`MERGE` 键是 `(id, user_id)`，两个用户各得一个节点；检索时还要再叠 `c.user_id = $uid` 过滤（`neo4j_graph_store.py:716`）。

**第 7 节**：实体可能被别的笔记也引用着。所以先拿候选（`clear_source_data` 的返回值），再摘引用，只有引用清零且没有任何 `MENTIONS` 边才删。

**第 8 节**：轮询要反复查库，延迟还取决于间隔。长连接只在真有事件时推，空闲时只有 15 秒一条 `ping`。

---

## 附录 C：Neo4j 里的节点和边

| 节点 | 关键属性 |
| --- | --- |
| `(:Entity)` | `id` / `user_id` / `name` / `display_name` / `type_id` / `description` / `aliases` / `confidence` / `source_note_ids` |
| `(:Chunk)` | `id` / `user_id` / `kind` / `source_id` / `source_name` / `chunk_index` / `text` / `embedding` / `page` / `image_paths` |
| `(:Note)` | `id` / `user_id` / `title` |
| `(:Doc)` | `id`（md5）/ `user_id` / `filename` |
| `(:EntityType)` | `id` / `name` / `display_name` / `color` / `icon` / `is_system` / `user_id`（NULL = 系统预置） |

| 边 | 含义 |
| --- | --- |
| `(Note\|Doc)-[:MENTIONS {id, mention_count, context_json}]->(Entity)` | 这个来源提到过这个实体，`context_json` 是原文片段 |
| `(Chunk)-[:MENTIONS]->(Entity)` | 这个块里出现了这个实体（规则匹配，零 LLM） |
| `(Entity)-[:RELATES_TO {relation_type, confidence, source_id, source_type}]->(Entity)` | 实体间关系，按来源可撤销 |
| `(Note)-[:WIKI {source_note_id, target_note_id, kind}]->(Note)` | `[[双链]]`，单向存储、查询双向匹配 |

七个系统类型（`neo4j_graph_store.py:34-35`）：`person` / `tech` / `concept` / `org` / `place` / `project` / `event`。首次 `list_types` 时惰性种入（`:489-502`）。

---

## 附录 D：图谱 API 一览

| 方法 | 路径 | 干什么 |
| --- | --- | --- |
| GET | `/api/graph/overview` | 画布总览 |
| GET | `/api/graph/entity/{id}` | 单个实体 |
| GET | `/api/graph/entity/{id}/neighbors?depth=1..3` | 邻居 |
| GET | `/api/graph/entity/{id}/notes` | 这个实体被哪些来源提到 |
| GET | `/api/graph/notes/{id}/related`、`/docs/{id}/related` | 某个来源的关联图 |
| GET | `/api/graph/search?q=` | 实体搜索 |
| GET | `/api/graph/extract-logs` | 抽取日志（前端"解析中"就来自这里） |
| POST/PUT/DELETE | `/api/graph/entities`、`/entities/merge` | 实体增删改与合并 |
| GET/POST/PUT/DELETE | `/api/graph/types` | 类型管理 |
| POST/DELETE | `/api/graph/relations` | 手动关系 |
| POST | `/api/graph/notes/{id}/re-extract` | 手动重抽（`force=True`） |
| GET | `/api/graph/events` | SSE 事件流 |

---

## 附录 E：文件清单

| 文件 | 职责 |
| --- | --- |
| `graph/services/graph_worker.py` | 轮询任务表、乐观认领、启动恢复 |
| `graph/services/graph_service.py` | 入队、判重、状态机、抽取管线、删除清理 |
| `graph/extraction/entity_extractor.py` | 调 LLM 抽实体与关系，三层解析 |
| `graph/extraction/chunk_matcher.py` | 兜底切片 + 实体到 chunk 的规则匹配 |
| `graph/extraction/link_parser.py` | `[[双链]]` 语法解析 |
| `graph/storage/neo4j_graph_store.py` | 唯一真正读写 Neo4j 的文件 |
| `graph/services/event_bus.py` | 进程内 per-user 事件总线 |
| `graph/routers/graph_router.py` | 图谱 API 与 SSE |
| `models/graph.py` | 三张 MySQL 表：`graph_build_tasks` / `graph_extract_logs` / `graph_docs` |
| `prompt/entity_extraction_prompt.md` | 抽取提示词 |

MySQL 三张表的分工：

- `graph_build_tasks`：待办队列，worker 消费的就是它。
- `graph_extract_logs`：抽取结果账本，`status` 决定界面显示"解析中"还是"完成"。
- `graph_docs`：文档注册行，`id` 就是 md5。

---

## 附录 F：面试口径（三句话）

1. 写入侧是"任务表 + 应用内轮询 worker"：任务落 MySQL，进程重启不丢；认领用乐观 `UPDATE` 加 `run_token`，三处校验防止旧内容覆盖新任务；失败重试上限 3 次。
2. 抽取是 LLM 抽实体/关系，落库全程按来源幂等：实体按名/别名 upsert，关系与 `MENTIONS` 先删后插，`Chunk` 用 `(id, user_id)` 复合键 `MERGE`。
3. 删除走"候选 + 孤儿清扫"，引用清零且无 `MENTIONS` 才删实体；Neo4j 不可用时只降级清理，不阻塞主流程。

---

## 附录 G：这一课不讲的三件事

1. **前端画布渲染**：力导向布局、节点拖拽、颜色映射，都在 `front/` 里，与图谱数据无关。
2. **多实例部署的租约**：`recover_stale_tasks` 的注释写明"单实例部署才成立，多实例需先引入 lease/owner"。这是已知限制，不是设计缺陷。
3. **实体合并的界面交互**：`merge_entities`（`neo4j_graph_store.py:197`）本身值得看，但它属于手工整理，不在自动抽取链路上。
