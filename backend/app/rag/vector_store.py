import asyncio
import sys
import os
import tempfile
import json
from datetime import datetime

from langchain_classic.retrievers import EnsembleRetriever

# 将根目录添加到系统路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import aiofiles
from aiofiles import os as aio_os

from langchain_chroma import Chroma
from langchain_core.documents import Document
from app.rag.text_spliter import AsyncTextSplitter
from langchain_community.retrievers import BM25Retriever

from app.utils.config import chroma_config
from app.utils.factory import embed_model
from app.utils.file_handler import pdf_loader, txt_loader, listdir_allowed_type, get_file_md5_hex, markdown_loader, \
    ppt_loader, word_loader, pdf_loader_sync, txt_loader_sync, markdown_loader_sync, ppt_loader_sync, word_loader_sync
from app.core.logger_handler import logger
from app.utils.path_tool import get_abstract_path

class VectorStoreService:
    """向量数据库服务"""
    def __init__(self):
        persist_dir = get_abstract_path(chroma_config['persist_directory'])
        # 使用同步 Chroma, 在调用时用 to_thread 包裹
        self.vectors_store = Chroma(
            collection_name=chroma_config['collection_name'],
            embedding_function=embed_model,
            persist_directory=persist_dir,
        )
        self.spliter = AsyncTextSplitter(
            chunk_size=chroma_config['chunk_size'],
            chunk_overlap=chroma_config['chunk_overlap'],
            separators=chroma_config['separators'],
            embedding_model=embed_model
        )

    async def get_bm25_retriever(self):
        """
        获取BM25检索器
        :return: BM25Retriever实例
        """
        # 从文件直接加载文档，不依赖向量数据库
        allowed_file_path: tuple[str] = await listdir_allowed_type(
            chroma_config['data_path'],
            tuple(chroma_config['allow_knowledge_file_types'])
        )
        file_paths = list(allowed_file_path)
        
        all_docs = []
        for file_path in file_paths:
            documents = await self.get_file_document(file_path)
            if documents:
                split_docs = await self.spliter.split_documents(documents)
                all_docs.extend(split_docs)
        
        # 创建BM25检索器
        if all_docs:
            bm25_retriever = BM25Retriever.from_documents(
                documents=all_docs,
                k=chroma_config['k']
            )
            return bm25_retriever
        else:
            return None

    async def _get_all_documents(self) -> list[Document]:
        """
        获取向量库中的所有文档
        :return: 文档列表
        """
        # 使用同步操作获取所有文档
        all_docs = await asyncio.to_thread(
            self.vectors_store.get,
            include=['documents', 'metadatas']
        )
        # 构建Document对象列表
        documents = []
        for i, doc in enumerate(all_docs['documents']):
            metadata = all_docs['metadatas'][i] if i < len(all_docs['metadatas']) else {}
            documents.append(Document(page_content=doc, metadata=metadata))
        return documents

    async def get_retriever(self, query: str = None):
        """
        获取混合检索器（BM25 + 向量检索）
        :param query: 查询语句，用于动态调整权重
        :return: EnsembleRetriever实例或单独的向量检索器
        """
        # 创建向量检索器
        vector_retriever = self.vectors_store.as_retriever(
            search_type='similarity',
            search_kwargs={'k': chroma_config['k']},
        )
        # 创建BM25检索器
        bm25_retriever = await self.get_bm25_retriever()
        
        # 根据是否有BM25检索器决定返回哪种检索器
        if bm25_retriever:
            # 获取动态权重
            weights = await self.get_dynamic_weights(query)
            # 创建混合检索器
            ensemble_retriever = EnsembleRetriever(
                retrievers=[vector_retriever, bm25_retriever],
                weights=weights
            )
            return ensemble_retriever
        else:
            # 如果没有BM25检索器，只返回向量检索器
            return vector_retriever

    @staticmethod
    async def get_dynamic_weights(query: str = None):
        """
        根据查询动态调整权重
        :param query: 查询语句
        :return: 权重列表 [向量检索权重, BM25检索权重]
        """
        # 默认权重
        default_vector_weight = 0.5
        default_bm25_weight = 0.5
        
        if not query:
            return [default_vector_weight, default_bm25_weight]
        
        # 根据查询特征调整权重
        query_length = len(query)
        query_words = len(query.split())
        
        # 长查询（>50字符）更适合向量检索
        if query_length > 50:
            vector_weight = 0.7
            bm25_weight = 0.3
        # 短查询（<20字符）更适合BM25检索
        elif query_length < 20:
            vector_weight = 0.3
            bm25_weight = 0.7
        # 中等长度查询使用默认权重
        else:
            vector_weight = default_vector_weight
            bm25_weight = default_bm25_weight
        
        # 关键词密集的查询（词数/长度比例高）更适合BM25
        if query_words > 0:
            word_density = query_words / query_length
            if word_density > 0.1:
                bm25_weight = min(bm25_weight + 0.1, 0.7)
                vector_weight = max(vector_weight - 0.1, 0.3)
        
        return [vector_weight, bm25_weight]

    async def check_md5_hex(self, md5_for_check: str, user_id: str = None) -> bool:
        """
        异步检查md5
        :param md5_for_check: 要检查的MD5值
        :param user_id: 用户ID，为None时检查公共知识库
        :return: 是否存在
        """
        md5_dir = self._get_md5_store_dir(user_id)
        md5_path = os.path.join(md5_dir, 'md5_hex_store.txt')
        
        if not await aio_os.path.exists(md5_dir):
            await aio_os.makedirs(md5_dir, exist_ok=True)
            async with aiofiles.open(md5_path, 'w', encoding="utf-8"):
                pass
            return False

        if not await aio_os.path.exists(md5_path):
            async with aiofiles.open(md5_path, 'w', encoding="utf-8"):
                pass
            return False

        try:
            async with aiofiles.open(md5_path, 'r', encoding="utf-8") as f:
                async for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith('{'):
                        try:
                            data = json.loads(line)
                            if data.get('md5') == md5_for_check:
                                return True
                        except:
                            if line == md5_for_check:
                                return True
                    else:
                        if line == md5_for_check:
                            return True
            return False
        except Exception as e:
            logger.error(f"【向量数据库】检查MD5时出错: {e}")
            return False

    async def save_md5_hex(self, md5_hex: str, filename: str = None, original_filename: str = None, user_id: str = None):
        """
        异步保存md5
        :param md5_hex: 要保存的MD5值
        :param filename: 文件名（可选）
        :param original_filename: 原始文件名（可选）
        :param user_id: 用户ID，为None时保存到公共知识库
        """
        md5_dir = self._get_md5_store_dir(user_id)
        md5_path = os.path.join(md5_dir, 'md5_hex_store.txt')
        
        if not await aio_os.path.exists(md5_dir):
            await aio_os.makedirs(md5_dir, exist_ok=True)
        
        data = {
            'md5': md5_hex,
            'filename': filename,
            'original_filename': original_filename,
            'upload_time': datetime.now().isoformat()
        }
        
        async with aiofiles.open(md5_path, 'a', encoding="utf-8") as f:
            await f.write(json.dumps(data, ensure_ascii=False) + '\n')
    
    def save_md5_hex_sync(self, md5_hex: str, filename: str = None, original_filename: str = None, user_id: str = None):
        """
        同步保存md5（用于多线程场景）
        :param md5_hex: 要保存的MD5值
        :param filename: 文件名（可选）
        :param original_filename: 原始文件名（可选）
        :param user_id: 用户ID，为None时保存到公共知识库
        """
        md5_dir = self._get_md5_store_dir(user_id)
        md5_path = os.path.join(md5_dir, 'md5_hex_store.txt')
        
        if not os.path.exists(md5_dir):
            os.makedirs(md5_dir, exist_ok=True)
        
        data = {
            'md5': md5_hex,
            'filename': filename,
            'original_filename': original_filename,
            'upload_time': datetime.now().isoformat()
        }
        
        with open(md5_path, 'a', encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + '\n')

    def _get_md5_store_dir(self, user_id: str = None) -> str:
        """
        获取MD5存储目录
        :param user_id: 用户ID，为None时返回公共目录
        :return: MD5存储目录路径
        """
        base_dir = os.path.dirname(get_abstract_path(chroma_config['md5_hex_store']))
        
        if user_id:
            return os.path.join(base_dir, 'user_md5', user_id)
        else:
            return os.path.join(base_dir, 'public_md5')

    async def delete_user_documents(self, user_id: str):
        """
        删除指定用户的所有文档（包括MD5记录）
        :param user_id: 用户ID
        """
        try:
            await self.delete_user_md5(user_id, delete_documents=True)
        except Exception as e:
            logger.error(f"【向量数据库】删除用户 {user_id} 的文档时出错: {e}")
            raise

    async def delete_user_md5(self, user_id: str, delete_documents: bool = True):
        """
        删除指定用户的MD5记录
        :param user_id: 用户ID
        :param delete_documents: 是否同时删除向量数据库中的文档（默认True）
        """
        try:
            if delete_documents:
                await asyncio.to_thread(
                    self.vectors_store.delete, 
                    where={"user_id": user_id}
                )
                logger.info(f"【向量数据库】已删除用户 {user_id} 的所有文档")
            
            md5_dir = self._get_md5_store_dir(user_id)
            md5_path = os.path.join(md5_dir, 'md5_hex_store.txt')
            
            if await aio_os.path.exists(md5_path):
                await aio_os.remove(md5_path)
                logger.info(f"【向量数据库】已删除用户 {user_id} 的MD5记录")
            
            if await aio_os.path.exists(md5_dir):
                await aio_os.rmdir(md5_dir)
        except Exception as e:
            logger.error(f"【向量数据库】删除用户 {user_id} 的MD5记录时出错: {e}")

    async def delete_by_filename(self, user_id: str, filename: str, delete_documents: bool = True):
        """
        通过文件名删除MD5记录及其对应的知识库内容
        :param user_id: 用户ID
        :param filename: 要删除的文件名
        :param delete_documents: 是否同时删除向量数据库中的对应文档（默认True）
        :return: 是否成功删除
        """
        try:
            md5_dir = self._get_md5_store_dir(user_id)
            md5_path = os.path.join(md5_dir, 'md5_hex_store.txt')
            
            if not await aio_os.path.exists(md5_path):
                logger.warning(f"【向量数据库】用户 {user_id} 的MD5文件不存在")
                return False
            
            remaining_lines = []
            found = False
            md5_to_delete = None
            
            async with aiofiles.open(md5_path, 'r', encoding="utf-8") as f:
                async for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    current_md5 = None
                    current_filename = None
                    if line.startswith('{'):
                        try:
                            data = json.loads(line)
                            current_md5 = data.get('md5')
                            current_filename = data.get('filename', data.get('original_filename'))
                        except:
                            current_md5 = line
                    else:
                        current_md5 = line
                    
                    if current_filename == filename:
                        found = True
                        md5_to_delete = current_md5
                    else:
                        remaining_lines.append(line)
            
            if not found:
                logger.warning(f"【向量数据库】文件 {filename} 不存在于用户 {user_id} 的MD5记录中")
                return False
            
            if len(remaining_lines) == 0:
                await aio_os.remove(md5_path)
                if await aio_os.path.exists(md5_dir):
                    await aio_os.rmdir(md5_dir)
            else:
                async with aiofiles.open(md5_path, 'w', encoding="utf-8") as f:
                    for line in remaining_lines:
                        await f.write(line + '\n')
            
            logger.info(f"【向量数据库】已删除用户 {user_id} 的文件 {filename} 的MD5记录")
            
            if delete_documents and md5_to_delete:
                where_clause = {"$and": [{"user_id": user_id}, {"md5": md5_to_delete}]}
                await asyncio.to_thread(
                    self.vectors_store.delete, 
                    where=where_clause
                )
                logger.info(f"【向量数据库】已删除用户 {user_id} 中文件 {filename} 对应的文档")
            
            return True
        
        except Exception as e:
            logger.error(f"【向量数据库】删除用户 {user_id} 的文件 {filename} 时出错: {e}")
            return False

    async def delete_single_md5(self, user_id: str, md5_to_delete: str, delete_documents: bool = True):
        """
        删除单个MD5记录及其对应的知识库内容
        :param user_id: 用户ID
        :param md5_to_delete: 要删除的MD5值
        :param delete_documents: 是否同时删除向量数据库中的对应文档（默认True）
        :return: 是否成功删除
        """
        try:
            md5_dir = self._get_md5_store_dir(user_id)
            md5_path = os.path.join(md5_dir, 'md5_hex_store.txt')
            
            if not await aio_os.path.exists(md5_path):
                logger.warning(f"【向量数据库】用户 {user_id} 的MD5文件不存在")
                return False
            
            remaining_lines = []
            found = False
            async with aiofiles.open(md5_path, 'r', encoding="utf-8") as f:
                async for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    current_md5 = None
                    if line.startswith('{'):
                        try:
                            data = json.loads(line)
                            current_md5 = data.get('md5')
                        except:
                            current_md5 = line
                    else:
                        current_md5 = line
                    
                    if current_md5 != md5_to_delete:
                        remaining_lines.append(line)
                    else:
                        found = True
            
            if not found:
                logger.warning(f"【向量数据库】MD5记录 {md5_to_delete} 不存在")
                return False
            
            if len(remaining_lines) == 0:
                await aio_os.remove(md5_path)
                if await aio_os.path.exists(md5_dir):
                    await aio_os.rmdir(md5_dir)
            else:
                async with aiofiles.open(md5_path, 'w', encoding="utf-8") as f:
                    for line in remaining_lines:
                        await f.write(line + '\n')
            
            logger.info(f"【向量数据库】已删除用户 {user_id} 的MD5记录: {md5_to_delete}")
            
            if delete_documents:
                where_clause = {"$and": [{"user_id": user_id}, {"md5": md5_to_delete}]}
                await asyncio.to_thread(
                    self.vectors_store.delete, 
                    where=where_clause
                )
                logger.info(f"【向量数据库】已删除用户 {user_id} 中MD5为 {md5_to_delete} 的文档")
            
            return True
        
        except Exception as e:
            logger.error(f"【向量数据库】删除用户 {user_id} 的MD5记录 {md5_to_delete} 时出错: {e}")
            return False

    async def get_md5_info(self, user_id: str, md5_value: str):
        """
        获取MD5对应的文档信息
        :param user_id: 用户ID
        :param md5_value: MD5值
        :return: MD5信息字典，不存在返回None
        """
        try:
            md5_dir = self._get_md5_store_dir(user_id)
            md5_path = os.path.join(md5_dir, 'md5_hex_store.txt')
            
            if not await aio_os.path.exists(md5_path):
                return None
            
            async with aiofiles.open(md5_path, 'r', encoding="utf-8") as f:
                async for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    if line.startswith('{'):
                        try:
                            data = json.loads(line)
                            if data.get('md5') == md5_value:
                                return data
                        except:
                            if line == md5_value:
                                return {
                                    'md5': md5_value,
                                    'filename': None,
                                    'original_filename': None,
                                    'upload_time': None
                                }
                    else:
                        if line == md5_value:
                            return {
                                'md5': md5_value,
                                'filename': None,
                                'original_filename': None,
                                'upload_time': None
                            }
            
            return None
        
        except Exception as e:
            logger.error(f"【向量数据库】获取MD5信息 {md5_value} 时出错: {e}")
            return None

    async def get_all_md5_records(self, user_id: str):
        """
        获取用户的所有MD5记录
        :param user_id: 用户ID
        :return: MD5记录列表
        """
        try:
            md5_dir = self._get_md5_store_dir(user_id)
            md5_path = os.path.join(md5_dir, 'md5_hex_store.txt')
            
            if not await aio_os.path.exists(md5_path):
                return []
            
            records = []
            async with aiofiles.open(md5_path, 'r', encoding="utf-8") as f:
                async for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    if line.startswith('{'):
                        try:
                            data = json.loads(line)
                            records.append(data)
                        except:
                            records.append({
                                'md5': line,
                                'filename': None,
                                'original_filename': None,
                                'upload_time': None
                            })
                    else:
                        records.append({
                            'md5': line,
                            'filename': None,
                            'original_filename': None,
                            'upload_time': None
                        })
            
            logger.info(f"【向量数据库】获取用户 {user_id} 的MD5记录，共 {len(records)} 条")
            return records
        
        except Exception as e:
            logger.error(f"【向量数据库】获取用户 {user_id} 的MD5记录时出错: {e}")
            return []

    async def get_user_documents(self, user_id: str = None):
        """
        获取用户的知识库文档列表
        :param user_id: 用户ID，如果为None则获取所有文档
        :return: 文档信息列表，包含文件名、文档数量、预览等信息
        """
        try:
            where_clause = {"user_id": user_id} if user_id else None
            all_docs = await asyncio.to_thread(
                self.vectors_store.get,
                include=['documents', 'metadatas'],
                where=where_clause
            )
            
            docs_info = {}
            
            for i, doc_id in enumerate(all_docs['ids']):
                metadata = all_docs['metadatas'][i] if i < len(all_docs['metadatas']) else {}
                content = all_docs['documents'][i] if i < len(all_docs['documents']) else ""
                
                filename = metadata.get('source', metadata.get('filename', 'unknown'))
                if isinstance(filename, str) and '\\' in filename:
                    filename = os.path.basename(filename)
                
                original_filename = metadata.get('original_filename', filename)
                if filename not in docs_info:
                    docs_info[filename] = {
                        'id': doc_id,
                        'filename': filename,
                        'original_filename': original_filename,
                        'user_id': metadata.get('user_id'),
                        'chunk_count': 0,
                        'preview': "",
                        'created_at': metadata.get('created_at')
                    }
                
                docs_info[filename]['chunk_count'] += 1
                
                if not docs_info[filename]['preview'] and content:
                    preview_length = 100
                    docs_info[filename]['preview'] = content[:preview_length] + ("..." if len(content) > preview_length else "")
            
            result = list(docs_info.values())
            logger.info(f"【向量数据库】获取用户 {user_id} 的知识库文档，共 {len(result)} 个文件")
            return result
        
        except Exception as e:
            logger.error(f"【向量数据库】获取用户 {user_id} 的知识库文档时出错: {e}")
            raise

    async def get_document_detail(self, user_id: str, filename: str):
        """
        获取文档的详细内容
        :param user_id: 用户ID
        :param filename: 文件名
        :return: 文档详情信息，包含完整内容
        """
        try:
            where_clause = {"user_id": user_id}
            all_docs = await asyncio.to_thread(
                self.vectors_store.get,
                include=['documents', 'metadatas'],
                where=where_clause
            )
            
            doc_info = None
            full_content = []
            chunk_count = 0
            
            for i, doc_id in enumerate(all_docs['ids']):
                metadata = all_docs['metadatas'][i] if i < len(all_docs['metadatas']) else {}
                content = all_docs['documents'][i] if i < len(all_docs['documents']) else ""
                
                source = metadata.get('source', metadata.get('filename', ''))
                if isinstance(source, str):
                    source_name = os.path.basename(source)
                else:
                    source_name = str(source)
                
                if source_name == filename:
                    if not doc_info:
                        doc_info = {
                            'id': doc_id,
                            'filename': filename,
                            'user_id': metadata.get('user_id'),
                            'chunk_count': 0,
                            'content': "",
                            'created_at': metadata.get('created_at')
                        }
                    chunk_count += 1
                    full_content.append(content)
            
            if doc_info:
                doc_info['chunk_count'] = chunk_count
                doc_info['content'] = '\n'.join(full_content)
            
            logger.info(f"【向量数据库】获取文档详情: {filename}，chunk数量: {chunk_count}")
            return doc_info
        
        except Exception as e:
            logger.error(f"【向量数据库】获取文档详情 {filename} 时出错: {e}")
            raise

    async def get_document_chunks(self, user_id: str, filename: str):
        """
        获取文档的所有切片信息
        :param user_id: 用户ID
        :param filename: 文件名
        :return: 切片列表信息
        """
        try:
            where_clause = {"user_id": user_id}
            all_docs = await asyncio.to_thread(
                self.vectors_store.get,
                include=['documents', 'metadatas'],
                where=where_clause
            )
            
            chunks = []
            chunk_index = 0
            
            for i, doc_id in enumerate(all_docs['ids']):
                metadata = all_docs['metadatas'][i] if i < len(all_docs['metadatas']) else {}
                content = all_docs['documents'][i] if i < len(all_docs['documents']) else ""
                
                source = metadata.get('source', metadata.get('filename', ''))
                if isinstance(source, str):
                    source_name = os.path.basename(source)
                else:
                    source_name = str(source)
                
                if source_name == filename:
                    chunks.append({
                        'chunk_id': doc_id,
                        'index': chunk_index,
                        'content': content,
                        'metadata': metadata
                    })
                    chunk_index += 1
            
            result = {
                'filename': filename,
                'total_chunks': len(chunks),
                'chunks': chunks
            }
            
            logger.info(f"【向量数据库】获取文档切片: {filename}，共 {len(chunks)} 个切片")
            return result
        
        except Exception as e:
            logger.error(f"【向量数据库】获取文档切片 {filename} 时出错: {e}")
            raise

    async def get_file_document(self, read_path: str) -> list[Document]:
        """异步加载文件"""
        if read_path.endswith('.txt'):
            return await txt_loader(read_path)
        elif read_path.endswith('.pdf'):
            return await pdf_loader(read_path)
        elif read_path.endswith('.md'):
            return await markdown_loader(read_path)
        elif read_path.endswith('.pptx'):
            return await ppt_loader(read_path)
        elif read_path.endswith('.docx'):
            return await word_loader(read_path)
        else:
            return []
    
    def get_file_document_sync(self, read_path: str) -> list[Document]:
        """同步加载文件（用于多线程场景）"""
        if read_path.endswith('.txt'):
            return txt_loader_sync(read_path)
        elif read_path.endswith('.pdf'):
            return pdf_loader_sync(read_path)
        elif read_path.endswith('.md'):
            return markdown_loader_sync(read_path)
        elif read_path.endswith('.pptx'):
            return ppt_loader_sync(read_path)
        elif read_path.endswith('.docx'):
            return word_loader_sync(read_path)
        else:
            return []
    
    def split_documents_sync(self, documents: list[Document]) -> list[Document]:
        """同步分割文档（用于多线程场景）"""
        return self.spliter.split_documents_sync(documents)

    async def get_document(self, files: list = None, user_id: str = None, progress_callback=None):
        """
        处理文档并将其转为向量存入向量数据库
        :param files: 上传的文件列表，如果为None则从数据文件夹读取
        :param user_id: 用户ID，用于标记文档的所有者
        :param progress_callback: 进度回调函数，用于实时返回处理进度
        """
        file_paths = []
        file_names = {}
        
        if files:
            for file in files:
                temp_file_path = await asyncio.to_thread(
                    tempfile.NamedTemporaryFile,
                    delete=False,
                    suffix=os.path.splitext(file.filename)[1]
                )
                content = await file.read()
                await asyncio.to_thread(temp_file_path.write, content)
                file_paths.append(temp_file_path.name)
                file_names[temp_file_path.name] = file.filename
        else:
            allowed_file_path: tuple[str] = await listdir_allowed_type(
                chroma_config['data_path'],
                tuple(chroma_config['allow_knowledge_file_types'])
            )
            file_paths = list(allowed_file_path)

        for idx, file_path in enumerate(file_paths):
            filename = file_names.get(file_path, os.path.basename(file_path))
            
            md5_hex = await get_file_md5_hex(file_path)
            if await self.check_md5_hex(md5_hex, user_id):
                if progress_callback:
                    await progress_callback({
                        'step': 'skipping',
                        'filename': filename,
                        'message': f'文件 {filename} 已存在，跳过'
                    })
                logger.info(f"【向量数据库】文件 {file_path} 的md5值 {md5_hex} 已存在，跳过")
                if files:
                    try:
                        os.unlink(file_path)
                    except:
                        pass
                continue

            try:
                if progress_callback:
                    await progress_callback({
                        'step': 'loading',
                        'filename': filename,
                        'message': f'正在加载文档 {filename}...'
                    })
                logger.info(f"【向量数据库】开始加载文档: {filename}")

                document: list[Document] = await self.get_file_document(file_path)
                if not document:
                    if progress_callback:
                        await progress_callback({
                            'step': 'error',
                            'filename': filename,
                            'message': f'文件 {filename} 加载内容为空，跳过',
                            'error_message': '文件内容为空'
                        })
                    logger.error(f"【向量数据库】文件 {file_path} 加载内容为空，跳过")
                    if files:
                        try:
                            os.unlink(file_path)
                        except Exception as e:
                            pass
                    continue

                if progress_callback:
                    await progress_callback({
                        'step': 'splitting',
                        'filename': filename,
                        'message': f'正在切分文档 {filename}...'
                    })
                logger.info(f"【向量数据库】开始切分文档: {filename}")

                document: list[Document] = await self.spliter.split_documents(document)
                if not document:
                    if progress_callback:
                        await progress_callback({
                            'step': 'error',
                            'filename': filename,
                            'message': f'文件 {filename} 切分内容为空，跳过',
                            'error_message': '文档切分后为空'
                        })
                    logger.error(f"【向量数据库】文件 {file_path} 切分内容为空，跳过")
                    if files:
                        try:
                            os.unlink(file_path)
                        except:
                            pass
                    continue

                if progress_callback:
                    await progress_callback({
                        'step': 'storing',
                        'filename': filename,
                        'message': f'正在存储向量 {filename}...'
                    })
                logger.info(f"【向量数据库】开始存储向量: {filename}，文档数量: {len(document)}")

                if user_id:
                    for doc in document:
                        doc.metadata['user_id'] = user_id
                
                for doc in document:
                    doc.metadata['original_filename'] = filename
                    doc.metadata['md5'] = md5_hex

                await asyncio.to_thread(self.vectors_store.add_documents, document)

                original_filename = file_names.get(file_path, filename) if files else filename
                await self.save_md5_hex(md5_hex, filename, original_filename, user_id)
                
                if progress_callback:
                    await progress_callback({
                        'step': 'completed',
                        'filename': filename,
                        'message': f'文件 {filename} 处理完成'
                    })
                logger.info(f"【向量数据库】文件 {file_path} 的md5值 {md5_hex} 已保存")

                if files:
                    try:
                        os.unlink(file_path)
                    except:
                        pass

            except Exception as e:
                if progress_callback:
                    await progress_callback({
                        'step': 'error',
                        'filename': filename,
                        'message': f'文件 {filename} 处理失败',
                        'error_message': str(e)
                    })
                logger.error(f"【向量数据库】文件 {file_path} 处理时出错: {e}")
                if files:
                    try:
                        os.unlink(file_path)
                    except:
                        pass
                continue


if __name__ == '__main__':
    async def main():
        store = VectorStoreService()
        await store.get_document()

        # 等待get_retriever方法完成
        retriever = await store.get_retriever()
        # 直接使用ainvoke方法，因为EnsembleRetriever的invoke可能返回协程
        results = await retriever.ainvoke('扫地')
        print(f"检索结果数量: {len(results)}")
        for result in results:
            print(result)

    asyncio.run(main())