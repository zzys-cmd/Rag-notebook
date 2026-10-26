# Agent 项目面试深挖手册

> 覆盖范围：`backend/app/agent/`（1727 行，5 个文件）+ `router/chat.py` + `tests/agent/`。
> 行号基于 2026-10 源码。每题标了优先级：
> **★★★ 答不出就挂** ｜ **★★ 区分"真做过"和"抄的"** ｜ **★ 说出来加分**

---

## 0. 面试官挖项目的固定套路

任何项目题，面试官都是四层往下钻，钻到你答不出为止：

| 层 | 他在问什么 | 你要准备的 |
|---|---|---|
| 一 | 你做了什么 | 30 秒说清 + 能指着代码说"这里是我写的" |
| 二 | 为什么这么做 | 有没有比较过替代方案，为什么否掉 |
| 三 | 出问题怎么办 | 异常、并发、边界、数据不一致 |
| 四 | 怎么验证的 | 指标、测试、线上 badcase |

**关键判断**：绝大多数人卡在第二层（只会说"教程这么写的"）和第三层（没想过会出问题）。
你项目里第三层有大量真实素材 —— 见文末「6 个真实的坑」，那是最能证明"这是我写的"的部分。

---

## 1. 30 秒 / 2 分钟项目介绍

### 30 秒版（背下来）

> 一个带知识图谱的 AI 笔记应用。后端 FastAPI，MySQL 存业务数据，Neo4j 存实体关系。
> 核心是两条链路：文档上传后异步构建知识图谱；问答时先跑一条 Agentic RAG 管线（规划检索策略 → 多路召回 → 重排 → 证据评估），把证据拼进上下文，再交给 LangGraph 的 Agent 循环 —— 它手上有 9 个工具，能自己查笔记、建笔记、再检索。
> 我重点做的是 Agent 这一层：多轮工具编排、流式输出、以及写操作的人工审批（HITL）。

### 2 分钟版（加三件事）

在上面基础上补：

1. **为什么要有 Agent，不直接 RAG**：RAG 是"一次检索然后回答"，遇到"我上周记的那篇关于 XX 的笔记和今天的有什么关系"这种需要多步才能答的问题就断了。Agent 能自己决定"先搜笔记、发现不够、换个角度再搜"。
2. **为什么要有审批**：Agent 有写权限（`create_note_tool`），模型幻觉时可能凭空建一堆笔记。所以写操作走人工中断，用户点确认才执行。
3. **工程上最难的部分**：审批中断意味着一个 run 会跨请求存活 —— 状态得落盘、恢复得能续、还得防重复执行。我自己实现了 MySQL 版的 checkpointer 来做这件事。

---

# 第一部分：项目定位与架构

### A1 用一句话介绍这个项目　★★★

- **考**：表达力。答不上来后面全是减分。
- **答**：见上面 30 秒版。
- **追问**：那你负责哪部分？（**必须能明确切出一块说"这是我做的"**，别答"都是我做"）

### A2 为什么用 MySQL + Neo4j 两个库？一个不够吗　★★★

- **考**：技术选型是否有判断，还是照抄教程。
- **答**：两类数据形状不同。笔记、会话、任务队列是强 schema、要事务、要分页的，MySQL；实体和关系是多跳遍历（"这篇笔记提到的概念，还出现在哪些文档里"），用 MySQL 得写递归 CTE 或多次 join，Neo4j 一条 Cypher 就完了。
- **反向答法（更显水平）**：也可以说"如果数据量不大，其实一个 Postgres + 邻接表就够，我选 Neo4j 是因为想练这块，代价是多一套运维和一致性问题 —— 删文档时要同步清图谱里的孤儿节点"。
- **位置**：`app/graph/`、`app/db/db_config.py`
- **追问**：两个库怎么保证一致性？（没有分布式事务，靠 `graph_build_tasks` 表做最终一致 + 孤儿清扫，见 `neo4j_graph_store.py:747`）

### A3 前置 RAG 是每轮对话都跑吗？成本多少　★★

- **考**：有没有算过账。
- **答**：`router/chat.py:61` 的 `run_rag()` 是无条件执行的。是否真检索由 planner 内部判断（`planner.py:165` 的三层降级 + `need_retrieval`），所以闲聊类问题不会真去检索，但**规划这一步的模型调用省不掉**。
- **可加分**：这是我后来发现的一个浪费 —— 应该在入口加一层轻量路由（比如意图分类或 embedding 相似度阈值），明显不需要检索的直接跳过 planner。代码里 `fakes.py` 还留着 `compute_route_score` 的替身，说明原本设计过这个路由层，后来没接上。

### A4 你的技术栈为什么是 FastAPI + React　★★

- **答**：FastAPI 的原生 async 和 SSE 支持直接对上"模型流式输出"这个需求；Pydantic 做请求校验和 schema 复用成本很低。
- **追问**：为什么不用 Django？（如果你答"没想过"，减分）**注意**：代码里有 `decode_django_jwt`（`utils/auth_utils.py`），说明 JWT 是 Django 侧签发的 —— 面试官如果细看会问"为什么一个项目有两套后端框架"。**这个你要提前想好说法**，或者承认这是历史遗留、两边共用一套 JWT 密钥。

### A5 这个项目的用户量、数据量大概多少　★★

- **考**：是不是真跑过，还是本地 demo。
- **答**：诚实说"个人项目，本地/小规模部署，没有真实用户量"。**不要编**。
- **补救**：主动补一句"但我做过压力和耗时统计" —— 代码里有完整的耗时埋点（`【Agent耗时】`、`【端到端耗时】`，见 `agent.py:512/596`、`chat.py:92/109`），能说出首 token 大概几百毫秒、RAG 阶段占多少，比编用户量强。

### A6 如果用户量涨 100 倍，哪里先崩　★★

- **答**（按顺序说，能连说三个就很好）：
  1. **同会话互斥锁失效** —— `agent.py:169` 的 `_session_locks` 是进程内 dict，多 worker 时锁不住，同一会话并发 run 会同时写 pending。要先换 Redis 锁。
  2. **每请求新建 Agent 图** —— `AgentFactory.create_agent` 每次都编译一遍图（`:137`），并发高时 CPU 全花在编译上。要么缓存编译结果，要么把模型/tools 组合收敛成有限几种做池化。
  3. **模型调用没有全局限流** —— 只有入口 `rate_limit(limit=10, window=60)`（`chat.py:44`，按用户维度），没有对上游模型的并发保护，打满就一起超时。
  4. **checkpoint 表无限增长** —— 正常 run 会删 thread，但中断的、异常的都留着，没有 TTL 清理任务。

### A7 前端怎么知道你"正在思考"　★★

- **答**：SSE。后端推 `{"type":"thinking","stage":...,"details":...}` 的事件帧，前端渲染成可折叠的思考过程框。
- **位置**：`chat.py:75-86`（先发占位帧）→ `agent.py:568`（thinking_callback 入队）→ `agent.py:645-651`（0.1s 轮询出队转 SSE）
- **追问**：为什么不直接把模型的 reasoning 推给前端？答：一是有些模型不给；二是工具执行阶段（`on_tool_start/end`）也想让用户看见，那是框架事件不是模型输出。

### A8 为什么用 LangChain 1.0 的 create_agent，不用旧版 AgentExecutor　★★

