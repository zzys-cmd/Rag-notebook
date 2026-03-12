import os

from langchain_classic.agents import create_tool_calling_agent, AgentExecutor
from langchain_community.chat_models import ChatTongyi
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from app.agent.agent_tools import rag_summary_tools, get_weather_tools, what_time_is_now, get_user_info_tools
from app.utils.logger_handler import logger

# 初始化聊天模型
chat_model = ChatTongyi(model="qwen3-max", api_key=os.getenv("CHAT_API_KEY"))

# 定义工具列表，放入包装后的AsyncTool实例
tools = [
    rag_summary_tools,
    get_weather_tools,
    what_time_is_now,
    get_user_info_tools
]

# 创建Agent
prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一个智能助手，能够根据用户的问题选择合适的工具来回答。请根据用户的问题，选择最合适的工具来获取信息并回答用户。"),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad")
])

# 创建工具调用Agent
agent = create_tool_calling_agent(chat_model, tools, prompt)
agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=True,
    return_intermediate_steps=True
)

async def get_agent_response(query: str, history: list = None):
    """
    获取Agent响应，支持会话历史
    :param query: 用户查询
    :param history: 会话历史，格式为[(user_msg, assistant_msg), ...]
    :return: 包含响应和步骤信息的字典
    """
    try:
        # 构建聊天历史
        chat_history = []
        if history:
            for user_msg, assistant_msg in history:
                chat_history.append(HumanMessage(content=user_msg))
                chat_history.append(AIMessage(content=assistant_msg))

        # 收集流式输出的结果
        full_response = []
        steps = []
        async for chunk in agent_executor.astream({
            "input": query,
            "chat_history": chat_history
        }):
            # 处理每个chunk
            if "output" in chunk:
                full_response.append(chunk["output"])
            elif "intermediate_steps" in chunk:
                # 处理中间步骤，展示agent的思考过程与调用的工具
                for action, observation in chunk["intermediate_steps"]:
                    logger.info(f"\n\n🧠 [Agent 思考] {action.log}")
                    logger.info(f"🛠️ [调用工具] {action.tool}")
                    logger.info(f"📥 [工具输入] {action.tool_input}")
                    logger.info(f"📤 [工具结果] {observation}\n")

                    # 收集步骤信息
                    step = {
                        "thought": action.log,
                        "tool": action.tool,
                        "tool_input": action.tool_input,
                        "tool_output": observation
                    }
                    steps.append(step)

        # 返回完整响应和步骤信息
        return {
            "response": "".join(full_response) if full_response else "抱歉，我无法理解您的请求。",
            "steps": steps
        }
    except Exception as e:
        return {
            "response": f"抱歉，处理您的请求时出现了错误: {str(e)}",
            "steps": []
        }