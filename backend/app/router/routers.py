from typing import List
import json
import uuid

from fastapi.routing import APIRouter
from fastapi import HTTPException, UploadFile, File, Depends
from fastapi.responses import StreamingResponse
import asyncio

from app.rag.vector_store import VectorStoreService
from app.router.models import QueryRequest, RAGRequest, SessionResponse, AgentResponse, RAGResponse
from app.rag.rag_service import RagService
from app.agent.agent import get_agent_response
from app.utils.logger_handler import logger
from app.services import session_manager as sm
from app.utils.auth_utils import get_current_user_id

router = APIRouter(prefix="/api", tags=["api"])


@router.post("/agent/query", response_model=AgentResponse)
async def query_agent(request: QueryRequest, user_id: str = Depends(get_current_user_id)):
    """查询Agent"""
    try:
        # 如果没有提供session_id，自动生成一个
        session_id = request.session_id or str(uuid.uuid4())

        # 获取会话历史
        history = await sm.session_manager.get_history(session_id, user_id)

        # 获取Agent响应
        result = await get_agent_response(request.query, history)
        response = result.get("response")
        steps = result.get("steps", [])

        # 添加到会话历史
        await sm.session_manager.add_message(session_id, user_id, request.query, response)

        return AgentResponse(response=response, session_id=session_id, steps=steps)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/agent/query/stream")
async def query_stream(request: QueryRequest, user_id: str = Depends(get_current_user_id)):
    """查询Agent流式响应"""
    # 如果没有提供session_id，自动生成一个
    session_id = request.session_id or str(uuid.uuid4())
    
    async def stream_response():
        try:
            # 获取会话历史
            history = await sm.session_manager.get_history(session_id, user_id)

            # 获取Agent响应
            result = await get_agent_response(request.query, history)
            response = result.get("response")
            steps = result.get("steps", [])

            # 添加到会话历史
            await sm.session_manager.add_message(session_id, user_id, request.query, response)

            # 先发送步骤信息
            for step in steps:
                yield f"data: {json.dumps({'type': 'step', 'content': step}, ensure_ascii=False)}\n\n"
                await asyncio.sleep(0.1)

            # 发送实际响应内容
            yield f"data: {json.dumps({'type': 'response', 'content': '', 'session_id': session_id}, ensure_ascii=False)}\n\n"

            # 模拟流式输出，将响应分割成多个块
            chunk_size = 50
            for i in range(0, len(response), chunk_size):
                chunk = response[i:i+chunk_size]
                # 发送SSE格式的数据
                yield f"data: {json.dumps({'type': 'response', 'content': chunk}, ensure_ascii=False)}\n\n"
                # 模拟网络延迟
                await asyncio.sleep(0.1)

            # 发送结束标记
            yield f"data: {json.dumps({'type': 'done', 'session_id': session_id}, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error(f"查询Agent流式响应时出错: {e}")
            # 发送错误信息
            error_message = f"错误: {str(e)}"
            yield f"data: {json.dumps({'type': 'error', 'content': error_message, 'session_id': session_id}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"

    # 返回流式响应
    return StreamingResponse(
        stream_response(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
    )


@router.post("/rag/query", response_model=RAGResponse)
async def query_rag(request: RAGRequest):
    """RAG检索"""
    try:
        rag_service = RagService()
        response = await rag_service.rag_summary(request.query)
        return RAGResponse(response=response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/session/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str, user_id: str = Depends(get_current_user_id)):
    """获取会话信息，使用user_id验证"""
    try:
        # 获取会话历史，会自动验证会话属于该用户
        history = await sm.session_manager.get_history(session_id, user_id)
        return SessionResponse(session_id=session_id, history=history)
    except Exception as e:
        raise


@router.delete("/session/{session_id}")
async def delete_session(session_id: str, user_id: str = Depends(get_current_user_id)):
    """删除会话"""
    try:
        await sm.session_manager.clear_session(session_id, user_id)
        return {"message": f"Session {session_id} deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions")
async def get_all_sessions():
    """获取所有会话ID"""
    try:
        session_ids = await sm.session_manager.get_all_session_ids()
        return {"sessions": session_ids}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sessions/{user_id}")
async def get_user_sessions(user_id: str, current_user_id: str = Depends(get_current_user_id)):
    """获取用户所有会话ID"""
    try:
        # 确保用户只能获取自己的会话
        if user_id != current_user_id:
            raise HTTPException(status_code=403, detail="Forbidden")
        
        session_ids = await sm.session_manager.get_user_sessions(user_id)
        return {"sessions": session_ids}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/vector/add/single")
async def add_vector_single(file: UploadFile = File(...)):
    """上传文件，将文件保存到向量数据库，仅支持TXT和PDF"""
    try:
        # 创建向量数据库服务实例
        store = VectorStoreService()

        # 先检查文件大小，如果超出20MB，抛出异常
        max_file_size = 20 * 1024 * 1024  # 20MB
        if file.size > max_file_size:
            raise HTTPException(status_code=400, detail="文件大小不能超过20MB")

        # 检查上传的文件类型是否符合要求
        allowed_types = ('.pdf', '.txt')
        if not file.filename.endswith(allowed_types):
            raise HTTPException(status_code=400, detail="仅支持上传PDF和TXT文件")

        # 处理文件并存储到向量数据库
        await store.get_document(files=[file])

        return {"code": 200, "message": f"文件 {file.filename} 已成功上传并存储到向量数据库"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/vector/add/multiple")
async def add_vector_multiple(files: List[UploadFile] = File(..., description="要上传的文件列表，仅支持PDF和TXT格式")):
    """上传多个文件，将文件保存到向量数据库，仅支持TXT和PDF"""
    try:
        store = VectorStoreService()
        max_file_folder_size = 200 * 1024 * 1024 # 文件最大不超过200MB

        # 检查文件类型
        allowed_types = ('.pdf', '.txt')
        if not all([file.filename.endswith(allowed_types) for file in files]):
            raise HTTPException(status_code=400, detail="仅支持上传PDF和TXT文件")

        # 检查文件大小
        total_size = 0
        for file in files:
            content = await file.read()
            total_size += len(content)
            # 重置文件指针，以便后续处理
            await file.seek(0)

        if total_size > max_file_folder_size:
            raise HTTPException(status_code=400, detail="文件总大小不能超过200MB")

        await store.get_document(files=files)

        return {"code": 200, "message": f"文件 {[file.filename for file in files]} 已成功上传并存储到向量数据库"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))