- **考**：是不是跟过版本演进。
- **答**：AgentExecutor 是"一个循环 + 一堆回调"，状态不可持久化、不能中断恢复；1.0 的 `create_agent` 底层是 LangGraph 编译图，状态在 checkpoint 里，这是做 HITL 的前提。
- **证据**：`agent.py:135-136` 的注释自己写了"create_agent 不提供 AgentExecutor 时代的 max_iterations / handle_parsing_errors" —— 说明对比过。

### A9 你还考虑过别的方案吗？Dify / Coze / 自己写循环　★

- **答**：Dify/Coze 这类平台的编排是配置驱动的，做不了我要的那几个东西：自定义 MySQL checkpointer、在 token 级别拦截工具调用、按会话做 run/resume 互斥。自己写 ReAct 循环（就一个 while + 手写 tool_call 解析）反而更简单，但会丢掉 checkpoint 和流式事件两套现成的能力，还得自己处理并行工具调用。

---

# 第二部分：Agent 主循环

### B1 你的 Agent 循环具体怎么跑的　★★★

- **考**：知不知道 `create_agent` 到底编出了什么。
- **答**：模型节点 → 判断有没有 tool_calls → 有就进工具节点执行 → 结果作为 ToolMessage 追加回状态 → 再回模型节点 → 没有 tool_calls 就结束。循环次数由 `ToolCallLimitMiddleware(run_limit=5)` 兜住。
- **必须做的准备**：跑一下 `get_agent().get_graph().draw_mermaid()` 把图打出来看一眼，**节点名以实际输出为准**，别背别人博客里的名字。
- **位置**：`agent.py:137`

### B2 为什么每个请求都新建一个 Agent 实例　★★★

- **考**：全局状态污染这个坑有没有踩过。
- **答**：`AgentFactory.create_agent` 每次 `create_agent` 一遍（`agent.py:130-144`），注释写的理由是"彻底避免全局状态污染" —— 比如某个请求传了 `custom_tools`，不该影响下一个请求。
- **追问（一定会来）**：那开销呢？**这题你必须承认**：每次都要重新编译图，代码里就打了 `create_agent=XXms` 的日志（`:595-596`）说明他自己在意这个数。正确答法是"这是有意的取舍，如果 QPS 上来了会改成按 (model, tools 组合, prompt 模板) 做缓存，图编译产物本身是无状态的，可以复用"。

### B3 对话历史存在哪？是 checkpointer 吗　★★★

- **考**：这题答错直接暴露没读懂 LangGraph。
- **答**：**不是**。长期历史在 MySQL 的 `chat_messages` 表（`session_manager`），每次请求重新拼成消息列表注入（`_build_chat_history`，`agent.py:194`）。checkpointer 只负责单次 run 的中断恢复和重放 —— 证据：非流式路径跑完就把 thread 删了（`:298-304`），流式路径正常完成也删（`:631-639`）。
- **一句话总结**：checkpointer 是"这一次 run 的现场"，不是"这个用户的记忆"。

### B4 那为什么还要 checkpointer？不用行不行　★★★

- **答**：三个用途：① HITL 中断后要能 `Command(resume=...)` 续上；② 防重复执行（`ALREADY_COMPLETED` 判断靠读 checkpoint 的 `pending_writes`）；③ 恢复时要能拿到原始 query（`:758-762` 从 checkpoint 里读最后一条 HumanMessage，而不是信任请求参数）。
- **追问**：不用 checkpoint 行不行？答：那中断就没法恢复，审批功能做不了。

### B5 状态（State）里存了什么　★★

- **答**：主要是 `messages`（HumanMessage / AIMessage / ToolMessage 的完整列表）。`AgentState` 是 LangGraph 的 TypedDict，`messages` 用 `add_messages` reducer 做追加合并。
- **追问**：消息会一直涨吗？**这是你项目里的真实缺口** —— 没有任何裁剪/摘要逻辑。`_build_chat_history` 把全部历史都塞进去（`:194-201`），聊久了必然爆上下文。标准答法：应该做窗口截断或摘要压缩（比如保留最近 N 轮 + 早期对话摘要），我目前没做。

### B6 怎么防止 Agent 死循环　★★★

- **答**：两层。
  1. 框架层：`ToolCallLimitMiddleware(run_limit=5)`（`agent_middleware.py:211`）
  2. 工具内层：`search_rag` 自己的护栏 `MAX_RAG_CALLS = 2`（`agent_rag_tool.py:21`）
- **加分**：说明为什么需要两层 —— `run_limit` 管的是"所有工具调用总次数"，但 RAG 一次调用内部还要跑完整的 planner + 检索 + rerank + evaluator，光限次数不够，得单独限这个最贵的工具。

### B7 run_limit 和 max_iterations 有什么区别　★★

- **答**：`max_iterations` 是旧 AgentExecutor 的**循环轮次**上限（一轮 = 模型调用 + 工具执行）；`run_limit` 是**工具调用次数**上限。一轮里模型可以并行发 3 个 tool_call，算 3 次。所以数值不能直接照搬。
- **位置**：`agent.py:135-136` 的注释

### B8 模型一次返回多个 tool_calls 会怎样　★★

- **答**：LangGraph 的工具节点会并行执行多个 tool_call（你的工具全是 `async def`，能被并发调度），结果按 tool_call_id 一一对应回填成多条 ToolMessage。
- **追问**：你代码里怎么对应上的？`_collect_steps`（`agent.py:204-222`）用 `other.tool_call_id == tool_call.get("id")` 做匹配 —— 这是非流式路径重放步骤用的。

### B9 工具执行失败会中断整个 Agent 吗　★★

- **答**：**不会**，因为每个工具自己 catch 了异常并返回错误字符串（`agent_tools.py` 里每个工具都是 `except Exception as e: return f"...出错: {e}"`）。模型看到错误文本，可以换个方式重试或直接告知用户。
- **加分**：这个设计有代价 —— 错误被吞掉，日志之外的监控看不到；而且模型可能反复重试同一个错。所以又加了 `ToolRetryMiddleware(max_retries=1)` 兜网络抖动。
- **追问**：那 raise 会怎样？答：会把异常冒出图执行，整个 run 失败，用户看到 500。

### B10 模型调用失败了怎么办　★★

- **答**：`ModelRetryMiddleware(max_retries=2)`（`agent_middleware.py:209`）做退避重试；重试还失败就抛到 `_emit_agent_events` 的 except（`agent.py:541`），转成 error 帧推给前端，不 500。

### B11 你说用 qwen3-max，代码里为什么是 gpt-4o-mini　★★★

- **考**：**这是你项目里一个真实的 bug，面试官真读代码就会问。**
- **事实**：`AgentFactory.__init__` 收了 `model="qwen3-max"` 并 `self.model = model`（`agent.py:61`），但 `_create_chat_model`（`:98-110`）用的是 `settings.OPENAI_MODEL_NAME or "gpt-4o-mini"`，**`self.model` 从头到尾没被读过**。所以 `AgentFactory(model="xxx")` 传参完全不生效，真正生效的只有环境变量。
- **答法**：主动承认，并说明这是重构时没清干净的配置项，正确的做法是 `custom_model or self.model or settings.OPENAI_MODEL_NAME`，让工厂参数优先于全局配置。

### B12 如果用本地模型 / 换个厂商，要改哪里　★

