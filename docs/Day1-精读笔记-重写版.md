# Day 1 精读笔记（重写版）：请求链路与 Agent

> 本笔记依据两份材料重写：
> 1. 资料库文档《Day1 精读笔记：请求链路与 Agent》（原文档保持不动）
> 2. 2026-10-17 ~ 10-18 的完整带读对话（含逐行核对源码的结果）
>
> 行号基于当前 `backend/` 源码。凡与原笔记冲突处，一律以源码为准，差异见文末「附录 A」。

---

## 0. 一句话记住 Day 1

> 一次提问 = **入口验票（chat.py）→ 前置 RAG 兜底检索 → 外壳接货开机（agent.py 2c）→ 框架内部跑"模型↔工具"循环 → 工具箱出手（agent_tools）→ 中间件记录与拦截（agent_middleware）→ 需要时二次检索（agent_rag_tool）→ 按四种结局收尾**。

四个角色分工：

| 层 | 文件 | 一句话职责 |
|---|---|---|
| 入口 | `app/router/chat.py` | 验身份、限流、跑第一遍 RAG、交接、提供 resume 入口 |
| 外壳 | `app/agent/agent.py` | 递小抄、开直播、按结局收尾 |
| 工具箱 | `app/agent/agent_tools.py` | 让模型"能动手"：8 件工具 |
| 护栏+审批 | `app/agent/agent_middleware.py` | 记录、限次重试、写操作先问人 |
| 二次检索 | `app/agent/agent_rag_tool.py` | 自主补搜 + 三重护栏 |

---

## 1. 全局时序：一个请求穿过 8 个文件

以「上周那篇切片策略的笔记太乱，帮我整理成一篇新笔记，标题《切片策略整理》」为例：

```
① 前端 POST /chat/agent/query/stream
      ↓
② chat.py            两道闸（JWT + 限流）→ 生成/沿用 session_id
      ↓
③ chat.py 后台任务    第一遍 RAG（AgenticRagService.run）产出 rag_context
      ↓               前台同时发占位帧，前端折叠框立刻出现
④ chat.py 交接         rag_context + searched_queries → get_agent_stream_response
      ↓
⑤ agent.py 2c        设身份、初始化检索护栏、读会话历史、注入证据、造 Agent、开机
      ↓
⑥ agent_tools.py     模型调 search_notes_tool 翻已有笔记
      ↓
⑦ agent_rag_tool.py  证据不够时调 search_rag 补搜（三重护栏）
      ↓
⑧ agent_middleware   全程日志/计时/限次；create_note_tool 命中白名单 → 中断
      ↓
⑨ agent.py 2c        查中断 → 记 pending_run_id → 发 interrupt 帧（thread 保留）
      ↓
⑩ chat.py resume     用户点批准 → /chat/agent/resume → Command(resume=...)
      ↓
⑪ agent_tools.py     create_note_tool 真正执行，写入 MySQL
      ↓
⑫ agent.py 2c        回答写会话历史 → 删 thread → 发 done 帧
```

涉及文件（按出现顺序）：

| # | 文件 | 作用 |
|---|---|---|
| 1 | `app/router/chat.py` | 入口、流式编排、resume 入口 |
| 2 | `app/rag/agentic_rag/service.py` | 第一遍 RAG 主流程（Day 2 拆） |
| 3 | `app/agent/agent.py` | 工厂 + 事件转发 + 生命周期收尾 |
| 4 | `app/agent/agent_tools.py` | 8 件工具 |
| 5 | `app/agent/agent_rag_tool.py` | 第二遍检索工具 |
| 6 | `app/agent/agent_middleware.py` | 观测钩子、重试限次、HITL |
| 7 | `app/agent/checkpoint/mysql_saver.py` | 暂停现场存哪 |
| 8 | `app/services/session_manager.py` | 会话历史、pending 标记（间接） |

---

## 2. 站点 1：`router/chat.py`（234 行）

### 2.1 文件头 docstring 就是设计文档（L1-5）

```python
"""Chat 路由：Agent 对话（流式/非流式）与 Agentic RAG 前置检索编排。
流式端点时序：先发占位 thinking 帧（前端折叠框即时出现）→ 转发 RAG 真实思考事件 →
Agent 流式回答 → done；RAG 失败不阻塞回答（rag_context 置空继续走 Agent）。
"""
```

