from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    UserRegistrationView,
    MyTokenObtainPairView,
    UserProfileView
)

urlpatterns = [
    # 1. 注册接口
    path('register/', UserRegistrationView.as_view(), name='user-register'),

    # 2. 登录接口 (获取 Access Token)
    path('login/', MyTokenObtainPairView.as_view(), name='token-obtain-pair'),

    # 3. 刷新 Token 接口 (用 Refresh Token 换新的 Access Token)
    path('token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),

    # 4. 获取当前登录用户信息
    path('profile/', UserProfileView.as_view(), name='user-profile'),
]