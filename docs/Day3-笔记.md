# Day3 笔记：从入队到图谱

> 承接 `docs/Day2-复盘笔记.md`。Day2 停在"任务入队"，这份从任务表往下走。
> 路径相对 `backend/app/`，行号基于 2026-10 源码。

---

## 一、起点：Day2 留下了什么

Day2 最后一行是 `processor.py:219`：

```python
asyncio.create_task(maybe_schedule_doc_extraction(user_id, md5_hex, filename, full_text, chunks=graph_chunks))
```

它做两件事（`graph_service.py:300-319`）：往 `graph_docs` 写一行文档注册（`id` 就是 md5），然后往 `graph_build_tasks` 写一条 `pending` 任务，payload 是 JSON。

payload 有两种形状：

- 文档：`{"chunks": [{chunk_index, text, page, image_paths}]}`——上传管线预切好的，带着页码和图片路径。
- 笔记：`{"text": 正文}`——没有预切，worker 自己切。

三张 MySQL 表分工：

| 表 | 干什么 | 关键字段 |
| --- | --- | --- |
| `graph_build_tasks` | 队列，worker 消费它 | `status` / `attempts` / `run_token` / `payload` / `content_hash` |
| `graph_extract_logs` | 账本，界面"解析中"的来源 | `status`（pending/success/failed）/ `content_hash` |
| `graph_docs` | 文档注册行 | `id` = md5 |

---

## 二、任务怎么被跑起来

**worker 是一个应用内的 asyncio 循环，不是线程池。**

```
run_worker_loop（graph_worker.py:90-107）
  ├─ recover_stale_tasks()   启动时：running → pending，清空 run_token（:21-34）
  └─ while not stop_event:
        _tick()               有任务就处理一条
        没任务 → wait_for(stop_event.wait(), 2.0)
```

`_tick` 每次只处理**一条**（`:60-87`）。所以抽取是串行的：同一时刻只有一个任务在跑。

**认领**（`:37-57`）：

```python
select ... where status='pending' order by created_at limit 1
update GraphBuildTask set status='running', run_token=$token
    where id=$id and status='pending'
```

这是乐观锁：`UPDATE` 带了 `status='pending'` 条件，`rowcount == 0` 就说明被别人抢了，返回 `None`。

---

## 三、三道令牌校验

抽取要几十秒。这期间用户可能又保存了一次，任务会被重新入队、`run_token` 被换掉。旧执行方必须自己停手，否则旧内容会覆盖新结果。

| 位置 | 校验什么 | 不通过时 |
| --- | --- | --- |
| `process_task:351-356` | 任务存在、`status == "running"`、token 一致 | 直接 return，不执行 |
| `_run_extraction` 前的 `claim_check:362-368` | 状态、token、`content_hash` 三者都没变 | 放弃写入，return |
| 回写状态前 `:413-415` | 状态、token | 丢弃本次结果，不写终态 |

注意第三处：**发现自己被顶掉时，什么都不写**。因为新任务已经回 `pending` 了，标 `failed` 会把新任务一起弄死。

---

## 四、判重：什么时候该跳过

`_ensure_extract_log`（`:58-99`）只有一种情况返回"跳过"：

```python
if row is not None and row.status == "success" and row.content_hash == content_hash_value:
    return False
```

`pending` 和 `failed` 都必须继续抽。原因写在同一段注释里（`:68-70`）：被中断的任务（重新入队、进程重启）日志会停在 `pending`，如果也跳过，任务会被置 `completed` 而日志永远停在 `pending`，界面就永久显示"解析中"。

并发插入同一条日志会撞唯一约束 `(user_id, note_id, source_type)`，代码用 `IntegrityError` → `rollback` → 重查复用（`:80-98`）。

---

## 五、状态机

```
pending ──claim──> running ──┬── 成功 ──────────> completed
                             ├── 失败且 attempts < 3 ──> pending（重试）
                             └── 失败且 attempts >= 3 ─> failed
```