读路由文件先读 docstring，作者已经把时序写好了。

### 2.2 两道闸（L40-47）

```python
@chat_router.post("/agent/query/stream")
async def query_stream(
        request: QueryRequest,
        user_id: str = Depends(get_current_user_id),        # 闸 1：JWT → user_id
        _: None = Depends(rate_limit(limit=10, window=60))  # 闸 2：每分钟最多 10 次
):
    session_id = request.session_id or str(uuid.uuid4())
```

- `request: QueryRequest` 是**请求体模型**（定义在 `app/schemas/models.py`）：`session_id`（可选）+ `query`（必填）。Pydantic 负责校验，格式不对直接拒收。
- `session_id` 没传就现场生成 —— 前端刷新后带着旧 id 回来，就能续聊。

### 2.3 传菜口三件套（L49-86）

```python
thinking_queue = asyncio.Queue()   # 传菜口
rag_done = object()                # 收工哨兵

async def thinking_callback(data: dict):
    await thinking_queue.put(data)  # RAG 每想一步就递一张纸条

async def run_rag():
    try:
        return await AgenticRagService().run(request.query, user_id, thinking_callback=thinking_callback)
    except Exception as e:
        logger.error(...)
        return None                 # RAG 挂了不抛，优雅降级
    finally:
        await thinking_queue.put(rag_done)   # 无论成败，哨兵一定放

rag_task = asyncio.create_task(run_rag())    # 后台跑
```

三个要点：

1. **`thinking_callback`**：把"往队列塞事件"的函数交给 RAG，RAG 内部每产生思考事件就调一次。这是「回调 → 队列 → SSE」解耦的起点。
2. **`return None` 而不是抛异常**：检索挂了，对话照常进行（少证据而已）。
3. **`finally` 放哨兵**：保证消费循环任何情况都能退出，不会死等。

### 2.4 占位帧与消费循环（L75-86）

```python
yield "data: " + json.dumps({
    "type": "thinking", "stage": "agentic_plan",
    "content": "正在规划检索策略…",
    "details": {"placeholder": True},
}, ensure_ascii=False) + "\n\n"

while True:
    event = await thinking_queue.get()
    if event is rag_done:     # 用 is 不用 ==：哨兵是唯一对象
        break
    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
```

- **占位帧**：LLM 规划要 1-3 秒，先发一帧假的，让前端折叠框立刻出现。`placeholder: True` 是给**前端代码**看的暗号，表示"收到真事件后替换我"。
- **`is` 判断**：`object()` 是唯一实例，绝不会和真实事件撞车。用字符串 `"done"` 当哨兵，万一某条内容恰好是 "done" 就出 bug。

### 2.5 两行交接（L88-104）

```python
result = await rag_task
rag_context = result.context or ""
searched_queries = build_pre_searched_queries(request.query, result)

async for chunk in get_agent_stream_response(
    request.query, session_id, user_id,
    rag_context=rag_context,                    # 交接物①：证据
    rag_searched_queries=searched_queries,      # 交接物②：已搜关键词清单
):
    yield chunk
```

**为什么检索跑两遍**：

| | 第一遍（前置 RAG） | 第二遍（search_rag） |
|---|---|---|
| 谁发起 | 服务端**强制** | Agent **自主** |
| 定位 | 保底：保证开局有证据、首字延迟可预期 | 补缺：它读着证据答题，最清楚还缺什么 |
| 为什么不能只留这一遍 | 只留前置：一次盲查，漏了没人补救 | 只留自主：每句都要模型决策，闲聊也决策，首轮必然空白，且全靠模型自觉 |

**防重复只靠交接物②**：`searched_queries` 会被 `init_rag_guard()` 预置进护栏；`rag_context` 只是证据，不参与去重。

### 2.6 耗时与收尾（L105-124）

- `TTFB`（首 token 时间）= 用户发问到看到第一个字，日志拆成「RAG 耗时 + Agent 启动耗时」两段。可观测性，方便定位慢在谁身上。
- `finally: if not rag_task.done(): rag_task.cancel()` —— Agent 阶段异常提前退出时，取消后台任务，不留孤儿协程。
- 返回 `StreamingResponse(..., media_type="text/event-stream", headers={"Cache-Control": "no-cache", "Connection": "keep-alive"})`。

