# Django User Service API 文档

## 项目简介

Django User Service 是一个基于 Django 和 Django REST Framework 开发的用户管理服务，提供用户注册、登录、获取用户信息等功能，并使用 JWT 进行身份认证。

## 接口列表

| 接口路径 | 方法 | 功能描述 |
|---------|------|--------|
| `/api/auth/register/` | POST | 用户注册 |
| `/api/auth/login/` | POST | 用户登录（获取 Access Token） |
| `/api/auth/token/refresh/` | POST | 刷新 Token（用 Refresh Token 换新的 Access Token） |
| `/api/auth/profile/` | GET | 获取当前登录用户信息 |

## 详细接口说明

### 1. 用户注册

**URL:** `/api/auth/register/`  
**方法:** POST  
**描述:** 创建新用户

**请求参数:**

| 参数名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| `user_name` | string | 是 | 用户名 |
| `email` | string | 是 | 邮箱地址 |
| `password` | string | 是 | 密码（至少6位） |
| `password2` | string | 是 | 确认密码 |
| `phone` | string | 否 | 手机号（11位） |

**请求示例:**
```json
{
  "user_name": "张三",
  "email": "zhangsan@example.com",
  "password": "123456",
  "password2": "123456",
  "phone": "13800138000"
}
```

**响应示例:**
```json
{
  "message": "注册成功",
  "user": {
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "user_name": "张三",
    "email": "zhangsan@example.com",
    "avatar": null,
    "date_joined": "2026-03-12T10:00:00Z"
  }
}
```

### 2. 用户登录

**URL:** `/api/auth/login/`  
**方法:** POST  
**描述:** 用户登录并获取 JWT Token

**请求参数:**

| 参数名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| `username` | string | 是 | 用户名或邮箱 |
| `password` | string | 是 | 密码 |

**请求示例:**
```json
{
  "username": "zhangsan@example.com",
  "password": "123456"
}
```

**响应示例:**
```json
{
  "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user_name": "张三",
  "user_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### 3. 刷新 Token

**URL:** `/api/auth/token/refresh/`  
**方法:** POST  
**描述:** 使用 Refresh Token 获取新的 Access Token

**请求参数:**

| 参数名 | 类型 | 必填 | 描述 |
|--------|------|------|------|
| `refresh` | string | 是 | 从登录接口获取的 Refresh Token |

**请求示例:**
```json
{
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**响应示例:**
```json
{
  "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

### 4. 获取当前登录用户信息

**URL:** `/api/auth/profile/`  
**方法:** GET  
**描述:** 获取当前登录用户的详细信息

**请求头:**

| 头部名称 | 值 | 描述 |
|---------|-----|------|
| `Authorization` | `Bearer <access_token>` | 使用登录接口获取的 Access Token |

**响应示例:**
```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_name": "张三",
  "email": "zhangsan@example.com",
  "avatar": null,
  "date_joined": "2026-03-12T10:00:00Z"
}
```

## 认证方式

本服务使用 JWT（JSON Web Token）进行身份认证。用户登录后获取 Access Token 和 Refresh Token：

- **Access Token**：用于访问需要认证的接口，有效期为 2 小时
- **Refresh Token**：用于在 Access Token 过期后获取新的 Access Token，有效期为 7 天

在访问需要认证的接口时，需要在请求头中添加 `Authorization: Bearer <access_token>`。

## 错误处理

| 错误码 | 描述 |
|--------|------|
| 400 | 请求参数错误 |
| 401 | 未授权或 Token 无效 |
| 403 | 禁止访问 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

## 技术栈

- Django 6.0.3
- Django REST Framework
- djangorestframework-simplejwt
- MySQL

## 文档访问

项目还提供了自动生成的 API 文档：

- Swagger UI: `http://127.0.0.1:8000/api/docs/swagger/`
- Redoc: `http://127.0.0.1:8000/api/docs/redoc/`

这些文档提供了交互式的 API 测试界面，可以方便地测试各个接口。