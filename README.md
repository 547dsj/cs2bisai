# CS2 赛事全景网站

一个 CS2 赛事展示与管理系统，包含：

- 用户页面：`/` 或 `/cs2bisai`，只读查看，无需登录
- 管理员页面：`/admin` 或 `/cs2bisai/admin`，需要密码登录后可增删改
- 数据接口：`/api/events`、`/api/settings` 等
- 管理员登录接口：`/api/admin/login`
- 后端安全：管理员密码哈希验证、Session 登录、接口限流、登录防爆破

## 项目结构

- `main.py`：FastAPI 后端入口
- `public/user.html`：用户只读页面
- `public/admin.html`：管理员页面
- `public/static/config.js`：前端 API 地址配置
- `schema.sql`：数据库结构
- `seed.sql`：初始赛事数据
- `.env.example`：环境变量示例

## 本地运行

```powershell
# 1. 创建并配置环境变量
copy .env.example .env
# 然后编辑 .env，填入 ADMIN_PASSWORD、SECRET_KEY、DB_PASSWORD 等

# 2. 安装依赖
pip install -r requirements.txt

# 3. 导入数据库
# 在 MySQL 中执行 schema.sql 和 seed.sql

# 4. 启动后端
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

访问：

- 用户页面：http://127.0.0.1:8000/
- 管理员页面：http://127.0.0.1:8000/admin

## 环境变量

| 变量 | 说明 |
| --- | --- |
| ADMIN_PASSWORD | 管理员密码，不会上传到 Git |
| SECRET_KEY | Session 加密密钥 |
| DB_HOST | MySQL 地址 |
| DB_USER | MySQL 用户名 |
| DB_PASSWORD | MySQL 密码 |
| DB_NAME | 数据库名 |

## 安全设计

- 管理员密码只保存哈希，不保存明文。
- 登录成功后使用 HttpOnly 会话 Cookie。
- 所有增删改接口都需要管理员登录。
- 登录接口限流：同一 IP 15 分钟内最多尝试 5 次。
- API 限流：同一 IP 每分钟最多 240 次。
- `.env` 已加入 `.gitignore`，不会提交到 GitHub。

## 部署到 Cloudflare

`public/` 目录是可直接发布的前端静态文件。Cloudflare Pages 可将构建输出目录设置为 `public`。

注意：本项目后端使用 Python + MySQL，Cloudflare Pages 本身不能运行 Python 和 MySQL。若要完全部署到 Cloudflare，需要：

- 将 FastAPI 后端单独部署到云服务器，前端通过 `public/static/config.js` 配置后端地址；或
- 将后端迁移为 Cloudflare Workers + D1/KV。

当前仓库先完成可发布文件整理和 GitHub 托管，后续可按上述方案接入 Cloudflare。