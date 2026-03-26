# DjangoUserService API 文档

## 1. 用户管理接口

### 1.1 用户注册

**接口路径**: `/user/register/`\
**请求方法**: `POST`\
**接口描述**: 注册新用户，支持用户名、邮箱、手机号注册

**请求参数**:

| 参数名               | 类型     | 必填 | 描述        |
| ----------------- | ------ | -- | --------- |
| username          | string | 是  | 用户名       |
| email             | string | 是  | 邮箱地址      |
| telephone         | string | 否  | 手机号码      |
| password          | string | 是  | 密码（6-20位） |
| confirm\_password | string | 是  | 确认密码      |

**请求示例**:

```json
{
  "username": "testuser",
  "email": "test@example.com",
  "telephone": "13800138000",
  "password": "password123",
  "confirm_password": "password123"
}
```

**返回示例**:

```json
{
  "message": "testuser 注册成功",
  "user": {
    "uuid": "a1b2c3d4-5678-90ef-ghij-klmnopqrstuv",
    "username": "testuser",
    "email": "test@example.com",
    "telephone": "13800138000",
    "gender": null,
    "bio": null,
    "avatar": null,
    "status": "active",
    "date_joined": "2026-03-24T12:00:00Z",
    "last_login": null
  },
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

### 1.2 用户登录

**接口路径**: `/user/login/`\
**请求方法**: `POST`\
**接口描述**: 用户登录，支持用户名或邮箱登录

**请求参数**:

| 参数名      | 类型     | 必填 | 描述                    |
| -------- | ------ | -- | --------------------- |
| username | string | 否  | 用户名（与email至少提供一个）     |
| email    | string | 否  | 邮箱地址（与username至少提供一个） |
| password | string | 是  | 密码（6-20位）             |

**请求示例**:

```json
{
  "username": "testuser",
  "password": "password123"
}
```

**返回示例**:

```json
{
  "message": "testuser 登录成功",
  "user": {
    "uuid": "a1b2c3d4-5678-90ef-ghij-klmnopqrstuv",
    "username": "testuser",
    "email": "test@example.com",
    "telephone": "13800138000",
    "gender": null,
    "bio": null,
    "avatar": null,
    "status": "active",
    "date_joined": "2026-03-24T12:00:00Z",
    "last_login": "2026-03-24T12:30:00Z"
  },
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

### 1.3 重置密码

**接口路径**: `/user/reset-password/`\
**请求方法**: `POST`\
**接口描述**: 重置用户密码，需要验证旧密码

**请求头**:

| 参数名           | 类型     | 必填 | 描述           |
| ------------- | ------ | -- | ------------ |
| Authorization | string | 是  | Bearer Token |

**请求参数**:

| 参数名               | 类型     | 必填 | 描述         |
| ----------------- | ------ | -- | ---------- |
| old\_password     | string | 是  | 旧密码（6-20位） |
| new\_password     | string | 是  | 新密码（6-20位） |
| confirm\_password | string | 是  | 确认新密码      |

**请求示例**:

```json
{
  "old_password": "password123",
  "new_password": "newpassword123",
  "confirm_password": "newpassword123"
}
```

**返回示例**:

```json
{
  "message": "密码重置成功",
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

### 1.4 刷新 Token

**接口路径**: `/user/refresh-token/`\
**请求方法**: `POST`\
**接口描述**: 使用旧 Token 刷新获取新 Token

**请求参数**:

| 参数名   | 类型     | 必填 | 描述           |
| ----- | ------ | -- | ------------ |
| token | string | 是  | 旧的 JWT Token |

**请求示例**:

```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**返回示例**:

```json
{
  "message": "Token刷新成功",
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expire_time": "2026-03-24T14:30:00Z"
}
```

### 1.5 获取用户详情

**接口路径**: `/user/detail/`\
**请求方法**: `GET`\
**接口描述**: 获取当前登录用户的详细信息

**请求头**:

| 参数名           | 类型     | 必填 | 描述           |
| ------------- | ------ | -- | ------------ |
| Authorization | string | 是  | Bearer Token |

**返回示例**:

```json
{
  "success": true,
  "message": "获取用户详情成功",
  "data": {
    "id": "a1b2c3d4-5678-90ef-ghij-klmnopqrstuv",
    "username": "testuser",
    "email": "test@example.com",
    "avatar": "/media/img/abc123.jpg",
    "telephone": "13800138000",
    "gender": "male",
    "bio": "这是个人简介",
    "create_time": "2026-03-24T12:00:00Z",
    "last_login": "2026-03-24T12:30:00Z"
  }
}
```

### 1.6 更新用户信息

**接口路径**: `/user/update/`\
**请求方法**: `PUT`\
**接口描述**: 更新当前登录用户的个人信息

**请求头**:

| 参数名           | 类型     | 必填 | 描述           |
| ------------- | ------ | -- | ------------ |
| Authorization | string | 是  | Bearer Token |

**请求参数**:

| 参数名       | 类型     | 必填 | 描述                    |
| --------- | ------ | -- | --------------------- |
| username  | string | 否  | 用户名                   |
| telephone | string | 否  | 手机号码                  |
| avatar    | string | 否  | 头像 URL                |
| gender    | string | 否  | 性别（male/female/other） |
| bio       | string | 否  | 个人简介                  |

**请求示例**:

```json
{
  "username": "newname",
  "telephone": "13900139000",
  "gender": "male",
  "bio": "更新后的个人简介"
}
```

**返回示例**:

```json
{
  "message": "用户信息更新成功",
  "user": {
    "uuid": "a1b2c3d4-5678-90ef-ghij-klmnopqrstuv",
    "username": "newname",
    "email": "test@example.com",
    "telephone": "13900139000",
    "gender": "male",
    "bio": "更新后的个人简介",
    "avatar": "/media/img/abc123.jpg",
    "status": "active",
    "date_joined": "2026-03-24T12:00:00Z",
    "last_login": "2026-03-24T12:30:00Z"
  },
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

### 1.7 用户注销

**接口路径**: `/user/logout/`\
**请求方法**: `POST`\
**接口描述**: 用户注销，将当前 Token 加入黑名单

**请求头**:

| 参数名           | 类型     | 必填 | 描述           |
| ------------- | ------ | -- | ------------ |
| Authorization | string | 是  | Bearer Token |

**返回示例**:

```json
{
  "message": "用户注销成功"
}
```

## 2. 文件管理接口

### 2.1 文件上传

**接口路径**: `/file/upload/`\
**请求方法**: `POST`\
**接口描述**: 上传图片文件，支持 JPG、JPEG、PNG、GIF 格式，大小不超过 1MB

**请求头**:

| 参数名           | 类型     | 必填 | 描述           |
| ------------- | ------ | -- | ------------ |
| Authorization | string | 是  | Bearer Token |

**请求参数**:

| 参数名 | 类型   | 必填 | 描述                           |
| --- | ---- | -- | ---------------------------- |
| img | file | 是  | 图片文件（支持 jpg、jpeg、png、gif 格式） |

**请求示例**:

```bash
# 使用 curl 上传文件
curl -X POST http://127.0.0.1:8001/file/upload/ \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -F "img=@/path/to/image.jpg"
```

**返回示例**:

```json
{
  "success": true,
  "data": {
    "url": "/media/img/a1b2c3d4.jpg",
    "alt": "当前加载较为缓慢，请稍后重试",
    "href": "/media/img/a1b2c3d4.jpg"
  }
}
```

## 3. 错误响应格式

所有接口在发生错误时都会返回统一的错误格式：

### 参数验证错误

```json
{
  "detail": {
    "field_name": "错误信息"
  }
}
```

### 认证失败

```json
{
  "detail": "认证失败或 Token 已过期"
}
```

### 服务器错误

```json
{
  "detail": "服务器内部错误"
}
```

## 4. Swagger 文档

项目集成了 Swagger 文档，可通过以下地址访问：

- Swagger UI: [http://127.0.0.1:8001/docs/](http://127.0.0.1:8000/docs/)
- ReDoc: [http://127.0.0.1:8001/redoc/](http://127.0.0.1:8000/redoc/)

## 5. 认证方式

所有需要认证的接口都需要在请求头中添加：

```
Authorization: Bearer <your_jwt_token>
```

JWT Token 的有效期为 2 小时，过期后需要使用 `/user/refresh-token/` 接口刷新。