- **答**：只改 `_create_chat_model`，因为项目统一走 OpenAI 兼容协议（`utils/factory.py:create_chat_openai`），`base_url` + `api_key` 换掉就行。但要注意 `streaming=True` 和 `top_p=0.7` 是硬编码的（`agent.py:108-109`），换模型时参数要重新调。

---

# 第三部分：工具设计

### B13 你有哪些工具　★★★

- **答**：9 个，按读写分两类：
  - **只读**：`what_time_is_now`、`get_user_info_tools`、`search_notes_tool`、`get_note_stats_tool`、`get_today_reviews_tool`、`get_related_notes_tool`、`search_rag`
  - **写**：`create_note_tool`、`mark_reviewed_tool`
- **位置**：`agent_tools.py:69-81`（`_get_default_tools`）

### B14 工具粒度怎么定的？为什么不合并成"笔记管理"一个工具　★★

- **答**：粒度按"模型需要做的**决策**"切，不按"资源"切。合并成一个工具的话，模型得在参数里表达"我要查统计还是查列表"，参数空间爆炸、容易传错；拆开每个工具的语义边界清楚，description 更好写。
- **反面**：拆太细也不行 —— 工具太多模型会选错，而且每次请求都要把全部工具的 schema 塞进 prompt，token 成本线性涨。

### B15 工具太多模型会选错吗？怎么优化　★★

- **答**：9 个还在可控范围（业界的经验阈值大概在 10-20 个）。再涨就要做**工具检索**：先用 query 做一次向量召回，只把 top-k 个工具的 schema 放进 prompt。
- **加分**：LangChain 的 middleware 里就有现成的（`langchain.agents.middleware.tool_selection`），但我没启用，因为 9 个工具还不到那个量级。

### B16 工具描述（description）为什么写这么长　★★

- **考**：知不知道 description 就是 prompt。
- **答**：模型的工具选择完全靠 description 判断。所以里面要写清三件事：**做什么**、**什么时候该调**、**什么时候不该调**。
- **最好的例子是你自己的 `search_rag`**（`agent_rag_tool.py:98-102`）：
  > "仅在已有参考资料不足、需按新维度深挖、或需验证具体事实时调用；参数 query 必须是本轮尚未检索过的新聚焦角度"
  这段话直接约束了模型的调用动机，比事后限流有效。

### B17 工具怎么拿到 user_id？为什么不做成参数　★★★

- **考**：安全设计，这题答好非常加分。
- **答**：`ContextVar`（`agent_tools.py:13`）。不做成参数的原因是：**工具参数是模型生成的，模型可以被 prompt 注入诱导传别人的 user_id**。ContextVar 由服务端在请求入口 `set_current_user_id` 写入，模型的输出改不了它。
- **位置**：`agent_tools.py:16-22`，设置点在 `agent.py:574`（流式）/ `:246`（非流式）
- **追问**：ContextVar 在 async 里安全吗？答：安全，是 context-local 的，每个请求的 task 有独立副本；但要注意 `asyncio.create_task` 会拷贝上下文，新起的 task 里 set 不影响外面。

### B18 那你为什么又把 JWT 当参数传进去了　★★★

- **考**：**面试官会拿这个打你的脸**，因为和你上一题的答案自相矛盾。
- **事实**：`get_user_info_tools(token: str)`（`agent_tools.py:33`）要求模型把**完整的 JWT 字符串**作为参数传进来，然后 `decode_django_jwt(token)` 解析。
- **怎么答才对**：承认这是设计不一致。这个工具是为了回答"我的 ID 是多少"这类问题，本来完全可以从 ContextVar 拿 user_id；把 JWT 塞进模型上下文有两个问题：① token 出现在 prompt 里，可能被日志、被模型回显泄露；② 模型要"记住"一长串 token，浪费上下文还容易传错。
- **正确做法**：改成无参工具，服务端从 ContextVar 取 user_id，需要用户名就查库。

### B19 工具为什么返回给人看的格式化字符串（还带 emoji）　★★

- **考**：有没有想过 token 成本和模型可读性。
- **事实**：`get_note_stats_tool` 返回 `"📊 笔记统计\n总笔记数: 12\n💼 work: 3 篇..."`（`agent_tools.py:84-92`），其他工具也都带 emoji 和 Markdown。
- **怎么答**：承认这个不好。工具返回值是**给模型读的**，不是给终端用户看的：emoji 是无效 token，Markdown 结构对模型没帮助反而干扰；而且"人看的格式"和"模型该拿到的字段"耦合在一起，改展示就得改工具。
- **正确做法**：返回紧凑 JSON（`{"total": 12, "categories": {...}}`），让模型自己组织语言；展示层的格式交给前端或 prompt 控制。

### B20 工具返回的超长内容会不会爆上下文　★★

- **答**：会。`search_notes_tool` 每条笔记截 200 字（`agent_tools.py:69`），5 条就是 1000 字；`search_rag` 直接返回 `result.context`，而上游 evidence 拼装是 8 条 / 6000 字上限（`evidence.py:17/42`）。一次补充检索就可能吃掉几千 token。
- **可加分**：所以才有 `MAX_RAG_CALLS=2` —— 不只是控延迟，也是控上下文。

### B21 工具能不能自己调工具　★

- **答**：你的实现里不能。`search_rag` 是在工具内部直接 new 了一个 `AgenticRagService().run()`（`agent_rag_tool.py:133`），是一条独立管线，不在 Agent 的图里；它不产生新的 tool_call，所以不占 `run_limit`。
- **追问**：这样设计好不好？答：好的一面是可控（内部管线有明确终点）；坏的一面是这一层里模型看不见中间过程，只能看到最终 ToolMessage。

### B22 为什么标记已回顾（mark_reviewed_tool）不在审批白名单里　★★

- **答**：审批白名单只有 `create_note_tool`（`agent_middleware.py:82-87`）。判断标准是**误操作的代价**：建笔记会在用户数据里留下一条垃圾记录，且模板/标签会触发后台处理；标记回顾只是推后一个复习时间，点错了下一轮再点就行。
- **加分**：这说明审批不是"凡是写操作都拦"，而是按代价分级 —— 否则用户会被审批弹窗烦死，最后闭眼点同意，审批就失去意义了。

---

# 第四部分：RAG × Agent 结合

### B23 项目里为什么有两套 RAG　★★★

- **答**：
  - **前置管线**：`AgenticRagService().run()`（`chat.py:63`），在 Agent 启动前跑完，结果拼进 system prompt 的 `{context}`（`agent.py:587-590`）。作用是**保证首轮回答有依据**，不依赖模型自己想起来去查。
  - **工具式检索**：`search_rag`（`agent_rag_tool.py:103`），Agent 自己决定要不要再查、查什么角度。
- **为什么两者都要**：只做前置 → 一次检索定生死，追问细节时没料；只做工具式 → 模型可能一次都不查就开始瞎编（尤其小模型），首轮质量不可控。

### B24 前置 RAG 的结果为什么放 system prompt 而不是当 HumanMessage　★★

- **答**：放 system 是"设定背景资料"，语义上属于系统给模型的约束，不占用对话轮次；放 Human 会污染历史（下一轮 `_build_chat_history` 从 `chat_messages` 重建时不会带上它，但当前这轮的消息序列里会多一条假用户消息，模型可能误以为是用户说的）。
- **实现**：`load_prompt("rag_context_prompt").replace("{context}", rag_context)`，是模板字符串替换（`agent.py:588`）。

