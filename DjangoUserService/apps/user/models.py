import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    """
    自定义用户模型
    核心联调字段：uuid (作为对外的唯一用户ID)
    """
    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        db_index=True,
        verbose_name="全局用户ID"
    )

    user_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="用户名"
    )

    # 扩展字段：手机号
    phone = models.CharField(
        max_length=11,
        unique=True,
        null=True,
        blank=True,
        verbose_name="手机号"
    )

    # 扩展字段：头像
    avatar = models.ImageField(
        upload_to='avatars/%Y/%m/%d/',
        null=True,
        blank=True,
        verbose_name="头像"
    )

    # 审计字段
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="注册时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        db_table = 'auth_users'
        verbose_name = "用户"
        verbose_name_plural = "用户"

    def __str__(self):
        return f"{self.user_name} ({self.uuid})"
