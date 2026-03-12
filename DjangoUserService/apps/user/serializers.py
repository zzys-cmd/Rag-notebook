from rest_framework import serializers
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()

class UserRegistrationSerializer(serializers.ModelSerializer):
    """用户注册序列化器"""
    password = serializers.CharField(write_only=True, required=True, min_length=6)
    password2 = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ('user_name', 'email', 'password', 'password2', 'phone')

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "两次密码不一致"})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password2')
        # 确保提供 username 字段，使用 user_name 或 email 作为 username
        if 'username' not in validated_data:
            validated_data['username'] = validated_data.get('user_name', validated_data.get('email', ''))
        user = User.objects.create_user(**validated_data)
        return user

class UserInfoSerializer(serializers.ModelSerializer):
    """返回给前端或 FastAPI 侧的用户信息"""
    # 显式指定 user_id 为 uuid
    user_id = serializers.CharField(source='uuid', read_only=True)
    class Meta:
        model = User
        fields = ('user_id', 'user_name', 'email', 'avatar', 'date_joined')

class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    自定义 JWT 返回内容
    可以在这里添加 FastAPI 可能需要的额外信息
    """
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # 往 Token 里加一些自定义的公开信息
        token['user_name'] = user.user_name
        token['user_id'] = str(user.uuid)
        return token