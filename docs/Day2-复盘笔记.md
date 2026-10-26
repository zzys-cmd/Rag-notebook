# Day2 复盘笔记（第 3–8 节）

> 一天的主线只有两条：
> **写入侧**：上传 → 解析 → 切片 → 贴标签 → 入队（真正落库是 Day3）。
> **读取侧**：规划 → 检索 → 评估 → 联网兜底 → 拼证据。
> 两条线在代码上互不调用，唯一交汇点是 Neo4j 里的 `(:Chunk)` 节点。

---

## 一、第 3 节 · 上传的六个动作

**结论**：上传不是"把文件存起来"，是"把文件变成能查的东西"。六步：写临时文件 → 算 md5 → 解析 → 切片 → 贴标签 → 入队。

两条路，六步相同，分工不同：

| | 单文件 `processor.py:85-253` | 流式 `knowledge_service.py` |
|---|---|---|
| ①-⑤ | 一个函数做完 | 每个线程各做各的（`_sync_slice_file:48-83`） |
| ⑥ | 同一函数里继续 | 挪到 `_process_slice_results:303-362` |

关键行：

- 临时文件 `:97-108`（三个 `asyncio.to_thread`）
- 算 md5 `:120`，查重 `:121-134`
- 解析 `:146` → 按扩展名分派 `:44-62`
- 切片 `:174`
- 贴三张标签 `:199-205`：`user_id` / `original_filename` / `md5`
- 入队 `:219` `asyncio.create_task(maybe_schedule_doc_extraction(...))`

**两个容易错的点**

1. **md5 必须在解析之前算。** `:51` 的 `if md5 and user_id:` 决定走不走多模态加载器。md5 传晚了，条件不成立，PDF 静默退回 `pdf_loader`（`:54`）——解析成功、块照样切、日志照常打"完成"，**只是图片一张都没抽**。不报错。
2. **上传的"完成"是"入队完成"，不是"可查"。** 真正写 Neo4j 的是 worker（`graph_service.py:339 process_task`）。刚传完立刻提问，检索返回空。

**附**：`get_document()` 全项目只有两个调用点——`vector_store.py:356` 和 `knowledge_service.py:110`（即 `/add/single`）。前端只调流式口（`KnowledgeBase.tsx:60`），单文件也走流式。

---

## 二、第 4 节 · 为什么切片能并行、写入不能

**结论**：切片是 CPU 重活且线程间不共享可变数据；写入要改同一份状态、追加同一个文件、按顺序发事件，而且每次只有毫秒级。

| | 切片侧 | 写入侧 |
|---|---|---|
| 在哪 | `ThreadPoolExecutor`（`:298`） | 一个协程里的 `while`（`:308`） |
| 线程数 | `min(文件数, CPU)`（`:295`） | 1 |
| 共享数据 | 无，唯一交汇点是线程安全的队列 | `state`、`md5_hex_store.txt`、`yield` 顺序 |

**背压**：`TaskQueue(maxsize=10)`（`:287`）。队列满了，`queue.put` 阻塞（`task_queue.py:34-42`），线程被迫等消费端。

**最值钱的一行**：`:311`

```python
result = await asyncio.to_thread(queue.get, True, 0.1)
```

- `to_thread`：`queue.get` 是阻塞调用，直接在协程里调会按住事件循环。
- `0.1`：等不到抛 `Empty`，`:361` 捕获后 `continue`，把控制权还回去。

**别混**：`processor.py:97/103/107` 的三个 `to_thread` 是"让路"（一个文件，把同步调用挪走），`knowledge_service.py:298` 的线程池是"并发"（多个文件同时切）。

---

## 三、第 5 节 · planner

**结论**：回答的第一步不是检索，是决定"要不要检索、用哪个工具、查什么"。

`plan()` 返回 `RetrievalPlan`（`schemas.py:31-36`），有用的三个字段：

```python
need_retrieval: bool          # 要不要查
steps: list[RetrievalStep]    # tool / query / top_k
allow_web_fallback: bool      # 只是提示，不是硬开关
```

三条填法（`planner.py:165-185`）：

1. 文本 JSON（主路径，2~4 秒）`:172`
2. pydantic 结构化（备胎）`:179`
3. 规则兜底（不调模型）`:183` → `_fallback_plan:243-266`

两个细节：

- `deadline`（`:170`）：两层共用一个 8 秒预算，不是各给 8 秒。
- `_clamp`（`:234-241`）：`steps[:2]`，`top_k` 压到 1..5。小模型会发散。

**为什么规划用小模型、评估用大模型**：`:114` 的注释写着——早先规划复用主回答模型，"那是 39 秒的来源"。规划只做"选工具 + 写 query"，小模型够；评估要判语义相关性，小模型判不准。

---

## 四、第 6 节 · 检索 + RRF

**结论**：稠密（向量）擅长意思近，稀疏（全文）擅长精确词，一次调用两路都查，按**名次**融合。

先对齐叫法：课程里的"稀疏 / 稠密"，在这个项目里叫"全文检索 / 向量检索"。

| 你学的 | 项目里的 | 索引名 |
|---|---|---|
| 稀疏（BM25） | 全文检索 | `chunk_text_index` |
| 稠密（embedding） | 向量检索 | `chunk_embedding_index` |

**四层往下的顺序**：

```
service.py:62-63   拆 graph_steps / text_steps
service.py:73-74   两个 create_task 并行
local_retriever.py:40-47   if/elif 分派四个工具名（全项目唯一一处）
local_retriever.py:54-72   _search_chunks：算向量(:61) → 调 store(:64) → 转 Evidence(:72)
neo4j_graph_store.py:674-727  真正发 Cypher
```