### B25 RAG 挂了 Agent 还能答吗　★★

- **答**：能。`run_rag` 里 `except` 返回 `None`（`chat.py:66-68`），`rag_context` 保持空字符串，Agent 用默认 system prompt 继续。设计原则是**检索失败不能阻塞回答**，降级成"没有资料的 Agent"。
- **追问**：那用户怎么知道资料没检索到？答：thinking 事件里有 RAG 阶段的错误，但**不会**明确告诉用户"这次没查到资料" —— 这是一个可以改进的点（应该给个提示，避免模型无依据硬答）。

### B26 RAG 工具的护栏为什么要限次　★★★

- **答**：一次 `search_rag` 内部是完整链路（planner → 多路召回 → RRF 融合 → rerank → evaluator → 证据拼装）。Agent 如果反复调，单次对话能从 3 秒变成 30 秒，token 成本也翻几倍。
- **位置**：`agent_rag_tool.py:21`，`MAX_RAG_CALLS = 2`

### B27 去重为什么只做字符串归一化　★★

- **答**：`normalize_query`（`agent_rag_tool.py:34-39`）去掉空白、中英文标点、转小写。这是**便宜的精确重复拦截**：模型经常换个标点就把同一个 query 再发一遍，这一步能拦住大部分无意义重试。
- **必须承认局限**：语义重复拦不住（"这篇笔记讲了什么" vs "笔记的主题是什么"）。真正要做得上 embedding 相似度阈值。**代码注释里已经写了这个 TODO**（`:36-38`），面试时主动说出来 = 你知道边界在哪。

### B28 护栏状态为什么用 ContextVar，不用实例变量　★★

- **答**：护栏是**请求级**的，不是全局的。ContextVar 随请求创建、请求结束即弃，天然隔离；如果用实例变量或者全局 dict，并发请求会互相污染计数。
- **追问**：那如果 Agent 在子 task 里调工具呢？答：`asyncio.create_task` 会复制当前 context，护栏的 dict 引用被共享，`count += 1` 仍然生效（因为同一个 dict 对象）。

### B29 工具返回的文本为什么要包 `[补充检索结果开始/结束]`　★★★

- **考**：这是你项目里最专业的一个细节，一定要会讲。
- **答**（`_format_supplementary_retrieval`，`agent_rag_tool.py:49-70`）：
  1. 用显式分隔符把"检索到的证据"和"检索状态提示"框起来，避免模型把状态提示当成证据内容；
  2. 每条状态都标 **"（非事实证据）"** —— 比如"检索已达上限""检索角度已覆盖"这些是系统提示，不是知识。不标注的话，模型很可能把"已检索过 2 次"写进回答里；
  3. 固定结构（检索角度 / 状态 / 来源概况 / 是否含外部搜索）让模型不用猜格式。

### B30 高并发下前置 RAG 会不会被拖慢　★★

- **答**：`chat.py:72` 把 RAG 放在 `asyncio.create_task` 里跑，同时主协程在等队列事件、往前端发占位帧 —— 所以用户看到"正在规划检索策略…"的时候 RAG 已经在跑了，不是串行等待。这是 TTFB 优化的关键一手。
- **代价**：如果客户端断开，`finally` 里会 `rag_task.cancel()`（`:113-115`），但 RAG 内部如果有不可取消的同步调用，取消不会立刻生效。

### B31 检索到的资料互相矛盾，Agent 怎么处理　★

- **答**：你的实现没有专门的冲突消解。能依赖的是 evaluator 给出的可答性判断（`evaluator.py:77`）和证据里带的来源/分数，模型自己权衡。
- **加分**：老实说这是 RAG 类系统的通病，正经做法是在 evidence 里带时间戳和来源权威度，让模型优先取新/权威的。

### B32 为什么 Agent 还要再检一次？前置一次不就够　★★

- **答**：前置那次用的是**原始 query**，但 Agent 走到第三步时，它已经知道了"用户真正想知道的是什么" —— 这个信息在原始 query 里可能没表达出来。比如用户问"我上次记的那个会议"，Agent 先搜笔记发现是"Q3 规划会"，这时候它该去知识库里查"Q3 规划"相关文档，而不是再搜一遍"上次记的会议"。
- **这才是 Agent 的意义**：检索 query 是被对话过程**改写**过的。

---

# 第五部分：流式输出与前端交互

### B33 流式怎么实现的　★★★

- **答**：`agent.astream_events(inputs, config, version="v2")`（`agent.py:499`），遍历事件流：
  - `on_chat_model_stream` → 取 chunk 内容，累积并转发
  - `on_tool_start` / `on_tool_end` → 发 thinking 事件（前端显示"正在调用 xx"）
  - `on_chat_model_end` → 兜底
- **为什么用 v2**：v1 的事件粒度不够，拿不到 tool_call 级别的输入输出。

### B34 为什么要过滤 tool_call_chunks　★★★

- **考**：这是流式实现里最经典的坑。
- **答**（`agent.py:504-505`）：模型流式返回时，工具调用的参数是**分片**吐出来的（`{"tool": "search_notes", "args": "{\"que` …）。这些碎片如果当正文转发，用户会看到半截 JSON 混在回答里。`chunk.tool_call_chunks` 非空就说明这个 chunk 是工具调用的参数碎片，直接 `continue`。

### B35 on_chat_model_end 那个兜底是干嘛的　★★

- **答**（`agent.py:532-536`）：不是所有模型都真流式 —— 假模型、或者某些厂商的非流式返回，根本不产生 `on_chat_model_stream` 事件，这时候 `full_response` 会是空的，用户等半天一个字都没有。所以在 `on_chat_model_end` 里检查 `if not full_response`，把整段输出取出来发一次。
- **注意**：必须加 `if not full_response` 这个条件，否则真流式的场景会把回答重复发两遍。

### B36 SSE 的帧格式是什么　★★

- **答**：`data: {json}\n\n`（两个换行是 SSE 的分帧约定）。类型有 `response`（正文增量）、`thinking`（思考过程）、`interrupt`（要审批）、`error`、`done`。
- **追问**：前端怎么判断结束？收到 `done` 或者流关闭。

### B37 thinking 事件为什么不直接 yield，要过一层队列　★★★

- **考**：这是 async generator 的经典约束。
- **答**：工具是在 Agent 图内部执行的，它的 callback 执行在**另一个 task** 里，没法直接 `yield` 到当前生成器 —— `yield` 只能在生成器自己的函数体里写。所以做法是：callback 把事件 `put` 进 `asyncio.Queue`（`:568-570`），生成器这边循环 `get` 出来 `yield`（`:645-651`）。
- **追问**：为什么用 `asyncio.wait_for(get(), timeout=0.1)` 而不是 `await queue.get()`？答：因为要同时等"队列有数据"和"agent_done 事件" —— 阻塞在 get 上的话，agent 结束了但队列空了，生成器就永远醒不过来。0.1s 是轮询换简单。
- **加分（能说出更好的写法）**：更干净的做法是 `asyncio.wait([queue.get(), done_event.wait()], return_when=FIRST_COMPLETED)`，不用轮询、没有 100ms 的空等。这里轮询的代价是最多 100ms 的延迟和一点 CPU 空转。

