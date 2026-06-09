# OAuth2.0 授权服务器模拟器

一个基于Flask的轻量级OAuth2.0授权服务器模拟器，用于本地开发和测试。

## 功能特性

- ✅ **动态客户端管理** - 通过Web界面或API动态创建OAuth客户端，自动生成client_id和client_secret
- ✅ **授权码模式** - 支持完整的Authorization Code Grant流程
- ✅ **客户端凭证模式** - 支持Client Credentials Grant
- ✅ **刷新令牌** - 支持Refresh Token流程
- ✅ **模拟登录** - 输入任意用户名即可完成登录
- ✅ **授权确认页面** - 模拟用户授权确认流程
- ✅ **Scope配置** - 可配置授权范围（read:user, write:data等）
- ✅ **多种令牌格式** - 支持JWT和随机字符串两种令牌格式
- ✅ **自定义过期时间** - 可为每个客户端设置不同的令牌过期时间
- ✅ **令牌验证接口** - 提供introspect endpoint供资源服务器使用
- ✅ **操作日志** - 记录所有令牌请求和换取令牌的操作
- ✅ **数据导出** - 支持导出客户端配置和令牌数据为JSON文件
- ✅ **令牌管理** - 管理页面查看、撤销已颁发的活跃令牌
- ✅ **模拟错误场景** - 支持模拟令牌验证失败等各种错误场景
- ✅ **现代化UI** - 响应式设计，美观的Web界面

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env` 并修改配置：

```bash
cp .env.example .env
```

### 3. 启动服务

```bash
python app.py
```

服务将在 http://localhost:5000 启动

## OAuth2.0 端点

| 端点 | 方法 | 描述 |
|------|------|------|
| `/oauth/authorize` | GET | 授权端点 - 获取授权码 |
| `/oauth/token` | POST | 令牌端点 - 换取访问令牌 |
| `/oauth/introspect` | POST | 令牌验证 - 供资源服务器使用 |
| `/oauth/revoke` | POST | 令牌撤销 - 撤销访问令牌或刷新令牌 |

## Web界面

| 页面 | 路径 | 描述 |
|------|------|------|
| 首页 | `/` | 仪表盘，显示统计信息和快捷操作 |
| 客户端管理 | `/clients` | 查看和管理所有客户端 |
| 创建客户端 | `/clients/new` | 创建新的OAuth客户端 |
| 客户端详情 | `/clients/<id>` | 查看客户端详情和相关令牌 |
| Scope管理 | `/scopes` | 配置授权范围 |
| 操作日志 | `/logs` | 查看所有操作日志 |
| 管理面板 | `/admin` | 令牌管理、模拟错误配置 |
| 令牌管理 | `/admin/tokens` | 查看和撤销令牌 |
| 模拟错误 | `/admin/simulated-errors` | 配置和管理模拟错误 |
| API文档 | `/docs` | 完整的API文档和使用说明 |

## API接口

### 客户端管理

```bash
# 获取所有客户端
GET /api/clients

# 创建客户端
POST /api/clients
Content-Type: application/json

{
    "name": "My App",
    "description": "My test application",
    "redirect_uris": ["http://localhost/callback"],
    "grant_types": ["authorization_code", "client_credentials"],
    "token_format": "jwt",
    "token_expire_seconds": 3600,
    "require_consent": true
}

# 获取客户端详情
GET /api/clients/<id>

# 更新客户端
PUT /api/clients/<id>

# 删除客户端
DELETE /api/clients/<id>
```

### Scope管理

```bash
# 获取所有Scope
GET /api/scopes

# 创建Scope
POST /api/scopes
{
    "name": "read:user",
    "description": "Read user profile",
    "is_enabled": true
}
```

### 数据导出

```bash
# 导出客户端配置
GET /api/export/clients

# 导出令牌数据
GET /api/export/tokens

# 导出所有数据
GET /api/export/all
```

## 使用示例

### 1. 创建客户端

访问 http://localhost:5000/clients/new 创建一个新客户端，或使用API：

```bash
curl -X POST http://localhost:5000/api/clients \
  -H "Content-Type: application/json" \
  -d '{
    "name": "测试应用",
    "description": "我的测试应用",
    "redirect_uris": ["http://localhost:3000/callback"],
    "grant_types": ["authorization_code", "client_credentials", "refresh_token"],
    "token_format": "jwt",
    "token_expire_seconds": 3600
  }'
