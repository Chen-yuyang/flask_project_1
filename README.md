# 物品管理系统 (Item Management System)

基于 Flask 的物品/空间/借用/预约管理系统。支持多级空间结构、物品二维码、借用记录、预约排期、邮件通知和定时任务。

## 项目架构

```
doubao_test_2/
├── run.py                    # 应用入口
├── config.py                 # 配置类（开发/测试/生产/ Docker）
├── requirements.txt          # Python 依赖
├── .env                      # 环境变量（不提交到 Git）
├── db_update_script.py       # 数据库更新脚本
├── fix_sqlite_constraint.py  # SQLite 约束修复脚本
│
├── app/
│   ├── __init__.py           # 应用工厂 create_app()、扩展初始化、APScheduler
│   ├── models.py             # 数据模型（User, Space, Item, Record, Reservation）
│   ├── tasks.py              # 定时任务（预约状态更新、逾期检查）
│   ├── email.py              # 邮件发送（异步线程）
│   ├── utils.py              # 工具函数（装饰器等）
│   │
│   ├── forms/                # WTForms 表单
│   │   ├── auth_forms.py     #   登录/注册/密码/邮箱
│   │   ├── space_forms.py    #   空间创建/编辑
│   │   ├── item_forms.py     #   物品创建/编辑
│   │   ├── record_forms.py   #   借用记录
│   │   └── reservation_forms.py  # 预约
│   │
│   ├── routes/               # 蓝图路由
│   │   ├── main.py           #   首页、全局搜索         (/)
│   │   ├── auth.py           #   认证/用户中心          (/auth)
│   │   ├── spaces.py         #   空间管理               (/spaces)
│   │   ├── items.py          #   物品管理               (/items)
│   │   ├── records.py        #   借用记录               (/records)
│   │   ├── reservations.py   #   预约管理               (/reservations)
│   │   ├── admin.py          #   超级管理员·用户管理    (/admin)
│   │   └── engineer.py       #   工程师面板·数据库查看  (/engineer)
│   │
│   └── templates/            # Jinja2 模板
│       ├── base.html
│       ├── main/
│       ├── auth/
│       ├── spaces/
│       ├── items/
│       ├── records/
│       ├── reservations/
│       └── engineer/
│
├── migrations/               # Alembic 数据库迁移
│   ├── env.py
│   └── versions/
│
├── instance/                 # SQLite 数据库文件（不提交到 Git）
│   └── item_management.db
│
├── logs/                     # 运行日志
│   └── app.log
│
└── tests/                    # 测试
    └── test_email.py
```

## 功能概览

### 用户与认证
- 用户注册 / 登录 / 登出（支持无邮箱注册）
- 邮箱绑定与验证
- 密码重置（邮件链接）
- 修改用户名 / 密码
- 个人中心

### 权限体系
| 角色 | 说明 |
|---|---|
| **超级管理员 (Root)** | 由 `.env` 中 `FLASKY_ADMIN` 邮箱列表指定，注册即自动获得；可任免普通管理员 |
| **普通管理员 (Admin)** | 可创建/编辑/删除空间和物品，查看所有借用记录和预约 |
| **普通用户 (User)** | 可浏览空间/物品，借用物品，创建预约，查看自己的记录 |

### 空间管理
- 多级树形空间结构（如：大楼 → 楼层 → 房间 → 柜子）
- 空间内搜索物品
- 空间 CRUD（仅管理员）

### 物品管理
- 物品创建 / 编辑 / 删除（仅管理员）
- 自动绑定序列号，自动生成二维码（扫码查看物品详情）
- 物品状态：`available`（可用）/ `borrowed`（借出）/ `reserved`（已预约）

### 借用记录
- 借用物品（普通用户仅能借可用/已预约给自己的物品）
- 管理员可代他人借用，支持批量指定用户
- 归还操作
- 逾期自动检测（超过 10 天）并邮件提醒

### 预约系统
- 预约物品的未来使用时间段
- 自动检测时间冲突
- 预约状态自动流转：
  - `scheduled`（待开始）→ `active`（生效）→ `used`（已使用）/ `expired`（过期）
  - 物品未归还时 → `conflicted`（冲突）→ 物品归还后自动恢复 `active`
