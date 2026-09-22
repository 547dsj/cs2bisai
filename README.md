# CS2 赛事全景网站

一个 CS2 赛事展示与管理系统，包含：

- 用户页面：`/` 或 `/cs2bisai`，只读查看，无需登录
- 管理员页面：`/admin` 或 `/cs2bisai/admin`，需要密码登录后可增删改
- 数据接口：`/api/events`、`/api/settings` 等
- 管理员登录接口：`/api/admin/login`
- 后端安全：管理员密码哈希验证、Session 登录、接口限流、登录防爆破

## 部署架构（Cloudflare Pages + Functions + D1）

- 前端：`public/` 目录，Cloudflare Pages 静态托管。
- 后端：`functions/api/[[path]].js`，Cloudflare Pages Functions，与前端同域。
- 数据库：Cloudflare D1，绑定变量名 `DB`。
- 无需云服务器。

## 项目结构

- `public/user.html`：用户只读页面
- `public/admin.html`：管理员页面
- `public/static/config.js`：前端 API 地址解析（生产环境留空，本地 `file:` 打开时指向 `http://localhost:8000`）
- `functions/api/[[path]].js`：Pages Functions 后端
- `wrangler.toml`：Cloudflare 配置（D1 绑定）
- `d1_schema.sql`：D1 建表 SQL
- `d1_seed.sql`：D1 初始赛事数据（29 条）
- `.dev.vars.example`：本地 Workers 环境变量示例
- `main.py` / `schema.sql` / `seed.sql` / `.env.example`：旧版 FastAPI + MySQL 本地实现，已保留备用

## Cloudflare 部署步骤

1. 在 Cloudflare Dashboard 创建 D1 数据库，记录 `database_id`。
2. 执行 `d1_schema.sql` 建表，再执行 `d1_seed.sql` 导入数据。
3. 在 Cloudflare Pages 中新建项目并连接本 GitHub 仓库。
4. Pages 构建设置：
   - 构建命令：留空
   - 构建输出目录：`public`
5. 绑定 D1：变量名 `DB`，指向步骤 1 创建的数据库。
6. 设置环境变量：
   - `SESSION_SECRET`：一段足够长的随机字符串。
   - `ADMIN_PASSWORD_HASH`：可选，管理员密码的 PBKDF2 哈希；未设置时使用代码内置默认值。
7. 保存后 Pages 会自动构建并部署。

## 安全设计

- 管理员密码只保存哈希，不保存明文。
- 登录成功后使用 HttpOnly 会话 Cookie，7 天过期。
- 所有增删改接口都需要管理员登录。
- 登录接口限流：同一 IP 15 分钟内最多尝试 5 次。
- API 限流：同一 IP 每分钟最多 240 次。
- 每次增删改操作后自动更新 `last_modified` 时间。
- `.env`、`.dev.vars` 已加入 `.gitignore`，不会提交到 GitHub。
