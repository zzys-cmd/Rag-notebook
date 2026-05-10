import os
import json
from datetime import datetime

import aiofiles
from aiofiles import os as aio_os

from app.utils.config import chroma_config
from app.utils.path_tool import get_abstract_path
from app.core.logger_handler import logger


class MD5Store:
    """MD5存储管理器"""

    def __init__(self):
        self.base_dir = os.path.dirname(get_abstract_path(chroma_config['md5_hex_store']))

    def _get_md5_store_dir(self, user_id: str = None) -> str:
        """
        获取MD5存储目录
        :param user_id: 用户ID，为None时返回公共目录
        :return: MD5存储目录路径
        """
        if user_id:
            return os.path.join(self.base_dir, 'user_md5', user_id)
        else:
            return os.path.join(self.base_dir, 'public_md5')

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