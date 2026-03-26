from abc import ABC, abstractmethod
from typing import Optional
import os
from dotenv import load_dotenv

from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel

from app.utils.config import rag_config

# 加载环境变量
load_dotenv()


class BaseModelFactory(ABC):
    """基础模型工厂"""

    @abstractmethod
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        """生成模型"""
        pass


class ChatModelFactory(BaseModelFactory):
    """聊天模型工厂"""
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        """生成模型"""
        return ChatOllama(
            model=rag_config['chat_model_name'],
            base_url="http://localhost:11434",
            temperature=0.3, # 控制输出的随机性，0-1之间，0越确定，1越随机
            num_predict=200, # 最大生成的token数
            num_thread=4,    # 并发线程数(CPU线程数)
            top_k=40,        # 考虑的token数，词汇选择范围，
            top_p=0.9,       # 考虑的token概率，控制生成的token分布，0-1之间，0越确定，1越随机
            keep_alive="5m"  # 保持连接时间，单位：分钟
        )


class EmbedModelFactory(BaseModelFactory):
    """嵌入模型工厂"""
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        """生成模型"""
        return OllamaEmbeddings(
            model=rag_config['text_embedding_model_name'],
            base_url="http://localhost:11434"
        )


chat_model = ChatModelFactory().generator()
embed_model = EmbedModelFactory().generator()