- `MAX_TASK_ATTEMPTS = 3`（`:33`）。
- `force=True` 跳过哈希判重，并把抽取日志打回 `pending`（`:377-385`）。
- 细节：`_enqueue_build_task` 只在**内容变了**时重置 `attempts`（`:281-289`），`force` 本身不重置。所以失败满 3 次后，手动重抽只再给一次机会。

---

## 六、抽取：LLM 那一步

`extract_entities(title, body, chat_model)`（`entity_extractor.py:33-65`），正文截前 6000 字。

prompt 的约束（`prompt/entity_extraction_prompt.md`）：

- 只输出一个 JSON 对象，不要解释、不要 markdown。
- 实体字段：`name` / `type` / `aliases` / `description` / `mentions`。
- 关系字段：`source` / `target` / `relation_type`。
- 最多 20 个实体；`type` 只能是 `person` / `tech` / `concept` / `org` / `place` / `project` / `event`。

解析三层：

1. `bind(response_format={"type": "json_object"})` 调一次。
2. 失败 → 普通 `ainvoke` 再调一次。
3. 再失败 → `_fallback_extract` 用正则从原文捞 `[[...]]`，保证不空手。

每层都先过 `_extract_json`（`:10-20`）：剥掉 ``` 前后缀，再截 `{` 到 `}`。

产物是 `ExtractResult(entities, relations)`，纯内存结构，还没写库。

---

## 七、写图谱：六步

`_run_extraction`（`graph_service.py:102-263`）的写入顺序：

| 步 | 做什么 | 幂等方式 |
| --- | --- | --- |
| 1 | `parse_links(body)`，只在笔记上做 | — |
| 2 | 调 LLM 抽实体与关系 | — |
| 2.5 | 来源存在性复检（抽取期间被删就放弃） | — |
| 2.6 | 令牌复检 | — |
| 3 | `upsert_entity` 逐个写实体 | 按名去重，名不中再按别名；别名取并集、`confidence` 取 `max` |
| 4 | `set_relations_from_source` | 先删该来源的 `RELATES_TO` 再插 |
| 5 | `ensure_source_node` + `set_source_mentions` | 单事务内先删该来源的 `MENTIONS` 再插 |
| 5.5 | `upsert_chunks` + `set_chunk_mentions` | `MERGE (id, user_id)`；`MENTIONS` 先删后插 |
| 5.6 | `sweep_orphan_entities` | 本轮没再关联的旧实体摘引用 |
| 6 | `set_note_wiki_edges`（仅笔记） | 先删本笔记全部出边再插 |
| 7 | 写 `graph_extract_logs` 为 `success`，`event_bus.publish` | 幂等覆盖 |

几个值得记的细节：

- 实体合并是"名 → 别名"两级：先精确匹配 `name`，没有再查 `$name IN e.aliases`（`neo4j_graph_store.py:98-107`）。
- 关系边带 `source_id` / `source_type`，清理时按这两列删，所以手动建的关系（`source_id` 为空）不会被自动抽取覆盖掉。
- Chunk 级 `MENTIONS` 不调 LLM：`match_entities_in_chunks` 拿实体名和别名在块文本里做大小写无关子串匹配，长度小于 2 的词项跳过（`chunk_matcher.py:32-48`）。
- 写 Chunk 前会批量算 `embedding`：`asyncio.to_thread(embed_model.embed_documents, texts)`（`graph_service.py:201-205`）。

---

## 八、Chunk 的形状（接 Day2）

```python
id = f"{source_type}:{source_id}:{chunk_index}"     # doc:abc123:0 / note:uuid:3
MERGE (c:Chunk {id: row.id, user_id: row.user_id})
SET c.kind = row.kind, c.source_id, c.source_name, c.chunk_index,
    c.text, c.embedding, c.page, c.image_paths