### 2.7 resume 端点（L133-159）

```python
pending_run_id = await sm.session_manager.get_pending_run_id(request.session_id, user_id)
if not pending_run_id:
    yield f"data: {json.dumps({'type': 'error', 'content': 'RESUME_MISMATCH'})}\n\n"
    return
```

`run_id` 从服务端会话里取，**不信任客户端传值**。找不到就报 `RESUME_MISMATCH`——这正是"记忆本被误删"时会出现的症状。

---

## 3. 站点 2：`agent/agent.py`（808 行，精读 3 段）

### 2a. AgentFactory（L35-144）——造助手

`create_agent()` 每次调用都现造一个全新实例（L121 注释：彻底避免全局状态污染）。装配 5 样东西：

```python
return create_agent(
    chat_model,                      # 大脑（OpenAI 兼容协议，默认 qwen3-max）
    tools,                           # 工具箱（9 件）
    system_prompt=system_prompt,     # 员工手册
    middleware=self.default_middleware,  # 9 个中间件
    checkpointer=get_checkpointer(), # 记忆本（MySQL）
)
```

**9 件工具（L71-81）**：时间、用户信息、搜笔记、笔记统计、今日回顾、标记已回顾、创建笔记、关联推荐、`search_rag`（第 9 件在另一个文件）。

**无状态工厂 vs 懒加载单例**：

- 助手：每次现造（编译图实例，用完即弃）
- 记忆本：全局一个（`get_checkpointer()` L152-159 懒加载），因为背后是数据库连接，建造成本高，必须共用

**代价**：每次重建有开销，L595-596 专门记录 `create_agent` 耗时。

### 2b. `_emit_agent_events`（L474-543）——事件转发

```python
async for event in agent.astream_events(inputs, config=config, version="v2"):
```

只关心 4 类事件：

| 事件 | 处理 | 前端效果 |
|---|---|---|
| `on_chat_model_stream` | 逐块累积并转 `response` 帧；**跳过 `tool_call_chunks`** | 回答逐字出现 |
| `on_tool_start` | 转 `thinking` 帧（工具名 + 入参） | "正在调用 xxx" |
| `on_tool_end` | 转 `thinking` 帧（工具名 + 输出） | "xxx 执行完成" |
| `on_chat_model_end` | 若 `full_response` 为空（非流式模型），兜底收割全文 | 兼容非流式模型 |

结尾的关键一行：

```python
snapshot = await agent.aget_state(config)
return _interrupt_payload(snapshot), None
```

==> **中断不是靠 try/except 抓的，是"正常跑完之后主动查快照"查出来的。** `_interrupt_payload` 要求 interrupts 里含 `action_requests` 才算数。

### 2c. `get_agent_stream_response`（L546-689）——生命周期

#### 结构：一个函数里两个角色

| 角色 | 代码 | 干什么 |
|---|---|---|
| 后台 | `run_agent()`（L572 起），`create_task` 于 L642 | 设身份 → 查 pending → 读历史 → 造 Agent → 跑 |
| 前台 | `while not agent_done.is_set()`（L645） | 守队列，捡到一帧就 `yield` |

通讯靠 `thinking_queue`；结局靠 `agent_result_holder`（结果登记处，L564）传递——因为后台协程的返回值前台拿不到。

#### 开场（L644）

```python
yield f"data: {json.dumps({'type': 'response', 'content': '', 'session_id': session_id})}\n\n"
```

空 content 的**握手帧**，作用有二：告诉前端"接上了"；把现场生成的 `session_id` 交给前端（新会话续聊的前提）。

#### 后台准备（L574-598）