### B38 用户中途关掉页面，后端还在跑吗　★★

- **答**：客户端断开 → `StreamingResponse` 的生成器被 GC → `GeneratorExit` 抛出 → `agent.py:672-689` 的 except 分支 `agent_task.cancel()`。所以会停。
- **但要注意**：`finally` 里删 thread 的逻辑依赖 `agent_result_holder` 的状态，取消发生在中断处理之前的话，可能把该保留的现场删了 —— 这是并发边界的风险点，可以主动说出来。

### B39 首 token 延迟（TTFB）多少？怎么优化的　★★

- **答**：埋点就在代码里：`【Agent耗时】首token`（`agent.py:512`）、`【端到端耗时】Agent首chunk TTFB`（`chat.py:107-109`），拆成 RAG 阶段 + Agent 启动两段。
- **优化手段**（都在代码里）：
  1. 先发占位 thinking 帧，让前端立刻有反馈，不是干等一整轮 LLM（`chat.py:74-80`）
  2. RAG 和 Agent 启动不串行等（RAG 在 task 里跑，事件实时转发）
  3. `_build_chat_history` 只在需要时调用，不用额外查一次

### B40 流式过程中中断了，前端怎么知道　★★

- **答**：后端发 `{"type": "interrupt", "run_id": ..., "payload": {...}}`（`agent.py:661-664`），前端拿 run_id 渲染审批卡片，用户点同意/拒绝后调 `/chat/agent/resume`。

---

# 第六部分：Checkpointer 与状态持久化

### B41 为什么自己写 checkpointer　★★★

- **答**：官方只提供 `SqliteSaver` 和 `PostgresSaver`（`langgraph-checkpoint-*` 包），项目用的是 MySQL。自己写是移植官方的 async sqlite 版（`mysql_saver.py:1-11` 的模块注释写了出处）。
- **追问**：为什么不用 SQLite？答：生产的业务数据都在 MySQL，多进程部署时 SQLite 的单文件锁撑不住，而且备份/运维要统一。

### B42 checkpointer 实现了哪些接口　★★

- **答**：`BaseCheckpointSaver` 的四个核心方法：
  - `aget_tuple(config)` → 取最新（或指定）checkpoint + 对应的 writes
  - `alist(config)` → 按 checkpoint_id 倒序列历史
  - `aput(config, checkpoint, metadata, new_versions)` → 写 checkpoint
  - `aput_writes(config, writes, task_id)` → 写"某一步的产出"
  - 外加 `adelete_thread(thread_id)` → 删整个 thread（官方基类没强制要求，你的清理逻辑依赖它）

### B43 为什么是两张表不是一张　★★★

- **答**（`agent_checkpoints` + `agent_checkpoint_writes`）：
  - `checkpoints` 是**状态快照**（某一时刻完整的 channel_values），一个 thread 一条链，用 `parent_checkpoint_id` 串起来；
  - `writes` 是**中间写入**（某个 task 的产出，比如工具的返回值、中断信号），在 checkpoint 之后才落库 —— 这样即使进程在"节点执行完但快照还没存"的窗口里崩了，writes 还在，恢复时能重放出这一步。
- **这就是"精确一次"的基础**：先存快照，再存 writes，重放时按 task_id 对齐。

### B44 aput_writes 里那个 upsert 判断在干什么　★★★

- **考**：整个文件里最需要解释的一行。
- **答**（`mysql_saver.py:270`）：`upsert = all(w[0] in WRITES_IDX_MAP for w in writes)`。
  - `WRITES_IDX_MAP` 是 LangGraph 定义的**特殊 channel 到负索引**的映射（如 `__error__`、`__interrupt__`、`__resume__`）
  - 这批 writes 如果**全是**特殊 channel，说明是**重放**：同一个 task 重跑，要覆盖上一次的写入 → 用 `ON DUPLICATE KEY UPDATE`
  - 否则是首次写入 → 用 `INSERT IGNORE`，重复了就不写（保证幂等，不报错）
- **说人话**：**重放要覆盖，首写要忽略。** 判断依据是 channel 是不是特殊 channel。

### B45 序列化用的什么？为什么不用 pickle　★★

- **答**：`JsonPlusSerializer`（LangGraph 基类默认的 `self.serde`）。它能序列化 `BaseMessage` 这类对象，本质是把对象转成带类型标记的 JSON。用 pickle 的问题是：不可读、跨版本不安全、反序列化能执行任意代码（存到数据库里等于留了个 RCE 后门）。

### B46 方言兼容怎么做的　★★

- **答**：首次使用时探测 `session.get_bind().dialect.name` 并缓存（`_dialect_name`，`:46-54`，带 asyncio.Lock 防并发重复探测），然后按 MySQL / 其他分别返回不同的 SQL 模板（`_sql`，`:57-99`）。所以同一套代码在测试的 SQLite 和生产 MySQL 上都能跑。
- **加分**：SQL 里一律用 SQLAlchemy `text()` 的 `:name` 命名绑定，由引擎按方言编译，**不手写 `%s` 或 `?`**（模块注释里专门强调了这点）—— 这是为了同时兼容 MySQL 的 pyformat 和 SQLite 的 qmark，也顺带防了 SQL 注入。

### B47 取最新 checkpoint 靠 ORDER BY checkpoint_id DESC，可靠吗　★★

- **答**：`checkpoint_id` 是 LangGraph 生成的**时间有序** ID（UUID6，字典序 = 生成顺序），所以按字符串倒序排等于按时间倒序。这个前提必须成立，否则"取最新"会取错。
- **加分**：这是个隐含依赖 —— 如果自己改 ID 生成策略（比如换成随机 UUID4），整个 `aget_tuple` 的"取最新"逻辑就废了。

### B48 checkpoint 表会不会越来越大　★★

- **答**：会。你的清理策略是"正常 run 结束就删 thread"（`agent.py:298-304`、`:631-639`），所以正常情况下不留东西。但：
  - 中断的 run 会保留（故意的，要供审批和查看）
  - 异常退出（进程被 kill）的 thread 不会被清理 → **孤儿**
  - 覆盖策略只是"下次同会话再中断时删掉上一个"（`:613-618`），不是定时任务
- **正确答法**：应该加一个定时清理任务，按 `metadata` 里的时间戳删掉 N 天前的 thread。

### B49 存 checkpoint 有性能影响吗　★★

- **答**：有。每次图推进都写一次（模型调用后、工具执行后各一次），所以一次三步的 Agent run 至少 4-6 次数据库写。你用的是 `aput` 单条 INSERT + commit（`:241-254`），每次都开新 session。
- **可优化**：同一次 run 内的多次写入可以攒批；或者关键节点才存快照（`durability` 参数）。

---

# 第七部分：HITL 人工审批

### B50 为什么要做人工审批　★★★

- **答**：Agent 有写权限。模型幻觉时最典型的坏行为是"用户问'我有哪些笔记'，它觉得这是个好机会，主动建了三篇"。审批把不可逆的操作挡在人后面。
- **一句话**：**读操作让 Agent 自主，写操作让人拍板。**

### B51 中断是怎么实现的　★★★