四个工具名的结局：

- `search_notes` → `kinds=["note"]`
- `search_knowledge_base` → `kinds=["doc"]`
- `hybrid_search` → `kinds=None`（不过滤）
- `search_graph` → `_search_graph()`，实体匹配那条路，不经过 `search_chunks`

（第五个 `web_search` 不在 `LocalRetriever` 里，`search()` 的 if/elif 没有 else，写进 steps 会被静默跳过；联网由 `service.py:182` 单独触发。）

**RRF**（`neo4j_graph_store.py:682-713`）：

```python
pool = limit * 2                                   # 每路取 2 倍候选
rrf[id] += 1.0 / (60 + rank)                       # :695 向量路
rrf[id] += 1.0 / (60 + rank)                       # :708 全文路
```

为什么不直接比分数：向量分是余弦相似度 0~1，全文分是 BM25 无上界。量纲不同，加权没有意义。RRF 只留名次，两边可比。`60` 的作用是把头部差距压平。

---

## 五、第 7 节 · evaluator

**结论**：检索永远返回 `top_k` 条，凑满不等于相关；不评估，模型就会拿噪声硬编。

四条出口（`evaluator.py:77-117`）：

| 情况 | 结果 | 行 |
|---|---|---|
| 一条证据都没有 | 不可答 | `:79` |
| 含"最新 / 今天 / 价格 / 版本" | 不可答，必须联网 | `:87` |
| 其余 | 交 LLM 判 | `:104` |
| LLM 不可用或报错 | **判可答** | `:99` / `:109` |

**为什么失败时判"可答"**：两种判错的代价不对称。判可答判错，少搜一次网；判不可答判错，每个问题都多一次外部搜索，更慢更贵还可能搜偏。而且模型不可用通常说明外部服务已经不稳，再让它联网大概率也失败。

**联网触发**：`_maybe_search_web`（`service.py:158-195`）接收 `answerability` 参数，自己不再判断可答性。`:170` 只有"可答且 `web_queries` 为空"才不搜。`allow_web_fallback` 不参与判断（注释 `:166-168`）。

**新鲜词表**：`FRESHNESS_TERMS` 在 `planner.py:10-24`，`evaluator` 从这里 import（`:11-15`）。一共 14 个中英文词。

---

## 六、第 8 节 · 拼 context

**结论**：三路证据会重复，全塞进 prompt 又长又容易被忽略。两道去重 → 最多 8 条 → 6000 字封顶。

**两道去重各管一种重复**（`evidence.py:17-39`）：

- `(source, id)`：同一条记录被收集两次（文本检索和图谱检索各返回一次）。
- 归一化内容 `re.sub(r"\s+", " ", c).strip().lower()`：不同记录但内容一样（同一段话笔记和 PDF 各一份）。

**6000 字封顶**（`:42-62`）：`if used + len(block) > max_chars: break`。是 `break`，不是 `continue`——这一条放不下，后面的也不要。

**为什么整条丢而不是截一半**：模型不知道文字被截断，会把半句当完整句子读。截断还可能把意思截反（"不支持 A，但支持 B" → "不支持 A"）。少一条相关内容，比喂半句话更便宜。

---

## 七、今天补的底层概念

**async / await / asyncio**

- `async def` 定义协程，调用不执行，返回协程对象。
- `await` 暂停当前协程，把控制权交回事件循环，完成后再从原处继续。
- `asyncio` 提供事件循环；`asyncio.run()` 启动它。

**线程 vs 协程**

| | 线程 | 协程 |
|---|---|---|
| 调度 | 操作系统 | 事件循环 |
| 切换 | 随时，抢占式 | 只在 `await` 处 |
| 并行 | 多核上真并行 | 同一时刻只有一个 |
| 共享数据 | 要加锁 | 同线程内，不跨 `await` 不用锁 |

**什么时候用哪个**：等得多 → asyncio；算得多 → 多进程；手上只有同步库 → `to_thread` 或线程池。

---

## 八、教案里两处要改

1. **第 3 节的答案不准确**。教案写"md5 算晚了图片会落到错误目录"，代码实际是 `processor.py:51` 的 `if md5 and user_id:` 不成立，**静默退回纯文本加载器**，图片根本不抽。
2. **附录 F 对 `vector_store.py` 的描述不对**。教案写"只转发，自己不做业务"，实际它是单例句柄：持有 `MD5Store` 和 `DocumentProcessor`，知识库的列表/详情/切片查询也从它出。

---

## 九、还没学的

1. **第 9 节 `reorder_service`**：不在主链路，只服务 `POST /chat/reorder`。
2. **Day3 的图谱 worker**：`graph_service.process_task` 在后台消费入队的任务、真正写 Neo4j。
3. **多模态 PDF 加载器**：`pdf_multimodal_loader` 怎么抽图、怎么调视觉模型生成描述。
4. **八节之后的"串一遍"**：拿一份真 PDF，从点上传走到出答案。

---

## 十、面试口径（三句话）

1. 写入侧是生产者—消费者：切片丢线程池并行，写入单线程串行，队列 `maxsize=10` 做背压；块带 `user_id` 为检索隔离做准备；上传完成只代表入队完成，落库在后台 worker。
2. 读取侧五步：规划（小模型、三层降级、输出钳位）→ 图/文并行检索（向量 + 全文 RRF 融合）→ 可答性评估 → 联网兜底 → 去重后 6000 字封顶。
3. 降级处处存在：planner 三层降级、图检索挂了文本照用、evaluator 挂了判可答、reorder 挂了按原序——每一处都是"失败时选便宜的那条路"。