| 行 | 动作 | 为什么 |
|---|---|---|
| L574 | `set_current_user_id(user_id)` | 放进 ContextVar，工具后面要靠它认人 |
| L575 | `set_thinking_callback(...)` | 工具/中间件要往队列推事件 |
| L576 | `init_rag_guard(rag_searched_queries)` | 预置已搜清单，防第二遍重复 |
| L580-583 | 查 pending，还在等审批 → `PENDING_EXISTS` 直接返回 | 挡回新问题，保住审批现场 |
| L585-586 | 从 MySQL 读会话历史 | 新助手一睁眼就有聊天记录 |
| L587-590 | 有证据则换 `rag_context_prompt` 模板 | **证据是通过系统提示词注入的**，不是当消息发 |
| L592 | `create_agent(...)` | 造 |
| L600-601 | `_emit_agent_events(...)` | 跑（内部 L499 才是 `astream_events`） |

#### 四种结局（L603-671）

| # | 结局 | 判据 | 后台动作 | thread | 前端末帧 |
|---|---|---|---|---|---|
| ① | 正常完成 | 无中断、无异常 | `add_message` 写会话历史（L622-625） | **删**（L637） | `done` |
| ② | 卡审批 | `aget_state` 查到 interrupts | 记 `pending_run_id`（L619）、不写镜像 | **留** | `interrupt` |
| ③ | 被挡回 | `_pending_is_active()` 为真 | 直接 return，未造 Agent | 不涉及 | `error: PENDING_EXISTS` + `done` |
| ④ | 异常 | `except` 抓到 | 若已有中断则不覆盖 | **删** | `error` + `done` |

**为什么删/留区别对待**：正常完成时答案已进"正式档案"，thread 只是用过的草稿，不清会撑爆数据库；卡审批时活儿才干到一半，**thread 是唯一现场**，删了用户点批准就只能得到 `RESUME_MISMATCH`。

**`_pending_is_active`（看是否真在等）**：读 checkpoint 的 `pending_writes`，里面有 `"__interrupt__"` 通道才算还在等；读不到/异常一律按"还在等"处理——**宁可挡住新问题，也不丢审批现场**。

**异常分支的保护**（L629-630）：若已记录中断，就不让 error 覆盖它——现场比错误信息重要。

**外层兜底**（L672-689）：前端断网/取消 → `agent_task.cancel()` → 幂等再删一次 thread。

---

## 4. 站点 3：`agent/agent_tools.py`（175 行）

### 4.1 两枚 ContextVar（L13-14）

```python
current_user_id_var: ContextVar[str] = ContextVar('current_user_id', default=None)
thinking_callback_var: ContextVar[Callable | None] = ContextVar('thinking_callback', default=None)
```

**为什么不用全局变量**：异步服务里请求并发，全局变量会互相覆盖——A 的请求刚 `set` 完，B 的请求覆盖成 B，A 的工具一读就读到 B，**A 看到 B 的笔记**。这种 bug 取决于时序，最难查，也最严重（数据越权）。

`ContextVar` 是**协程级隔离**：每个请求一份副本，请求结束即弃。凡"这次请求专属"的状态都不能放全局。

### 4.2 8 件工具

| 工具 | 参数 | 干什么 |
|---|---|---|
| `what_time_is_now` | 无 | 当前时间 |
| `get_user_info_tools` | token | 从 JWT 解用户 ID/名 |
| `search_notes_tool` | query, top_k | 语义搜笔记 |
| `get_note_stats_tool` | 无 | 笔记统计 |
| `get_today_reviews_tool` | 无 | 今日待回顾 |
| `mark_reviewed_tool` | note_id | 标记已回顾（艾宾浩斯间隔） |
| `create_note_tool` | title, content | 创建笔记（**需审批**） |
| `get_related_notes_tool` | note_id, top_k | 关联推荐 |

### 4.3 工具的"三件套"（以 `search_notes_tool` L50-73 为例）

```python
@tool(description="语义搜索用户的笔记，根据关键词返回最相关的笔记列表...")
async def search_notes_tool(query: str, top_k: int = 5) -> str:
    user_id = get_current_user_id_from_context()   # ① 认人
    if not user_id:
        return "错误: 无法确定用户身份"
    async with AsyncSessionLocal() as db:          # ② 干活
        try:
            results = await ...
            return "\n".join(lines)                # ③ 返回中文文本
        except Exception as e:
            logger.error(...)
            return f"搜索笔记时出错: {str(e)}"      # 不抛异常
```

