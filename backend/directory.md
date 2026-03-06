后端目录结构
backend/
├── app/                      # 主应用目录
│   ├── api/                  # API路由
│   │   ├── __init__.py
│   │   ├── agent.py          # Agent相关接口
│   │   ├── rag.py            # RAG相关接口
│   │   └── routes.py         # 路由汇总
│   ├── agent/                # Agent核心模块
│   │   ├── __init__.py
│   │   ├── base.py           # Agent基类
│   │   ├── tools.py          # Agent工具
│   │   └── memory.py         # Agent记忆管理
│   ├── rag/                  # RAG核心模块
│   │   ├── __init__.py
│   │   ├── retriever.py      # 检索器
│   │   ├── vector_store.py   # 向量存储
│   │   └── document_processor.py  # 文档处理
│   ├── services/             # 服务层
│   │   ├── __init__.py
│   │   ├── llm_service.py    # LLM服务
│   │   └── embedding_service.py  # 嵌入服务
│   ├── config/               # 配置
│   │   ├── __init__.py
│   │   └── settings.py       # 应用设置
│   └── utils/                # 工具函数
│       ├── __init__.py
│       └── helpers.py        # 辅助函数
├── data/                     # 数据目录
│   ├── documents/            # 原始文档
│   └── vector_db/            # 向量数据库
├── scripts/                  # 脚本
│   ├── ingest_data.py        # 数据摄入脚本
│   └── init_vector_db.py     # 向量数据库初始化
├── tests/                    # 测试
│   ├── __init__.py
│   ├── test_agent.py         # Agent测试
│   └── test_rag.py           # RAG测试
├── .env                      # 环境变量
├── main.py                   # 应用入口
├── requirements.txt          # 依赖
└── README.md                 # 项目说明