- 预约生效时自动锁定物品，过期自动释放
- 预约前提醒（提前 12 小时邮件通知）

### 定时任务（APScheduler）
| 任务 | 频率 | 说明 |
|---|---|---|
| `update_reservation_status` | 每 30 秒 | 更新预约状态（scheduled→active、conflicted→active、active→expired） |
| `check_overdue_records` | 每 1 小时 | 检查超过 7 天未归还的记录，发送逾期提醒邮件 |

### 工程师面板
- 通过 Access Key 认证（独立于用户系统）
- 查看所有数据库表内容
- 查看应用日志
- 手动触发定时任务

### 全局搜索
- 按物品名称/功能/序列号、记录使用地点/用户名、空间名称进行模糊搜索

---

## 从零开始部署

### 1. 环境要求

- Python 3.9+
- pip

### 2. 克隆项目

```bash
git clone git@github.com:Chen-yuyang/flask_item_system.git
cd flask_item_system
```

### 3. 创建虚拟环境

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

### 4. 安装依赖

```bash
pip install -r requirements.txt
```

### 5. 配置环境变量

复制并编辑 `.env` 文件：

```bash
cp .env.example .env   # 如果有模板的话，否则手动创建
```

`.env` 关键配置项：

```ini
# Flask 入口
FLASK_APP=run.py
FLASK_CONFIG=development    # development / production / testing / docker
FLASK_DEBUG=1               # 生产环境设为 0

# 安全密钥（生产环境必须修改）
SECRET_KEY=your-secret-key-here

# 数据库（可选，默认使用 instance/item_management.db）
# DEV_DATABASE_URL=sqlite:///instance/item_management.db

# 邮件（QQ 邮箱示例）
MAIL_SERVER=smtp.qq.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=your-email@qq.com
MAIL_PASSWORD=your-smtp-password    # QQ 邮箱的授权码

# 超级管理员邮箱（逗号分隔多个）
FLASKY_ADMIN=admin@example.com

# 二维码基础链接（物品详情页 URL 前缀）
QR_CODE_BASE_URL=http://192.168.1.101:8080

# 工程师面板密钥
ENGINEER_ACCESS_KEY=your-engineer-key
```

### 6. 初始化数据库

```bash
# 方式一：Flask CLI 命令
flask init-db

# 方式二：Flask-Migrate（如果有迁移历史）
flask db upgrade
```

### 7. 运行

```bash
# 开发环境
python run.py

# 或者用 flask 命令
flask run --host=0.0.0.0 --port=8080
```

访问 `http://localhost:8080`。

### 8. 注册超级管理员

在浏览器访问 `/auth/register`，使用 `.env` 中 `FLASKY_ADMIN` 配置的邮箱注册，系统会自动将其设为超级管理员。

---

## 生产环境部署

```bash
# 设置环境变量
export FLASK_CONFIG=production
export FLASK_DEBUG=0
export SECRET_KEY=<强随机密钥>

# 使用 Gunicorn（Linux）
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8080 "run:app"
```

建议配合 Nginx 反向代理，并将 SQLite 替换为 PostgreSQL/MySQL。

## 常用 CLI 命令

```bash
flask init-db          # 初始化数据库（清空重建）
flask db upgrade       # 执行数据库迁移
flask db migrate -m "描述"  # 生成迁移脚本
```

## 技术栈

| 组件 | 技术 |
|---|---|
| Web 框架 | Flask 3.x |
| 数据库 ORM | Flask-SQLAlchemy (SQLAlchemy 2.x) |
| 数据库迁移 | Flask-Migrate (Alembic) |
| 表单验证 | Flask-WTF (WTForms) |
| 用户认证 | Flask-Login |
| 邮件 | Flask-Mail（异步线程发送） |
| 定时任务 | APScheduler |
| 前端 | Flask-Bootstrap + Jinja2 |
| 二维码 | qrcode + Pillow |
| 时区处理 | pytz |