1. **`description` 是写给模型看的说明书**，不是注释。模型只看得到 description + 参数名，看不到函数体。
2. **认人**：拿不到 `user_id` 直接拒绝，宁可不干活也不查错人。
3. **异常翻译成文本**：工具一 `raise`，整个 Agent 循环就崩；返回一句"出错"，模型还能决定换法或告知用户。这是 Agent 工具的必修课。

### 4.4 返回值即 prompt 工程

工具返回的是**排版好的中文**（标题、分类、标签、预览），因为要作为 `ToolMessage` 喂回模型。格式清晰，模型提取就准；一团乱，答得就歪。

---

## 5. 站点 4：`agent/agent_middleware.py`（222 行）

### 5.1 中间件是什么

在"模型调用"和"工具调用"前后插一脚的钩子。代码不用改，调用自动经过它们。本项目共 9 个，分两类（**注："观测型/保护型"是便于理解的说法，官方只叫 middleware**）：

**A. 自定义钩子（6 个，只记录不拦截）**

| 钩子 | 时机 | 干什么 |
|---|---|---|
| `before_agent` / `after_agent` | Agent 整体前后 | 日志：消息数、角色、字符数 |
| `before_model` / `after_model` | 每次模型前后 | 同上 |
| `model_call_hook`（`wrap_model_call`） | 包住模型调用 | 计时 + token 用量 + >5s 告警 + 推 `model_metrics` |
| `tool_call_hook`（`wrap_tool_call`） | 包住工具调用 | 计时 + 参数截断日志（200 字） |

包装器的写法就是"在 `await handler(request)` 外面套一层"：

```python
@wrap_model_call
async def model_call_hook(request, handler):
    start = time.perf_counter()
    response = await handler(request)
    duration_ms = (time.perf_counter() - start) * 1000
```

**B. 官方中间件（3 个，会拦截）**

```python
ModelRetryMiddleware(max_retries=2),    # 模型失败重试 2 次
ToolRetryMiddleware(max_retries=1),     # 工具失败重试 1 次
ToolCallLimitMiddleware(run_limit=5),   # 单轮最多调 5 次工具
```

它们替代旧版 `max_iterations` 的语义，防"无限调工具"——循环能正常转，但永不收敛，烧钱、超时。

### 5.2 HITL 审批（L213-219）

```python
HumanInTheLoopMiddleware(
    interrupt_on=approval_tools or DEFAULT_APPROVAL_TOOLS,
    description_prefix="工具执行需要你的确认",
)
```

白名单（L82-87）：

```python
DEFAULT_APPROVAL_TOOLS = {
    "create_note_tool": {
        "allowed_decisions": ["approve", "reject"],
        "description": _describe_create_note,
    },
}
```

- 键：命中这个工具名才停
- `allowed_decisions`：批准 / 拒绝
- `description`：**弹窗文案生成函数**。`_describe_create_note`（L73-80）只取标题 + 正文长度 + 前 120 字预览——**避免把全文塞进审批负载**

**为什么只拦 create_note**：审批门槛应设在"有副作用、不可逆"的写操作上。读操作（搜索）拦了只增加打扰、不增加安全。本项目 8 件工具里唯一的写操作就是创建笔记（**没有删除、没有更新**）。

### 5.3 审批全链路

```
模型决定调 create_note_tool
  → HITL 命中白名单，中断执行（工具一行都没跑）
  → 现场存进 checkpoint thread
  → agent.py L539-540 aget_state 查到 interrupt
  → 记 pending_run_id（L619）+ 发 interrupt 帧
  → 前端弹窗（标题 + 120 字预览）
  → 用户点批准 → POST /chat/agent/resume
  → agent.py L743 重新 create_agent，L746 Command(resume={"decisions": [...]})
  → 工具这时才真正执行
  → 回答落库 + 删 thread
```

---

## 6. 站点 5：`agent/agent_rag_tool.py`（207 行）

### 6.1 工具定义（L98-103）

```python
@tool(description=(
    "在你的本地知识库/笔记/知识图谱中做补充检索，返回带来源标注的证据摘要。"
    "仅在已有参考资料不足、需按新维度深挖、或需验证具体事实时调用；"
    "参数 query 必须是本轮尚未检索过的新聚焦角度，不要重复已覆盖的问题。"
))
async def search_rag(query: str) -> str:
```

