from pydantic import BaseModel
from typing import List, Tuple, Optional


class QueryRequest(BaseModel):
    """查询请求模型"""
    session_id: Optional[str] = None
    query: str


class RAGRequest(BaseModel):
    """RAG检索请求模型"""
    query: str


class SessionResponse(BaseModel):
    """会话响应模型"""
    session_id: str
    history: List[Tuple[str, str]]


class AgentStep(BaseModel):
    """Agent执行步骤模型"""
    thought: Optional[str] = None
    tool: Optional[str] = None
    tool_input: Optional[dict] = None
    tool_output: Optional[str] = None


class AgentResponse(BaseModel):
    """Agent响应模型"""
    response: str
    session_id: str
    steps: Optional[List[AgentStep]] = None


class RAGResponse(BaseModel):
    """RAG检索响应模型"""
    response: str


class ReorderRequest(BaseModel):
    """重排序请求模型"""
    query: str
    documents: List[str]


class ReorderResponse(BaseModel):
    """重排序响应模型"""
    documents: List[dict]


class KnowledgeDocument(BaseModel):
    """知识库文档信息模型"""
    id: str
    filename: str
    original_filename: Optional[str] = None
    user_id: Optional[str] = None
    chunk_count: int
    preview: str
    created_at: Optional[str] = None


class KnowledgeListResponse(BaseModel):
    """知识库文档列表响应模型"""
    documents: List[KnowledgeDocument]
    total_count: int


class KnowledgeDocumentDetail(BaseModel):
    """知识库文档详情响应模型"""
    id: str
    filename: str
    user_id: Optional[str] = None
    chunk_count: int
    content: str
    created_at: Optional[str] = None


class ChunkInfo(BaseModel):
    """文档切片信息模型"""
    chunk_id: str
    index: int
    content: str
    metadata: dict


class DocumentChunksResponse(BaseModel):
    """文档切片列表响应模型"""
    filename: str
    total_chunks: int
    chunks: List[ChunkInfo]


class MD5Record(BaseModel):
    """MD5记录模型"""
    md5: str
    filename: Optional[str] = None
    original_filename: Optional[str] = None
    upload_time: Optional[str] = None


class MD5ListResponse(BaseModel):
    """MD5记录列表响应模型"""
    records: List[MD5Record]
    total_count: int