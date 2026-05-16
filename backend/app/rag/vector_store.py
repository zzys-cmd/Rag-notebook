import asyncio
import os

from langchain_chroma import Chroma
from langchain_core.documents import Document

from app.utils.config import chroma_config
from app.utils.factory import embed_model
from app.utils.path_tool import get_abstract_path
from app.core.logger_handler import logger

from .retrievers import EmptyRetriever
from .retrievers.hybrid_retriever import HybridRetriever
from .md5_manager import MD5Store
from .document_handler import DocumentProcessor


class VectorStoreService:
    """向量数据库服务"""

    def __init__(self):
        persist_dir = get_abstract_path(chroma_config['persist_directory'])
        self.vectors_store = Chroma(
            collection_name=chroma_config['collection_name'],
            embedding_function=embed_model,
            persist_directory=persist_dir,
        )

        self.md5_store = MD5Store()
        self.hybrid_retriever = HybridRetriever(self.vectors_store)
        self.document_processor = DocumentProcessor(self.vectors_store, self.md5_store)

    async def get_bm25_retriever(self, user_id: str = None):
        return await self.hybrid_retriever.get_bm25_retriever(user_id)

    async def _get_all_documents(self) -> list[Document]:
        return await self.hybrid_retriever._get_all_documents()

    async def get_retriever(self, query: str = None, user_id: str = None):
        return await self.hybrid_retriever.get_retriever(query, user_id)

    @staticmethod
    async def get_dynamic_weights(query: str = None):
        return await HybridRetriever.get_dynamic_weights(query)

    async def check_md5_hex(self, md5_for_check: str, user_id: str = None) -> bool:
        return await self.md5_store.check_md5_hex(md5_for_check, user_id)

    async def save_md5_hex(self, md5_hex: str, filename: str = None, original_filename: str = None, user_id: str = None):
        await self.md5_store.save_md5_hex(md5_hex, filename, original_filename, user_id)

    def save_md5_hex_sync(self, md5_hex: str, filename: str = None, original_filename: str = None, user_id: str = None):
        self.md5_store.save_md5_hex_sync(md5_hex, filename, original_filename, user_id)

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

            await self.md5_store.delete_user_md5(user_id)
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
            md5_to_delete = await self.md5_store.delete_by_filename(user_id, filename)
            if md5_to_delete is None:
                logger.warning(f"【向量数据库】文件 {filename} 不存在于用户 {user_id} 的MD5记录中")
                return False

            logger.info(f"【向量数据库】已删除用户 {user_id} 的文件 {filename} 的MD5记录")

            if delete_documents:
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
            success = await self.md5_store.delete_single_md5(user_id, md5_to_delete)
            if not success:
                logger.warning(f"【向量数据库】MD5记录 {md5_to_delete} 不存在")
                return False

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
            return await self.md5_store.get_md5_info(user_id, md5_value)
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
            records = await self.md5_store.get_all_md5_records(user_id)
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
        return await self.document_processor.get_file_document(read_path)

    def get_file_document_sync(self, read_path: str) -> list[Document]:
        return self.document_processor.get_file_document_sync(read_path)

    def split_documents_sync(self, documents: list[Document]) -> list[Document]:
        return self.document_processor.split_documents_sync(documents)

    async def get_document(self, files: list = None, user_id: str = None, progress_callback=None):
        await self.document_processor.get_document(files, user_id, progress_callback)


if __name__ == '__main__':
    async def main():
        store = VectorStoreService()
        await store.get_document()

        retriever = await store.get_retriever()
        results = await retriever.ainvoke('扫地')
        print(f"检索结果数量: {len(results)}")
        for result in results:
            print(result)

    asyncio.run(main())