- **答**：`HumanInTheLoopMiddleware(interrupt_on=approval_tools)`（`agent_middleware.py:213-219`）。模型发出 `create_note_tool` 的 tool_call 后，中间件拦截、不执行工具、在图里抛一个 `interrupt`，把待审批的 action 写进 `pending_writes` 的 `__interrupt__` 通道，整个 run 挂起，状态留在 checkpoint 里。
- **返回给前端**：`{"type": "interrupt", "run_id": ..., "payload": {"action_requests": [...]}}`

### B52 resume 怎么恢复　★★★

- **答**：`Command(resume={"decisions": decisions})` 喂回**同一个 thread_id**（`agent.py:746`），图从中断点继续，按 decision 决定执行还是跳过。
- **关键**：必须用同一个 `thread_id`，因为状态是按 thread 存的。你的实现里 `run_id` 就是 `thread_id`（`_thread_config`，`:306-308`）。

### B53 为什么 run_id 从服务端取，不让前端传　★★★

- **考**：安全 + 一致性。
- **答**：`chat.py:140-146` 注释写了"从会话 pending_run_id 取（更稳，不信任客户端）"。如果让前端传 run_id，用户可以传别人的 run_id 去审批别人的操作 —— **越权**。
- **答法**：这是"服务端持有会话状态，客户端只表达意图"的设计。

### B54 四个错误码分别是什么意思　★★★

| 码 | 触发点 | 含义 |
|---|---|---|
| `PENDING_EXISTS` | `agent.py:580-583` | 这条会话还有**未审批完**的 run，拒绝开新问题（防止两个 run 抢同一个会话状态） |
| `RESUME_MISMATCH` | `:723-725`、`:736-738` | 传的 run_id 和会话里的 pending 不一致，或者 thread 已经不存在 |
| `ALREADY_COMPLETED` | `:739-741` | 这个 run 审批完了，thread 还在（留着供查看快照），重复 resume 会二次执行工具，必须拒 |
| `RESUME_CHECK_FAILED` | `:731-735` | 检查 thread 时数据库出错 → 宁可报错也不放行（fail-closed） |

### B55 为什么审批完了 thread 不删　★★★

- **答**：要留着给用户看"审批前的快照"（`read_approval_snapshot`，`agent.py:404`，`active=False` 表示已完成）。前端可以回看"当时要建的是什么笔记、我批了还是拒了"。
- **代价**：thread 留着就占空间，所以下次同会话再中断时把上一个删掉（`:613-618`）。
- **加分**：这是个有意识的空间/功能折中，不是忘了删。

### B56 用户审批完直接刷新页面，还能看到审批记录吗　★

- **答**：能。`/chat/session/{id}/approval`（`chat.py:172-179`）走 `read_approval_snapshot`，扫描该 thread 的历史找最新的 `__interrupt__`（包括已完成的那次）。注意这个接口**不编译图**，只读 checkpoint，很轻。

### B57 审批超时了怎么办　★★★

- **考**：**这是你项目里真实缺的一块，别硬编。**
- **答**：**没做**。pending run 会一直挂着，用户不批就永远等，checkpoint 一直留着。
- **正确做法**：① pending 加 TTL（比如 30 分钟），过期自动 reject 并清理 thread；② 前端加倒计时；③ 后台定时扫描过期 pending 做兜底。
- **为什么这题重要**：面试官问"边界情况"时，能明确说出"这块我没做，因为当时优先保了主链路"比瞎编强得多。

### B58 一次要审批三个工具，怎么处理　★★

- **答**：`decisions` 是 list（`chat.py:130`），每个元素对应一个 action。`HumanInTheLoopMiddleware` 的 payload 里 `action_requests` 就是多个待审批项，可以逐个批/拒。
- **但要注意**：你的 `allowed_decisions` 只配了 `["approve", "reject"]`（`agent_middleware.py:84`），没有 `edit`（改参数后再执行）—— 那是官方支持的第三种 decision，你没开。

### B59 用户拒绝审批后，Agent 怎么继续　★★

- **答**：`reject` 的 decision 会作为 ToolMessage 回填（内容是拒绝原因），模型看到"这个操作被用户拒绝了"，可以换个方式（比如改成把内容直接贴在回答里让用户自己建）。**不会**让整个 run 失败。

### B60 多标签页同时点审批会怎样　★★

- **答**：`agent.py:709` 的 `async with _get_session_lock(...)` 会把两个 resume 串行化。第一个执行完、状态变成"已完成"，第二个进来会命中 `ALREADY_COMPLETED` 检查（`:739`）。
- **隐患**：这个锁是进程内的，多 worker 下不成立。**主动说出来。**

---

# 第八部分：并发、异常与可靠性

### B61 同一会话并发两个请求会怎样　★★★

- **答**：`_get_session_lock(user_id, session_id)`（`agent.py:169-179`）把 run 和 resume 串行化。第二个请求会等第一个结束。
- **追问（必来）**：多进程/多 worker 呢？答：**失效**。`_session_locks` 是模块级 dict，只在单进程内有效。要换 Redis 分布式锁（`SET NX PX`），或者把并发控制下移到 MySQL（行锁 / 唯一索引）。

### B62 为什么要按 (user_id, session_id) 加锁，不只按 session_id　★

- **答**：防越权。session_id 是 UUID，但理论上可能被猜到/泄露；带上 user_id 保证不同用户即使拿到同一个 session_id 也不会互相阻塞或串状态。

### B63 一个用户开两个会话，会互相影响吗　★★

- **答**：不会串状态（锁的粒度是会话），但共享：
  - `current_user_id_var` 是 ContextVar，每个请求 task 独立 → 安全
  - `rag_guard_var` 同理 → 安全
  - 全局 `_checkpointer` 单例 → 安全（无状态，只持有 session_factory）
- **反而要注意**：`set_current_user_id` 是**模块级函数改 ContextVar**（`agent_tools.py:16`），如果某个后台任务（比如 `asyncio.create_task` 起的）继承了上下文，可能拿到错误的 user_id。你的 `run_agent` 里显式 `set_current_user_id(user_id)`（`agent.py:574`）就是为了防这个。

### B64 同一个请求重发两次，会不会建两条笔记　★★★

- **考**：**幂等性，这是你项目里的真实缺口。**
- **答**：会。`create_note_tool`（`agent_tools.py:140-153`）没有幂等键，网络超时用户重试 → 两条一样的笔记。
- **正确做法**：请求入口生成 `request_id`，工具执行前先查 `(user_id, request_id)` 是否已处理；或者数据库层加唯一约束（同用户同标题同分钟）。

### B65 工具执行成功但落库失败怎么办　★★

- **答**：没专门处理。`create_note_tool` 内部 `create_note` 抛异常会 catch 成错误字符串返回给模型，模型可能重试 —— 结合上一题，这就是重复创建的来源之一。
- **更稳的做法**：工具内部用事务，成功才返回成功；失败明确返回"未创建，可重试"。

### B66 进程崩了，正在跑的 run 怎么办　★★

- **答**：状态在 checkpoint 里（每次图推进都落盘），进程重启后可以用同一个 thread_id 从最后一个 checkpoint 继续。但你的实现里**没有启动时的恢复扫描** —— 断掉的 thread 就留在表里成孤儿，用户重开会话会开新的 run。

### B67 模型一直不返回，会卡多久　★★★