```

### 2. 测试授权码模式

1. 在浏览器中访问授权URL：
```
http://localhost:5000/oauth/authorize?response_type=code&client_id=YOUR_CLIENT_ID&redirect_uri=http://localhost:3000/callback&scope=read:user%20write:data&state=random123
```

2. 输入任意用户名登录（例如：testuser）

3. 点击"允许授权"

4. 从回调URL中复制 `code` 参数

5. 使用code换取令牌：
```bash
curl -X POST http://localhost:5000/oauth/token \
  -u "YOUR_CLIENT_ID:YOUR_CLIENT_SECRET" \
  -d "grant_type=authorization_code" \
  -d "code=YOUR_AUTHORIZATION_CODE" \
  -d "redirect_uri=http://localhost:3000/callback"
```

### 3. 测试客户端凭证模式

```bash
curl -X POST http://localhost:5000/oauth/token \
  -u "YOUR_CLIENT_ID:YOUR_CLIENT_SECRET" \
  -d "grant_type=client_credentials" \
  -d "scope=read:user write:data"
```

### 4. 验证令牌

```bash
curl -X POST http://localhost:5000/oauth/introspect \
  -u "YOUR_CLIENT_ID:YOUR_CLIENT_SECRET" \
  -d "token=YOUR_ACCESS_TOKEN"
```

响应示例：
```json
{
    "active": true,
    "scope": "read:user write:data",
    "client_id": "YOUR_CLIENT_ID",
    "username": "testuser",
    "token_type": "Bearer",
    "exp": 1717234567,
    "iat": 1717230967,
    "token_format": "jwt"
}
```

### 5. 刷新令牌

```bash
curl -X POST http://localhost:5000/oauth/token \
  -u "YOUR_CLIENT_ID:YOUR_CLIENT_SECRET" \
  -d "grant_type=refresh_token" \
  -d "refresh_token=YOUR_REFRESH_TOKEN"
```

### 6. 撤销令牌

```bash
curl -X POST http://localhost:5000/oauth/revoke \
  -u "YOUR_CLIENT_ID:YOUR_CLIENT_SECRET" \
  -d "token=YOUR_ACCESS_TOKEN"
```

## 模拟错误场景

访问 http://localhost:5000/admin/simulated-errors 可以配置各种模拟错误：

| 错误类型 | 影响端点 | 状态码 |
|----------|----------|--------|
| `invalid_request` | /oauth/authorize | 400 |
| `invalid_client` | /oauth/token, /oauth/introspect | 401 |
| `invalid_grant` | /oauth/token | 400 |
| `invalid_scope` | /oauth/authorize, /oauth/token | 400 |
| `access_denied` | /oauth/authorize | 403 |
| `invalid_token` | /oauth/introspect | 401 |
| `insufficient_scope` | 资源验证 | 403 |
| `server_error` | 所有端点 | 500 |

启用某个错误后，对应的OAuth端点将返回预设的错误响应，方便测试客户端的错误处理逻辑。

## 项目结构

```
.
├── app.py                      # 应用入口
├── requirements.txt            # Python依赖
├── .env.example               # 环境变量示例
├── app/
│   ├── __init__.py            # 应用工厂
│   ├── models.py              # 数据库模型
│   ├── utils.py               # 工具函数
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── main.py            # 主页面路由
│   │   ├── oauth.py           # OAuth2.0端点
│   │   ├── admin.py           # 管理面板路由
│   │   ├── api.py             # API接口
│   │   └── auth.py            # 登录/登出
│   ├── templates/             # HTML模板
│   │   ├── base.html
│   │   ├── index.html
│   │   ├── login.html
│   │   ├── authorize.html
│   │   ├── clients.html
│   │   ├── client_detail.html
│   │   ├── client_form.html
│   │   ├── scopes.html
│   │   ├── logs.html
│   │   ├── admin.html
│   │   ├── admin_tokens.html
│   │   ├── simulated_errors.html
│   │   ├── simulated_error_form.html
│   │   └── docs.html
│   └── static/                # 静态资源
│       ├── css/style.css
│       └── js/main.js
└── README.md
```

## 数据库模型

- **Client** - OAuth客户端
- **AuthorizationCode** - 授权码
- **Token** - 访问令牌和刷新令牌
- **Scope** - 授权范围
- **Log** - 操作日志
- **SimulatedError** - 模拟错误配置

## 注意事项

⚠️ **仅供开发和测试使用，不要在生产环境中使用**

- 这是一个模拟器，不包含真实的用户认证和安全机制
- 登录只需要任意用户名，不需要密码
- 数据库使用SQLite，数据存储在本地文件中
- 所有密钥和配置都在.env文件中，生产环境需要加强安全措施

## 许可证

MIT License
