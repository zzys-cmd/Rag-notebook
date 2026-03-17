"""
自定义加密算法
"""
import base64
import os


class StringEncryptor:
    """
    字符串加密器类
    
    提供字符串的加密和解密功能，支持中英文及特殊字符，使用Unicode码点移位结合Base64编码的方式进行加密。
    """
    
    def __init__(self, default_shift=3):
        """
        初始化加密器
        
        Args:
            default_shift (int): 默认的字符移位量，默认为3
        """
        self.default_shift = default_shift
    
    def encrypt(self, text, shift=None):
        """
        对字符串进行加密处理，支持中文和特殊字符
        
        Args:
            text (str): 要加密的字符串
            shift (int): 字符移位量，如果不提供则使用默认值
            
        Returns:
            str: 加密后的字符串
            
        Raises:
            TypeError: 当输入不是字符串类型时
        """
        if not isinstance(text, str):
            raise TypeError("输入必须是字符串类型")
        
        # 如果未提供移位量，使用默认值
        if shift is None:
            shift = self.default_shift
        
        # 对所有字符进行Unicode码点移位加密
        shifted_text = ''.join(chr((ord(char) + shift) % 0x10FFFF) for char in text)
        
        # 添加随机盐值
        salt = os.urandom(8).hex()
        text_with_salt = shifted_text + salt
        
        # Base64编码
        encoded_bytes = base64.b64encode(text_with_salt.encode('utf-8'))

        # 反转字符串以增加复杂度
        encoded_text = encoded_bytes.decode('utf-8')[::-1]
        
        return encoded_text
    
    def decrypt(self, encrypted_text, shift=None):
        """
        对加密后的字符串进行解密，支持中文和特殊字符
        
        Args:
            encrypted_text (str): 加密后的字符串
            shift (int): 字符移位量，必须与加密时使用的相同
            
        Returns:
            str: 解密后的原始字符串
            
        Raises:
            TypeError: 当输入不是字符串类型时
            ValueError: 当解密失败时
        """
        if not isinstance(encrypted_text, str):
            raise TypeError("输入必须是字符串类型")
        
        # 如果未提供移位量，使用默认值
        if shift is None:
            shift = self.default_shift
        
        try:
            # 反转字符串
            reversed_text = encrypted_text[::-1]
            
            # Base64解码
            decoded_bytes = base64.b64decode(reversed_text)
            text_with_salt = decoded_bytes.decode('utf-8')
            
            # 移除盐值
            shifted_text = text_with_salt[:-16]  # 盐值是16个字符（8字节hex编码）
            
            # 对所有字符进行Unicode码点反向移位解密
            original_text = ''.join(chr((ord(char) - shift) % 0x10FFFF) for char in shifted_text)
            
            return original_text
            
        except Exception as e:
            raise ValueError(f"解密失败: {str(e)}")
    
    def test_encryption(self):
        """
        测试加密和解密功能，包括中文和特殊字符
        
        输出测试结果到控制台
        """
        test_strings = [
            "Hello World",
            "这是一个测试字符串123!@#",
            "你好世界@#￥@@#@",
            "",
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            "中文English混合测试123!@#$%^&*()",
            "Unicode测试：😊👍✓"
        ]
        
        print("加密解密测试:")
        print("=" * 50)
        for test_str in test_strings:
            encrypted = self.encrypt(test_str)
            decrypted = self.decrypt(encrypted)
            print(f"原始字符串: {test_str}")
            print(f"加密后结果: {encrypted}")
            print(f"解密后结果: {decrypted}")
            print(f"解密是否成功: {test_str == decrypted}")
            print("-" * 50)

if __name__ == "__main__":
    # 创建加密器实例并运行测试
    encryptor = StringEncryptor()
    encryptor.test_encryption()