- **考**：**真实缺口。**
- **答**：没有全局超时。`asyncio.wait_for(..., timeout=0.1)`（`agent.py:647`）只是轮询队列，不是给 Agent 执行设超时。模型或工具卡住，这个请求就一直挂着，占着连接和那把会话锁。
- **正确做法**：`asyncio.wait_for(agent_task, timeout=N)` 包整个 run；SSE 层再加心跳（定期发 `: ping`）让中间代理不断连。

### B68 工具超时了怎么办　★★

- **答**：没有单独设置。`ToolRetryMiddleware(max_retries=1)` 只重试，不管时长。工具内部的耗时点是数据库查询和 RAG 管线（后者可能几十秒），都没有 `asyncio.timeout` 包。

### B69 数据库连接会不会泄漏　★★

- **答**：每个工具都是 `async with AsyncSessionLocal() as db`（`agent_tools.py:56` 等），context manager 保证释放 —— 即使抛异常。checkpointer 也是同样的模式。
- **加分**：这是"工具里不能长期持有 session"的直接体现：一个 session 活太久会占连接池，Agent 循环里工具是逐个调的，用完必须还。

### B70 前端断了，后台任务会泄漏吗　★★

- **答**：`agent.py:672-689` 的 except 里 `agent_task.cancel()` + `await agent_task` 捕获 `CancelledError`，正常不会泄漏。
- **隐患**：如果是 `thinking_queue.put` 阻塞（队列无界，不会阻塞），或者 RAG 的 task 没被取消（`chat.py:113-115` 的 finally 有 cancel）—— 目前看是覆盖了的。

### B71 限流是怎么做的　★

- **答**：`rate_limit(limit=10, window=60)`（`chat.py:44`），每个用户每分钟 10 次，走 Redis（`core/rate_limit.py` + `FakeRedis` 替身）。
- **追问**：这能防模型成本被打爆吗？答：只能防单用户刷；分布式刷（多账号）防不住，需要在模型调用层做全局配额。

---

# 第九部分：性能与成本

### B72 一次对话调用几次模型　★★

- **答**：至少 3 次起：
  1. 前置 RAG 的 planner（`planner.py:165`，判断要不要检索、拆检索步）
  2. evaluator（`evaluator.py:77`，判断证据够不够答）
  3. Agent 的模型节点（可能一轮结束，也可能循环多次，每次工具调用后来一轮）
  4. 如果 Agent 调了 `search_rag`，再加 planner + evaluator 两轮
- **加分**：所以 `MAX_RAG_CALLS=2` 也间接限了模型调用次数上限（最多 ~2 + 2×2 + 工具循环）。

### B73 token 成本怎么控制　★★

- **答**（按见效排序）：
  1. 工具返回内容截断（笔记预览 200 字、工具参数日志 200 字）
  2. `MAX_RAG_CALLS=2` + `ToolCallLimitMiddleware(run_limit=5)`
  3. 历史消息……**没控制**（见 B5，这是成本大头）
  4. 前置 RAG 的 context 有 8 条 / 6000 字上限（`evidence.py`）

### B74 你的 prompt 有多长？里面有什么　★★

- **答**：`load_prompt("main_prompt")`（`agent.py:96`），从 `app/prompt/` 加载。加上 9 个工具的 schema（每个几十行 JSON）—— **工具 schema 往往比 system prompt 还长**，这是很多人忽略的成本。
- **加分**：所以工具 description 要精炼，不是越长越好（和 B16 呼应：要"该说的说清楚"，不是堆字）。

### B75 怎么降低首 token 延迟　★★

- 见 B39。补充几条：
  1. 模型换更快的（qwen-turbo 之类），代价是工具选择准确率下降
  2. 压缩历史（B5）
  3. 把前置 RAG 改成"边检索边给模型"（流式注入）—— 复杂，但能省掉整段等待
  4. 占位帧（已经做了）

### B76 上下文快满了怎么办　★★★

- **答**：目前没有处理（见 B5）。方案按复杂度：
  1. 滑动窗口：只保留最近 N 轮 + 系统提示
  2. 摘要压缩：早期对话用模型压成一段摘要
  3. 分层记忆：短期（最近几轮原文）+ 长期（存成笔记/向量，按需检索）
- **加分**：说一句"第三种其实就是把我项目里 `search_notes_tool` 那条路用起来做长期记忆，架构上已经具备条件了"。

### B77 9 个工具 schema 塞进 prompt，值得吗　★

- **答**：值得，因为工具不多（9 个）。如果涨到 30 个，就要做工具检索（B15），否则光 schema 就吃掉几千 token，而且模型选错概率上升。

---

# 第十部分：可观测性、评测与测试

### B78 线上出了问题怎么定位　★★

- **答**：三层日志：
  1. **结构化事件**：`【思考过程】stage: content`（`agent.py:569`）
  2. **耗时链路**：`【Agent耗时】`+`【端到端耗时】`，把一次请求拆成 RAG 阶段 / Agent 启动 / 首 token / 总耗时（`chat.py:92/109/112`）
  3. **中间件摘要日志**：`_messages_summary` 只打消息数量+角色序列+字符数，**不打全文**（`agent_middleware.py:94-98`）
- **这个设计值得讲**：Agent 的 messages 动辄几千字，打全文日志会把磁盘写爆，而且日志里会混进用户隐私。所以只打摘要。

### B79 有一条请求变慢了，你怎么查　★★

- **答**：先看埋点定位在哪一段：RAG 阶段慢 → 看 planner 是不是多拆了几步、rerank 是不是走了大模型；Agent 启动慢 → 看 `create_agent=XXms`；首 token 慢 → 看模型本身。
- **加分**：`model_call_hook`（`agent_middleware.py:154-176`）会把每次模型调用的耗时 + token 用量打出来，超 5 秒告警（`SLOW_MODEL_CALL_MS`）。所以能直接看出是"调了很多次"还是"某一次特别慢"。

### B80 为什么要在 middleware 里统计 token　★★

- **答**：成本核算和异常发现。`_extract_usage` 从 `usage_metadata` 取 input/output/total（`agent_middleware.py:124-136`）。如果某次调用 output token 异常大，可能是模型陷入了重复输出。
- **注意**：有些模型不返回 `usage_metadata`，代码里 `if usage is None` 就跳过（`:170`）—— 兼容性处理。

### B81 你怎么评测 Agent 好不好　★★★

- **答**（分层说）：
  1. **单测**：`tests/agent/` 2181 行，7 个文件。用 `FakeAgent`（`tests/fakes.py:129`）替身 CompiledStateGraph，`GenericFakeChatModel` 替身模型，不依赖真实模型和数据库。
  2. **集成测试**：`test_agent_stream_integration.py`（SSE 帧序）、`test_agent_rag_integration.py`（护栏逻辑）、`test_hitl_behavior.py`（四个错误码）。
  3. **离线评测**：`scripts/eval_*.py`（召回、图谱多跳、端到端）。
- **必须承认**：没有 Agent 专属的指标化评测（比如"工具选择准确率""多步任务成功率""平均工具调用次数"）。这是真缺口，说清楚比编强。

### B82 怎么测一个不确定输出的大模型　★★★

- **考**：这是 AI 工程岗位的核心题。
- **答**：**不测模型输出，测它的"行为"**。
  - `FakeAgent` 是预制事件序列（`tests/fakes.py:147-150`），测的是"编排层拿到这些事件后，SSE 帧对不对、状态对不对、有没有落库"—— 这部分是确定的。
  - HITL 的测试（`test_hitl_behavior.py`）测的是状态机：给一个"有 pending"的替身，新请求该被拒；给一个"已完成"的 thread，resume 该报 `ALREADY_COMPLETED`。
  - 真实模型的质量问题交给离线评测，不进单测（否则测试不稳定、还烧钱）。

