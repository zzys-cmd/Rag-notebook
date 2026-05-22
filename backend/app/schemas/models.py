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


class ChunkDetail(BaseModel):
    """
    文档切片详情（含对应图片）。
    images 字段保存该切片所涉及的所有图片URL，前端可据此在切片旁边展示图片。
    """
    chunk_id: str
    index: int
    content: str
    page: Optional[int] = None
    images: list[str] = []


class KnowledgeDocumentDetail(BaseModel):
    """
    知识库文档详情响应模型。
    相比旧版本新增了 chunks（切片级详情，包含每段文本对应的图片）和 images（文档全量图片列表）字段，
    前端可以在文档详情页同时展示文本和图片。
    """
    id: str
    filename: str
    user_id: Optional[str] = None
    chunk_count: int
    content: str
    chunks: list[ChunkDetail] = []
    images: list[str] = []
    created_at: Optional[str] = None


class ChunkInfo(BaseModel):
    """
    文档切片信息模型。
    images 字段保存该切片关联的图片URL，前端在"查看切片"页面中可以按切片展示对应的图片。
    """
    chunk_id: str
    index: int
    content: str
    metadata: dict
    images: list[str] = []


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


class NoteCreate(BaseModel):
    """创建笔记请求模型"""
    title: str
    content: str


class NoteUpdate(BaseModel):
    """更新笔记请求模型（所有字段可选）"""
    title: Optional[str] = None
    content: Optional[str] = None


class NoteResponse(BaseModel):
    """笔记响应模型"""
    id: str
    user_id: str
    title: str
    content: str
    tags: Optional[List[str]] = None
    category: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class NoteListResponse(BaseModel):
    """笔记列表响应模型"""
    notes: List[NoteResponse]
    total_count: int


class NoteSearchRequest(BaseModel):
    """笔记搜索请求模型"""
    query: str


class RelatedNoteItem(BaseModel):
    """关联笔记项模型"""
    id: str
    title: str
    content_preview: str
    similarity: float
    source: str  # 来源：knowledge_base 或 note


class RelatedNotesResponse(BaseModel):
    """关联笔记列表响应模型"""
    notes: List[RelatedNoteItem]


class PageRequest(BaseModel):
    """分页请求模型"""
    page: int = 1
    page_size: int = 20
    category: Optional[str] = None
    tag: Optional[str] = None