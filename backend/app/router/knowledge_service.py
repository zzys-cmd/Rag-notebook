import asyncio
import time
import json
from typing import List, Optional, Dict, Any, AsyncGenerator
import uuid
import magic
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor

from fastapi import HTTPException, UploadFile

from app.core.logger_handler import logger
from app.rag.vector_store import VectorStoreService
from app.rag.task_queue import TaskQueue, SliceResult


class KnowledgeService:
    """知识库管理服务"""

    async def handle_add_vector_single(self, file: UploadFile, user_id: str) -> str:
        """处理添加单个向量逻辑"""
        store = VectorStoreService()

        max_file_size = 20 * 1024 * 1024
        if file.size > max_file_size:
            raise HTTPException(status_code=400, detail="文件大小不能超过20MB")

        content = await file.read()
        await file.seek(0)

        mime = magic.Magic(mime=True)
        file_type = mime.from_buffer(content)

        file_extension = os.path.splitext(file.filename)[1].lower()
        allowed_extensions = {'.pdf', '.txt', '.md', '.pptx', '.docx'}

        allowed_mime_types = {'application/pdf', 'text/plain', 'text/markdown', 'application/vnd.ms-powerpoint', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}
        if file_type not in allowed_mime_types and file_extension not in allowed_extensions:
            raise HTTPException(status_code=400, detail=f"文件类型不支持，目前支持PDF、TXT、Markdown、PPTX、DOCX文件类型。检测到的文件类型: {file_type}，扩展名: {file_extension}")

        await store.get_document(files=[file], user_id=user_id)

        return file.filename

    async def handle_add_vector_multiple(self, files: List[UploadFile], user_id: str) -> List[str]:
        """处理添加多个向量逻辑"""
        max_file_folder_size = 200 * 1024 * 1024

        total_size = 0
        allowed_mime_types = {'application/pdf', 'text/plain', 'text/markdown', 'application/vnd.ms-powerpoint', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}
        mime = magic.Magic(mime=True)

        for file in files:
            content = await file.read()
            total_size += len(content)

            file_type = mime.from_buffer(content)
            file_extension = os.path.splitext(file.filename)[1].lower()
            allowed_extensions = {'.pdf', '.txt', '.md', '.pptx', '.docx'}
            if file_type not in allowed_mime_types and file_extension not in allowed_extensions:
                raise HTTPException(status_code=400, detail=f"文件 {file.filename} 类型不支持，目前支持PDF、TXT、Markdown、PPTX、DOCX文件类型。检测到的文件类型: {file_type}，扩展名: {file_extension}")

            await file.seek(0)

        if total_size > max_file_folder_size:
            raise HTTPException(status_code=400, detail="文件总大小不能超过200MB")

        start_time = time.time()

        store = VectorStoreService()

        async def process_file(file):
            await store.get_document(files=[file], user_id=user_id)
            return file.filename

        results = await asyncio.gather(*[process_file(file) for file in files])

        end_time = time.time()
        logger.info(f"【添加向量】耗时: {end_time - start_time:.2f}秒，处理文件数: {len(results)}")

        return results

    async def handle_add_vector_multiple_stream(
            self,
            files: List[UploadFile],
            user_id: str
    ) -> AsyncGenerator[str, None]:
        """
        处理多个文件上传并返回流式进度（多线程切片 + 单线程串行写入）
        """
        total_files = len(files)
        success_count = 0
        failed_count = 0

        logger.info(f"【SSE上传】开始处理文件上传，文件数量: {total_files}，用户ID: {user_id}")

        yield f"event: progress\ndata: {json.dumps({
            'event_type': 'start',
            'total_files': total_files,
            'message': '开始处理文件...',
            'progress': 0
        })}\n\n"

        max_file_folder_size = 200 * 1024 * 1024
        total_size = 0
        files_content = []

        for file in files:
            content = await file.read()
            files_content.append({'file': file, 'content': content})
            total_size += len(content)
            await file.seek(0)

        if total_size > max_file_folder_size:
            logger.error(f"【SSE上传】文件总大小超过限制，总大小: {total_size / (1024 * 1024):.2f}MB，限制: 200MB")
            yield f"event: progress\ndata: {json.dumps({
                'event_type': 'error',
                'message': '文件总大小不能超过200MB',
                'error_message': '文件总大小不能超过200MB'
            })}\n\n"
            return

        allowed_mime_types = {'application/pdf', 'text/plain', 'text/markdown',
                            'application/vnd.ms-powerpoint',
                            'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}
        mime = magic.Magic(mime=True)

        valid_files_info = []
        current_index = 1

        for file_info in files_content:
            file = file_info['file']
            content = file_info['content']
            file_type = mime.from_buffer(content)
            file_extension = os.path.splitext(file.filename)[1].lower()
            allowed_extensions = {'.pdf', '.txt', '.md', '.pptx', '.docx'}

            if file_type not in allowed_mime_types and file_extension not in allowed_extensions:
                failed_count += 1
                logger.warning(f"【SSE上传】文件类型验证失败: {file.filename}，检测到类型: {file_type}，扩展名: {file_extension}")
                yield f"event: progress\ndata: {json.dumps({
                    'event_type': 'error',
                    'file_index': current_index,
                    'total_files': total_files,
                    'filename': file.filename,
                    'step': 'validation',
                    'message': f'文件 {file.filename} 类型不支持',
                    'error_message': f'文件类型: {file_type}，扩展名: {file_extension}',
                    'progress': int(current_index / total_files * 100),
                    'success_count': success_count,
                    'failed_count': failed_count
                })}\n\n"
            else:
                valid_files_info.append({
                    'content': content,
                    'filename': file.filename,
                    'file_index': current_index
                })
                logger.debug(f"【SSE上传】文件类型验证通过: {file.filename}")
            current_index += 1

        start_time = time.time()

        slice_queue = TaskQueue(maxsize=10)
        slice_queue.set_total_count(len(valid_files_info))

        sliced_count = 0
        written_count = 0
        slice_success_count = 0

        def sync_slice_file(file_content: bytes, filename: str, file_index: int, user_id: str):
            from app.rag.vector_store import VectorStoreService
            from app.utils.file_handler import get_file_md5_hex_sync

            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as temp_file:
                    temp_file.write(file_content)
                    temp_file_path = temp_file.name

                try:
                    store = VectorStoreService()

                    documents = store.get_file_document_sync(temp_file_path)
                    if not documents:
                        slice_queue.put(SliceResult.error_result(
                            file_index=file_index,
                            filename=filename,
                            error="文件加载为空"
                        ))
                        return

                    split_docs = store.split_documents_sync(documents)
                    if not split_docs:
                        slice_queue.put(SliceResult.error_result(
                            file_index=file_index,
                            filename=filename,
                            error="切片结果为空"
                        ))
                        return

                    md5_hex = get_file_md5_hex_sync(temp_file_path)

                    for doc in split_docs:
                        doc.metadata['user_id'] = user_id
                        doc.metadata['original_filename'] = filename
                        doc.metadata['md5'] = md5_hex

                    slice_queue.put(SliceResult.success_result(
                        file_index=file_index,
                        filename=filename,
                        documents=split_docs,
                        md5=md5_hex
                    ))

                finally:
                    if os.path.exists(temp_file_path):
                        os.unlink(temp_file_path)

            except Exception as e:
                logger.error(f"【SSE上传】切片文件 {filename} 时出错: {e}")
                slice_queue.put(SliceResult.error_result(
                    file_index=file_index,
                    filename=filename,
                    error=str(e)
                ))

        slice_tasks = []
        for info in valid_files_info:
            slice_tasks.append((info['content'], info['filename'], info['file_index'], user_id))

        slice_workers = min(len(slice_tasks), 4)
        logger.info(f"【SSE上传】切片阶段使用 {slice_workers} 个线程")

        write_store = VectorStoreService()

        executor = ThreadPoolExecutor(max_workers=slice_workers)
        futures = [executor.submit(sync_slice_file, *args) for args in slice_tasks]

        while written_count < len(valid_files_info):
            try:
                result = slice_queue.get(block=True, timeout=0.1)

                sliced_count += 1

                if result.success:
                    slice_success_count += 1

                    yield f"event: progress\ndata: {json.dumps({
                        'event_type': 'slicing_completed',
                        'file_index': result.file_index,
                        'total_files': total_files,
                        'filename': result.filename,
                        'chunk_count': result.chunk_count,
                        'step': 'slicing',
                        'message': f'文件 {result.filename} 切片完成，共 {result.chunk_count} 个切片',
                        'progress': self._calculate_progress(sliced_count, written_count, len(valid_files_info)),
                        'success_count': success_count,
                        'failed_count': failed_count,
                        'slice_success_count': slice_success_count
                    })}\n\n"

                    try:
                        yield f"event: progress\ndata: {json.dumps({
                            'event_type': 'writing',
                            'file_index': result.file_index,
                            'total_files': total_files,
                            'filename': result.filename,
                            'step': 'writing',
                            'message': f'正在写入向量 {result.filename}...',
                            'progress': self._calculate_progress(sliced_count, written_count, len(valid_files_info)),
                            'success_count': success_count,
                            'failed_count': failed_count,
                            'slice_success_count': slice_success_count
                        })}\n\n"

                        await asyncio.to_thread(write_store.vectors_store.add_documents, result.documents)

                        await write_store.save_md5_hex(result.md5, result.filename, result.filename, user_id)

                        success_count += 1
                        written_count += 1

                        yield f"event: progress\ndata: {json.dumps({
                            'event_type': 'completed',
                            'file_index': result.file_index,
                            'total_files': total_files,
                            'filename': result.filename,
                            'step': 'completed',
                            'message': f'文件 {result.filename} 处理完成',
                            'progress': self._calculate_progress(sliced_count, written_count, len(valid_files_info)),
                            'success_count': success_count,
                            'failed_count': failed_count,
                            'slice_success_count': slice_success_count
                        })}\n\n"

                        logger.info(f"【SSE上传】文件 {result.filename} 写入完成")

                    except Exception as e:
                        written_count += 1
                        failed_count += 1
                        logger.error(f"【SSE上传】写入文件 {result.filename} 时出错: {e}")

                        yield f"event: progress\ndata: {json.dumps({
                            'event_type': 'error',
                            'file_index': result.file_index,
                            'total_files': total_files,
                            'filename': result.filename,
                            'step': 'writing',
                            'message': f'文件 {result.filename} 写入失败',
                            'error_message': str(e),
                            'progress': self._calculate_progress(sliced_count, written_count, len(valid_files_info)),
                            'success_count': success_count,
                            'failed_count': failed_count,
                            'slice_success_count': slice_success_count
                        })}\n\n"

                else:
                    written_count += 1
                    failed_count += 1
                    logger.error(f"【SSE上传】切片文件 {result.filename} 失败: {result.error}")

                    yield f"event: progress\ndata: {json.dumps({
                        'event_type': 'error',
                        'file_index': result.file_index,
                        'total_files': total_files,
                        'filename': result.filename,
                        'step': 'slicing',
                        'message': f'文件 {result.filename} 切片失败',
                        'error_message': result.error,
                        'progress': self._calculate_progress(sliced_count, written_count, len(valid_files_info)),
                        'success_count': success_count,
                        'failed_count': failed_count,
                        'slice_success_count': slice_success_count
                    })}\n\n"

                slice_queue.task_done()

            except Exception:
                continue

        executor.shutdown(wait=True)

        end_time = time.time()
        total_time = round(end_time - start_time, 2)

        logger.info(f"【SSE上传】文件处理完成，总数: {total_files}，成功: {success_count}，失败: {failed_count}，耗时: {total_time}秒，切片并发数: {slice_workers}")

        yield f"event: progress\ndata: {json.dumps({
            'event_type': 'finish',
            'total_files': total_files,
            'success_count': success_count,
            'failed_count': failed_count,
            'message': f'处理完成，耗时 {total_time} 秒',
            'progress': 100
        })}\n\n"

    def _calculate_progress(self, sliced_count: int, written_count: int, total: int) -> int:
        if total == 0:
            return 0

        slice_progress = (sliced_count / total) * 60
        write_progress = (written_count / total) * 40

        return int(min(99, slice_progress + write_progress))

    async def clean_user_upload(self, user_id: str) -> None:
        """处理删除用户上传的所有向量逻辑"""
        store = VectorStoreService()
        await store.delete_user_documents(user_id)

    async def handle_clear_user_md5(self, user_id: str, delete_documents: bool = True) -> None:
        store = VectorStoreService()
        await store.delete_user_md5(user_id, delete_documents)
        if delete_documents:
            logger.info(f"【知识库】清空用户 {user_id} 的MD5记录和文档")
        else:
            logger.info(f"【知识库】仅清空用户 {user_id} 的MD5记录")

    async def handle_delete_single_md5(self, user_id: str, md5_value: str, delete_documents: bool = True) -> bool:
        store = VectorStoreService()
        success = await store.delete_single_md5(user_id, md5_value, delete_documents)
        if success:
            logger.info(f"【知识库】删除用户 {user_id} 的MD5记录: {md5_value}")
        else:
            logger.warning(f"【知识库】删除用户 {user_id} 的MD5记录失败: {md5_value}")
        return success

    async def handle_delete_by_filename(self, user_id: str, filename: str, delete_documents: bool = True) -> bool:
        store = VectorStoreService()
        success = await store.delete_by_filename(user_id, filename, delete_documents)
        if success:
            logger.info(f"【知识库】删除用户 {user_id} 的文件: {filename}")
        else:
            logger.warning(f"【知识库】删除用户 {user_id} 的文件失败: {filename}")
        return success

    async def handle_get_md5_info(self, user_id: str, md5_value: str):
        store = VectorStoreService()
        return await store.get_md5_info(user_id, md5_value)

    async def handle_get_all_md5_records(self, user_id: str):
        store = VectorStoreService()
        return await store.get_all_md5_records(user_id)

    async def handle_get_user_knowledge(self, user_id: str) -> list:
        store = VectorStoreService()
        documents = await store.get_user_documents(user_id)
        logger.info(f"【知识库】获取用户 {user_id} 的知识库文档，共 {len(documents)} 个文件")
        return documents

    async def handle_get_document_detail(self, user_id: str, filename: str) -> dict:
        store = VectorStoreService()
        document = await store.get_document_detail(user_id, filename)
        if not document:
            raise HTTPException(status_code=404, detail=f"文档 {filename} 不存在")
        logger.info(f"【知识库】获取文档详情: {filename}")
        return document

    async def handle_get_document_chunks(self, user_id: str, filename: str) -> dict:
        store = VectorStoreService()
        chunks = await store.get_document_chunks(user_id, filename)
        if chunks['total_chunks'] == 0:
            raise HTTPException(status_code=404, detail=f"文档 {filename} 不存在或没有切片")
        logger.info(f"【知识库】获取文档切片: {filename}，共 {chunks['total_chunks']} 个切片")
        return chunks


def get_knowledge_service() -> KnowledgeService:
    """获取知识库服务实例（用于依赖注入）"""
    return KnowledgeService()