### B83 FakeAgent 怎么替换真实 Agent 的　★★

- **答**：`agent_factory.create_agent` 是可 patch 的（模块级函数 + 依赖注入），测试里 monkeypatch 掉它返回 `FakeAgent`。这也是为什么 `create_agent` 要包一层 `AgentFactory` 而不是到处直接调 LangChain 的 —— **可测试性**。

### B84 `reset_checkpointer` 这种函数为什么要暴露出来　★

- **答**：`agent.py:162-165`，注释写了"测试用：清空全局 checkpointer 单例"。全局单例 + 测试 = 状态污染，得有个重置口子。同理 `reset_rag_guard`（`agent_rag_tool.py:29`）。

### B85 你的测试覆盖率怎么样　★★

- **答**：不知道具体数字（**不要编百分比**）。可以说"agent 目录 2181 行测试，覆盖了编排层的分支：流式三种结局（正常/中断/错误）、resume 的四个错误码、护栏的三种响应（放行/去重/超限）"。

---

# 第十一部分：压力题与反问

### B86 这个项目是你自己写的吗　★★★

- **怎么答**：不要辩解"是我写的"。**用细节证明** —— 指着一个非通用的地方讲为什么这么写。最好的三个素材：
  1. `_format_supplementary_retrieval` 里的"（非事实证据）"标注：为什么会想到这个？因为踩过模型把"检索已达上限"当事实回答的坑。
  2. `aput_writes` 的 `upsert = all(w[0] in WRITES_IDX_MAP)`：为什么会写这行？因为移植时发现"重放"和"首写"语义不同，照抄会报唯一键冲突。
  3. 四个错误码：为什么需要 `ALREADY_COMPLETED`？因为审批完 thread 不删，重复 resume 会二次执行工具（真的发生过）。

### B87 这个项目最不满意的地方是哪里　★★

- **答**（挑一个真实且有方案的）：**会话互斥锁只做了进程内**。写的时候是单进程部署，现在回头看这是最容易在多 worker 时出事的点 —— 两个 worker 会同时给一个会话写 pending_run_id，后写的覆盖先写的，用户点了审批可能恢复错 run。

### B88 如果重做，你会改什么　★★

- 按优先级说三条：
  1. 并发控制下移到 Redis/DB
  2. 历史消息做窗口 + 摘要（现在无界增长）
  3. 工具返回值改成 JSON（现在是人看的格式）
  4. 补 pending 的 TTL 和全局超时

### B89 你这个和 Dify 有什么区别　★

- **答**：Dify 是给人配工作流的，我做的是**在代码层控制 Agent 的运行时行为**：自定义 checkpointer、token 级事件拦截、按会话的 run/resume 互斥。这些在配置驱动的平台里做不了。反过来说，Dify 的运营后台、多租户、可视化调试我都没有 —— 它解决的是产品化问题，我解决的是运行时可控性。

### B90 你这个 Agent 比纯 RAG 好在哪？怎么证明　★★★

- **考**：**最致命的一题，因为大部分 RAG 项目答不出来。**
- **诚实答法**：没有做过 A/B 对比，所以不能给量化结论。但从机制上讲，纯 RAG 在一次检索后就固定了证据集，遇到需要多步的问题（"我上周那篇笔记提到的概念，和我最近看的文档有冲突吗"）没法处理；Agent 能做的是**根据中间结果改写检索 query**。
- **要有准备**：如果面试官追问"那你怎么知道值这个成本"，答"这正是我项目里 `MAX_RAG_CALLS=2` 的原因 —— 我承认它有成本，所以给最贵的那条路设了硬上限。"

### B91 反问环节你问什么　★

挑能体现你关注工程质量的：

- 你们线上 Agent 的失败率大概多少？主要失败在哪一类（工具选错 / 参数错 / 幻觉 / 超时）？
- 有没有做 Agent 的离线评测集？badcase 怎么回收成测试用例？
- 模型调用有全局限流和降级方案吗？

**别问**：加班多不多、转正率、团队多少人。

---

# 附一：6 个真实的坑（主动说出来是加分）

面试官读代码或者追问边界时，这六处会被抓到。**自己先说，性质就从"被发现缺陷"变成"我知道边界在哪"**。

| # | 位置 | 问题 | 一句话答法 |
|---|---|---|---|
| 1 | `agent.py:61` | `self.model` 赋值后从未使用，`_create_chat_model` 用的是 `settings.OPENAI_MODEL_NAME` → `AgentFactory(model=...)` 静默失效 | 重构时没清干净的配置项，正确顺序应该是 `custom_model or self.model or settings...` |
| 2 | `agent.py:169` | `_session_locks` 是进程内 dict，多 worker 下互斥失效 | 换 Redis 分布式锁，或把互斥下移到 DB |
| 3 | `agent.py:647` | `asyncio.wait_for(..., timeout=0.1)` 是队列轮询，不是 run 超时；整个 Agent 没有超时保护 | 用 `asyncio.wait([...], FIRST_COMPLETED)` 替轮询；外面包 `wait_for(agent_task, timeout=N)` |
| 4 | `agent_tools.py:140` | `create_note_tool` 无幂等键，重试会建重复笔记 | 加 request_id + 唯一约束 |
| 5 | `agent_tools.py:33` | JWT 作为模型可见参数传入，和"user_id 走 ContextVar"的原则矛盾 | 改成无参工具，从 ContextVar 取 |
| 6 | `chat.py:61` | 前置 RAG 无条件执行（`compute_route_score` 只活在测试替身里），闲聊也跑 planner | 入口加轻量路由，明显不需要检索的直接跳过 |

**额外可提**：`agent_tools.py` 各工具返回带 emoji 的 Markdown 给人看格式（B19）；历史消息无裁剪（B5）；pending 无 TTL（B57）。

---

# 附二：一页速记

**必答的 12 题（背下来）**

1. 30 秒介绍（A1）
2. 两套 RAG 的关系（B23）
3. 对话历史存哪 / checkpointer 不是记忆（B3）
4. 为什么每请求新建 Agent（B2）
5. 怎么防死循环（B6）
6. user_id 为什么走 ContextVar（B17）
7. 流式怎么实现 + 为什么过滤 tool_call_chunks（B33/B34）
8. 为什么自己写 checkpointer（B41）
9. 两张表 + WRITES_IDX_MAP 判断（B43/B44）
10. 中断/resume 的完整流程（B51/B52）
11. 四个错误码（B54）
12. 进程内锁的局限（B61）

**答辩总原则**

- 不知道就说不知道，然后给方案 —— 面试官考的是"你有没有想过"，不是"你有没有做完"。
- 每个设计都要能说出**放弃了什么**（.e.g. 每请求新建 = 牺牲编译开销换无状态）。
- 宁可说"这是我后来发现的坑"，不要说"这是教程这么写的"。

**绝对不要做的事**

- 编用户量、编 QPS、编准确率百分比
- 说"都做完了，没有遗留问题"
- 把 `AgenticRagService` 和 `app/agent/` 混为一谈（这是两条线，见 B23）
