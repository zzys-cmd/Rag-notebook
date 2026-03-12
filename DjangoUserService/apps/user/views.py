from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth import get_user_model

from .serializers import (
    UserRegistrationSerializer,
    UserInfoSerializer,
    MyTokenObtainPairSerializer
)

User = get_user_model()

class UserRegistrationView(generics.CreateAPIView):
    """注册接口"""
    queryset = User.objects.all()
    permission_classes = (AllowAny,)
    serializer_class = UserRegistrationSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # 注册成功后，自动返回用户信息
        return Response({
            "message": "注册成功",
            "user": UserInfoSerializer(user, context=self.get_serializer_context()).data
        }, status=status.HTTP_201_CREATED)

class MyTokenObtainPairView(TokenObtainPairView):
    """
    登录接口：获取 Token
    返回: refresh, access
    refresh: 刷新 Token，续期access
    access: 访问 Token，用于调用需要认证的接口
    """
    serializer_class = MyTokenObtainPairSerializer

class UserProfileView(generics.RetrieveAPIView):
    """
    获取当前登录用户信息
    供 FastAPI 服务内部调用
    """
    permission_classes = (IsAuthenticated,)
    serializer_class = UserInfoSerializer

    def get_object(self):
        return self.request.user