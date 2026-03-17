from langchain_core.tools import tool

from app.rag.rag_service import RagService
from app.utils.auth_utils import decode_django_jwt

import datetime

@tool(description="用于从向量数据库里检索文档并生成摘要")
async def rag_summary_tools(query: str) -> str:
    """RAG 摘要工具"""
    return await RagService().rag_summary(query)

@tool(description="从JWT中获取当前用户信息，参数为完整的JWT token字符串")
async def get_user_info_tools(token: str) -> str:
    """获取用户信息工具"""
    payload = decode_django_jwt(token)
    if payload:
        user_id = payload.get("user_id", "未知")
        user_name = payload.get("user_name", "未知")
        return f"用户信息：\n- 用户ID: {user_id}\n- 用户名: {user_name}"
    else:
        return "无法解析JWT token，无法获取用户信息"


@tool(description="用于获取天气信息，需要提供城市名称作为参数，你需要从用户输入中提取城市名称，是str类型")
async def get_weather_tools(city: str = None) -> str:
    """获取天气工具"""
    if not city:
        return "请提供城市名称"
    return f"【{city}】的天气是晴朗的"


@tool(description="用于获取当前年月日时分的工具")
async def what_time_is_now() -> str:
    """获取当前年月日时分的工具"""
    return f"当前时间是：{datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}"