description 在教模型"什么时候调、别重复"——**工具描述就是行为约束**。

### 6.2 三重护栏

| 护栏 | 代码 | 作用 |
|---|---|---|
| 同 query 短路 | L116 | `normalize_query` 去标点/空白/小写后比对，换个标点重问也拦得住 |
| 限次 | L21 / L122 | `MAX_RAG_CALLS = 2` |
| ContextVar 存状态 | L26 / L113 | 每请求独立计数，A 的 2 次不算到 B 头上 |

`normalize_query`（L34-39）：`"你好，Python？"` 与 `"你好 python"` 归一化后同为 `"你好python"`。

### 6.3 三个细节

1. **失败不占配额**：`guard["count"] += 1` 写在检索成功之后（L145-147）
2. **搜不到也返回文本**："未找到证据（非事实证据）"，Agent 可继续答
3. **"（非事实证据）"标注**：防止模型把状态提示当成证据引用

### 6.4 与站点 1 的闭环

`chat.py` 把第一遍搜过的关键词交给 2c → 2c `init_rag_guard()` 预置 → 第一遍搜过的词，第二遍必然被拦。**这是"两遍不重复"的实现**。

---

## 7. 关键概念对照

| 概念 | 是什么 | 别搞混 |
|---|---|---|
| `session_id` | 一个聊天窗口 | 一个会话里可以有多次提问 |
| `thread`（= `run_id`） | 一次提问的过程存档编号 | 一次提问一个；正常结束即删，卡审批才留 |
| 会话镜像（MySQL） | 正式档案：一问一答 | 长期保存 |
| checkpoint（记忆本） | 过程现场：做到哪、想调什么 | 临时，按结局删留 |
| `agent_result_holder` | 后台给前台的小黑板（dict） | 传"结局"，不存业务数据 |
| 两层 RAG | 前置强制 + 自主补搜 | 防重复靠"已搜清单" |

---

## 8. SSE 帧格式与五种帧

**帧格式**：

```
data: {"type":"thinking","stage":"agentic_plan","content":"正在规划检索策略…","details":{...}}\n\n
```

- `data: ` 开头 + JSON
- `\n\n` 结尾 = SSE 帧分隔符（前端靠它切分）
- `ensure_ascii=False`（中文不转义）
- 响应头：`text/event-stream`、`no-cache`、`keep-alive`

**五种帧**：

| 帧 | 什么时候发 | 内容 | 前端用途 |
|---|---|---|---|
| `thinking` | 检索规划/步骤、工具开始结束、模型指标 | stage + content + details | 思考折叠框 |
| `response` | 模型每吐一小段；第一帧是空 content 握手帧 | content + session_id | 追加正文 / 拿会话 id |
| `interrupt` | 命中审批、流程暂停 | run_id + payload | 弹审批框 |
| `error` | 被挡回（PENDING_EXISTS）或异常 | 错误文本/码 | 显示错误 |
| `done` | 正常答完；error 之后补一帧 | session_id | 关加载动画 |

正常序列：`response(空)` → `thinking × N` → `response × N` → `done`；命中审批中止于 `interrupt`（无 done）。

---

## 9. 六道自测题与答案

### 题 1　一条消息从前端到最终回答，经过哪些文件、哪些阶段？

**答**：

```
① 前端 → chat.py（POST /chat/agent/query/stream）
② 两道闸：JWT 解 user_id + 限流 10 次/分钟
③ 后台 create_task 跑第一遍 RAG，产出 rag_context（前台同时发占位帧）
④ 交接两样：rag_context（证据）+ searched_queries（已搜清单）
⑤ agent.py L592 造 Agent → L499 astream_events 开机
⑥ 事件进 asyncio.Queue → 前台 while 循环 yield 成 SSE 帧
⑦ 四种结局：正常存历史删 thread / 卡审批留 thread 挂牌 / PENDING_EXISTS 挡回 / 异常删 thread 报错
```

### 题 2　前置 RAG 和 search_rag 是什么关系？为什么检索跑两遍？