```

三件事对上 Day2：

- `kind` 取 `source_type`（`note` / `doc`），就是检索时 `kinds` 过滤的那个字段。
- `id` 不含 `user_id`，所以两个用户传同一份 PDF，id 相同但节点不同——`MERGE` 键是 `(id, user_id)`。
- 检索时还要再叠一次 `c.user_id = $uid` 过滤（`neo4j_graph_store.py:716`），双保险。

---

## 九、删除

| 场景 | 入口 | 做了什么 |
| --- | --- | --- |
| 删笔记 | `cleanup_note_graph:437-450` | 事务内清图谱 + 删日志 |
| 删文档 | `cleanup_doc_graph:453-476` | 自开会话，清图谱 + 删 `graph_docs` 行与日志 |
| 清空知识库 | `cleanup_all_docs_graph:491-508` | 删该用户全部 `Doc`、doc Chunk、doc 溯源边 |
| 按文件名兜底 | `cleanup_doc_graph_by_filename:479-488` | md5 记录缺失时反查 |

图谱清理分两步：

1. `clear_source_data`（`neo4j_graph_store.py:747-764`）：单事务删源节点（连带 `MENTIONS`、`WIKI`）、删该来源的 `Chunk`、删按来源溯源的 `RELATES_TO`，返回"曾关联的实体 id"。
2. `sweep_orphan_entities`（`:766-780`）：从这些实体的 `source_note_ids` 里摘掉本来源；只有"引用清零 **且** 没有任何 `MENTIONS` 边"才 `DETACH DELETE`。

不能直接删实体的原因：同一个实体可能被别的笔记也引用着。

Neo4j 不可用时（`GraphUnavailableError` / `Neo4jError`）只跳过图谱清理并打日志，MySQL 侧照删——降级，不阻塞。

---

## 十、前端怎么知道好了

- `event_bus` 是进程内的 per-user `asyncio.Queue` 集合（`event_bus.py`）。`publish` 往该用户所有订阅队列 `put_nowait`，没有订阅者就静默丢弃。
- 成功与失败各发一次：`extract_done`（`graph_service.py:242-244`）、`extract_failed`（`:258-260`）。
- `/api/graph/events` 是 SSE 长连接（`graph_router.py:256-273`）：15 秒没事件发一条 `ping`，断开时 `unsubscribe`。
- 它是**内存事件**，进程重启就没了。但任务在 MySQL 里，重启后 worker 会接着跑，界面靠 `extract-logs` 重新对齐状态。

---

## 十一、笔记和文档的差异

| | 笔记 | 文档 |
| --- | --- | --- |
| 触发点 | 保存笔记 | 上传成功 |
| `source_id` | 笔记 UUID | 文件 md5 |
| payload | `{"text": 正文}` | `{"chunks": [...]}`，可能带 `page` / `image_paths` |
| 切片 | worker 现切（`build_text_chunks`） | 上传管线预切，worker 直接用 |
| 双链 `WIKI` | 有 | 无 |
| 正文来源 | payload；`force` 时读 `Note` 表最新内容 | payload |

---

## 十二、七个容易记错的点

1. **入队不等于入库**。`create_task` 只是往 MySQL 写一条 pending，Neo4j 里此时还没有 `Chunk`。
2. **`pending` 不能判重跳过**。跳过会导致界面永久"解析中"。
3. **worker 不是多线程**。单协程循环，一次一条任务。
4. **同 md5 不等于同一个 Chunk**。跨用户 id 相同，节点不同。
5. **删来源不等于删实体**。实体是共享的，走孤儿清扫。
6. **`event_bus` 不是消息队列**。进程内、不持久化，重启丢事件不丢任务。
7. **`force` 不重置 `attempts`**。失败满 3 次后，手动重抽只再给一次机会。

---

## 十三、面试口径

1. 写入侧是"任务表 + 应用内轮询 worker"：任务落 MySQL，进程重启不丢；认领用乐观 `UPDATE` 加 `run_token`，三处校验防旧内容覆盖新任务；失败重试上限 3 次。
2. 抽取是 LLM 抽实体/关系，落库全程按来源幂等：实体按名/别名 upsert，关系与 `MENTIONS` 先删后插，`Chunk` 用 `(id, user_id)` 复合键 `MERGE`。
3. 删除走"候选 + 孤儿清扫"，引用清零且无 `MENTIONS` 才删实体；Neo4j 不可用时只降级清理，不阻塞主流程。