**答**：前置 RAG 是服务端强制的兜底检索，保证开局有证据、首字延迟可预期；`search_rag` 是 Agent 的自主补充，它读着证据答题，最清楚还缺什么。两遍靠"已搜清单"（`searched_queries` → `init_rag_guard`）防重复。去掉前置，漏检无人补救；去掉自主，检索变成一次性盲查。

### 题 3　SSE 每一帧长什么样？五种帧分别什么时候发？

**答**：`data: {JSON}\n\n`，两个换行是帧分隔符，`text/event-stream` 响应头。五种帧见第 8 节表格。

### 题 4　用户 A 和 B 同时提问，工具里怎么知道该查谁？

**答**：靠 `ContextVar`。请求进入时 `set_current_user_id(user_id)`（agent.py L574），工具里 `get_current_user_id_from_context()` 取出。协程级隔离，各请求有自己的副本。若用普通全局变量，后到的请求会覆盖先到的，导致 A 的工具查到 B 的数据——数据越权，且依赖时序、极难排查。

### 题 5　用户说"帮我创建一篇笔记"，Agent 决定调 create_note_tool，接下来发生什么？

**答**：

1. `HumanInTheLoopMiddleware` 查白名单，命中 `create_note_tool`
2. **工具没有执行**（先问再执行）
3. 现场存进 checkpoint thread（做到哪、想调什么、参数）
4. `aget_state` 查到中断 → 记 `pending_run_id` → 发 `interrupt` 帧 → 前端弹窗（标题 + 120 字预览）
5. 用户批准 → `/chat/agent/resume` → 取出 `pending_run_id` → `Command(resume={"decisions":[...]})` → 工具真正执行 → 回答落库 + 删 thread

### 题 6　正常完成 vs 审批中断，thread 分别怎么处理？为什么？

**答**：正常完成 → 回答已进会话历史（正式档案），thread 是废草稿，删掉省存储；审批中断 → 活儿才干到一半，**thread 是唯一现场**，必须留，同时记 `pending_run_id` 挂牌。若误删，用户点批准时服务端找不到现场，只能返回 `RESUME_MISMATCH`，Agent 想做的事永远做不成。

---

## 10. 面试可用的三句话

1. "两层 RAG：前置检索由服务端强制跑，负责覆盖率兜底；`search_rag` 由 Agent 自主调用，负责精准补搜。两者通过已检索关键词集合去重，并用 ContextVar 做请求级隔离。"
2. "Agent 侧用 LangChain 1.0 中间件做观测与治理：自定义钩子记模型/工具耗时与 token，官方中间件负责重试上限与单轮工具调用限次，HITL 中间件对写操作做人工审批，中断现场存 checkpoint，恢复走 `Command(resume=...)`。"
3. "会话历史与 checkpoint 分离：历史是正式档案（MySQL），checkpoint 是一次运行的过程现场，正常结束即删、审批中断保留，避免孤儿数据堆积，也保证审批可恢复。"

---

## 附录 A：与原笔记的三处出入（以源码为准）

| 项 | 原笔记说法 | 实际代码 |
|---|---|---|
| 站点编号 | 工具层被写作"站点 3"、中间件"站点 4"、`agent_rag_tool` "站点 5"（此编号正确）；但实际带读时曾把工具层误标为"站点四" | 以本笔记第 1 节为准：站点 1 chat.py / 2 agent.py / 3 agent_tools / 4 agent_middleware / 5 agent_rag_tool |
| 审批白名单 | "删笔记这类危险操作要先人工确认" | `DEFAULT_APPROVAL_TOOLS` 只有 `create_note_tool`；项目**没有删除工具** |
| 生命周期分支 | 只列四种分支但未给判据来源 | 四种结局的判据分别是：无中断无异常 / `interrupts` 含 `action_requests` / `_pending_is_active()` 为真 / `except` 捕获 |

## 附录 B：易错点清单

- `event is rag_done` 用 `is`，不用 `==`
- 占位帧的 `placeholder: True` 是给前端代码看的，不是给人看的
- 证据通过**系统提示词**注入（`rag_context_prompt`），不是当消息发
- HITL 是"先问再执行"，不是"先执行再问"
- 正常完成才删 thread；中断必须留
- 工具的异常要 `return` 文本，不要 `raise`
- `ContextVar` 不只是拿 user_id，护栏计数、thinking_callback 用的也是它
