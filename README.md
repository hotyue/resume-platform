# 简历模板付费平台 (Resume Platform)

简历模板付费下载与众包定制服务平台，支持多级推广分佣、制作者接单交付、在线聊天、支付与提现。

**当前版本**: `v0.11.0` | [Release](https://github.com/hotyue/resume-platform/releases/tag/v0.11.0)

## 功能概览

| 模块 | 功能 |
|------|------|
| **模板下载** | 简历模板浏览、购买（¥1.99）、PayJS 支付 |
| **定制服务** | 买家下单（¥19.99）→ 制作者抢单 → 24h 交付 → 买家验收 |
| **推广分佣** | 二级推广体系，L1 上级 30%、L2 上上级 10% |
| **订单分佣** | 定制订单走制作者推广链（本人 30% / 上级 10%） |
| **制作者管理** | 入驻申请、保证金冻结（¥20）、超时违约金（8h 扣 10%，上限 50%） |
| **在线聊天** | 买家与制作者 WebSocket 实时沟通，消息持久化存库 |
| **钱包与提现** | 钱包余额、分佣累计统计、提现申请（最低 ¥50）、转账凭证管理 |
| **退款管理** | 退款申请、审核、制作者扣款、平台承担 |
| **后台管理** | 用户/订单/申请/提现/分佣/退款/审计日志/系统配置全管理 |
| **第三方登录** | 微信 OpenID、支付宝授权登录 |
| **系统配置** | 后台动态调整分佣比例、保证金、提现门槛等参数 |

## 技术栈

### 后端

| 组件 | 技术 |
|------|------|
| 框架 | FastAPI 0.104 + Uvicorn |
| ORM | SQLAlchemy 2.0 (declarative) |
| 数据库 | PostgreSQL 15 / SQLite (开发) |
| 迁移 | Alembic 1.13 |
| 认证 | JWT (python-jose, 24h 有效期) |
| 定时任务 | APScheduler 3.10 |
| 存储 | S3 兼容服务 (boto3) / 本地文件 |
| 支付 | PayJS Native / 模拟支付 |
| 实时通信 | WebSocket (websockets) |
| 文件上传 | python-multipart |

### 前端

| 组件 | 技术 |
|------|------|
| 框架 | Vue 3.5 (Composition API) |
| 构建 | Vite 8 |
| UI 库 | Vant 4 (移动端组件) |
| 状态管理 | Pinia 3 |
| 路由 | Vue Router 5 (带路由守卫) |
| HTTP | Axios (统一拦截器 + Token 注入) |

## 项目结构

```
resume-platform/
├── backend/
│   ├── main.py                  # FastAPI 入口 + 定时任务调度
│   ├── models.py                # SQLAlchemy 数据模型 (15 个表)
│   ├── schemas.py               # Pydantic 请求/响应模型
│   ├── database.py              # 数据库连接
│   ├── config.py                # 环境变量配置
│   ├── auth.py                  # JWT 认证、密码哈希
│   ├── commission.py            # 分佣计算、违约金逻辑
│   ├── payjs.py                 # PayJS 支付接口
│   ├── storage.py               # S3 文件存储
│   ├── import_templates.py      # 模板批量导入工具
│   ├── entrypoint.sh            # Docker 启动入口
│   ├── Dockerfile               # 后端镜像构建
│   ├── requirements.txt
│   ├── alembic.ini              # Alembic 配置
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/            # 迁移脚本
│   └── routers/                 # 路由拆分
│       ├── auth.py              # 登录 / 注册 / 第三方登录
│       ├── user.py              # 用户中心 / 钱包 / 推广
│       ├── creator.py           # 制作者中心 / 入驻 / 抢单 / 交付
│       ├── orders.py            # 订单查询 / 验收 / 退款申请
│       ├── templates.py         # 模板列表 / 下载
│       ├── ws.py                # WebSocket 聊天
│       └── admin/               # 后台管理路由
│           ├── dashboard.py     # 仪表盘统计
│           ├── users.py         # 用户管理
│           ├── orders.py        # 订单管理
│           ├── applications.py  # 入驻申请审核
│           ├── withdrawals.py   # 提现审核
│           ├── refunds.py       # 退款审核
│           ├── audit.py         # 审计日志
│           ├── commission.py    # 分佣管理
│           └── config.py        # 系统配置
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   ├── src/
│   │   ├── main.js              # Vue 入口
│   │   ├── router.js            # 路由定义 + 守卫
│   │   ├── App.vue              # 根组件 (Tabbar + WebSocket 心跳)
│   │   ├── api/request.js       # Axios 封装
│   │   ├── stores/auth.js       # 认证状态管理
│   │   └── components/
│   │       ├── ResumeList.vue       # 模板列表 (首页)
│   │       ├── CrowdHall.vue        # 众包大厅
│   │       ├── UserCenter.vue       # 用户中心
│   │       ├── CreatorCenter.vue    # 制作者中心
│   │       ├── MyCustomOrders.vue   # 我的定制订单
│   │       ├── OrderChat.vue        # 订单聊天
│   │       ├── DeliveryDialog.vue   # 交付弹窗
│   │       ├── Login.vue            # 登录
│   │       ├── Register.vue         # 注册
│   │       ├── OAuthCallback.vue    # 第三方登录回调
│   │       ├── AdminPanel.vue       # 后台管理入口
│   │       └── admin/               # 后台管理子组件
│   │           ├── AdminDashboard.vue
│   │           ├── AdminUsers.vue
│   │           ├── AdminOrders.vue
│   │           ├── AdminApplications.vue
│   │           ├── AdminWithdrawals.vue
│   │           ├── AdminRefunds.vue
│   │           ├── AdminAuditLogs.vue
│   │           └── AdminSettings.vue
├── assets/                      # 模板素材库 (JPG/DOCX)
├── docker-compose.yml
└── .env.example
```

## 快速开始

### 前置条件

- Docker & Docker Compose
- 模板素材放在 `assets/` 目录

### 一键启动

```bash
git clone https://github.com/hotyue/resume-platform.git
cd resume-platform
docker compose up -d
```

启动后服务地址：

| 服务 | 地址 |
|------|------|
| 后端 API | http://localhost:8000 |
| API 文档 | http://localhost:8000/docs |
| 前端开发 | http://localhost:5173 |
| PostgreSQL | localhost:5432 |

### 本地开发

#### 后端

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 环境变量
export DATABASE_URL="sqlite:///./resume_dev.db"
export JWT_SECRET="dev-secret-change-in-prod"

# 数据库迁移
alembic upgrade head

# 启动
uvicorn main:app --reload --port 8000
```

#### 前端

```bash
cd frontend
npm install
npm run dev
```

## 配置

### 环境变量

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `DATABASE_URL` | ✅ | `sqlite:///./resume_dev.db` | 数据库连接 |
| `JWT_SECRET` | ✅ | `resume-platform-dev-secret-change-in-prod` | JWT 密钥 |
| `ASSETS_DIR` | - | `/root/assets` | 模板素材目录 |
| `PAYJS_MCHID` | - | *(空=模拟支付)* | PayJS 商户号 |
| `PAYJS_KEY` | - | *(空=模拟支付)* | PayJS API 密钥 |
| `PAYJS_NOTIFY_URL` | - | *(空)* | PayJS 回调地址 |
| `S3_ENDPOINT` | - | *(空)* | S3 兼容服务地址 |
| `S3_ACCESS_KEY` | - | *(空)* | S3 访问密钥 |
| `S3_SECRET_KEY` | - | *(空)* | S3 密钥 |
| `S3_BUCKET` | - | `resume-deliveries` | S3 存储桶 |
| `S3_REGION` | - | `us-east-1` | S3 区域 |

### 数据库迁移

```bash
# 查看迁移状态
alembic current

# 执行所有迁移
alembic upgrade head

# 生成新迁移
alembic revision --autogenerate -m "description"

# 回退一步
alembic downgrade -1
```

## 数据模型

| 模型 | 表名 | 说明 |
|------|------|------|
| `User` | `users` | 用户（含推广树、钱包余额、提现账户） |
| `Template` | `templates` | 简历模板 |
| `Order` | `orders` | 订单（下载/定制，含状态机） |
| `CommissionConfig` | `commission_config` | 分佣比例配置 |
| `CommissionRecord` | `commission_records` | 分佣明细 |
| `CommissionPending` | `commission_pending` | 待发放佣金（冻结期管理） |
| `CreatorApplication` | `creator_applications` | 制作者入驻申请 |
| `Delivery` | `deliveries` | 交付记录（PDF + Word 双文件） |
| `Review` | `reviews` | 买家验收记录 |
| `WithdrawRequest` | `withdraw_requests` | 提现申请 |
| `RefundRequest` | `refund_requests` | 退款申请 |
| `RechargeRecord` | `recharge_records` | 充值记录 |
| `CreatorAuditLog` | `creator_audit_log` | 制作者审计日志 |
| `ThirdPartyAuth` | `third_party_auth` | 第三方登录授权 |
| `OrderMessage` | `order_messages` | 订单聊天消息 |
| `SystemConfig` | `system_config` | 系统配置（后台可改） |

## 业务流程

### 订单状态机

```
pending → paid → (download: 完成)
                → (custom: awaiting_claim → claimed → in_progress
                   → delivered → accepted → completed)
                        ↑              ↓
                        └── rejected ──┘
```

### 定制订单完整流程

1. **买家下单** → 支付 ¥19.99 → 状态 `paid`
2. **发布到众包大厅** → 状态 `awaiting_claim`
3. **制作者抢单** → 冻结保证金 ¥20 → 状态 `claimed` → `in_progress`
4. **制作者交付** → 上传 PDF + Word → 状态 `delivered`
5. **买家验收** → 通过/拒绝（7 天自动验收）
6. **佣金结算** → 通过 → 冻结佣金释放 → 状态 `completed`

### 分佣体系

**两类分佣**：

| 分佣类型 | 触发条件 | 推广链 | L1 本人 | L2 上级 |
|----------|---------|--------|---------|---------|
| 推荐分佣 | 用户首单（一次性） | 下单用户推广链 | 30% | 10% |
| 订单分佣 | 非首单（无限次） | 定制：制作者链 / 下载：下单用户链 | 30% | 10% |

> ⚠️ 首单互斥：只走推荐分佣，不走订单分佣。原三级推广 (5%) 已停用，归平台。

### 违约金规则

| 条件 | 规则 |
|------|------|
| 接单后 24h | 正常交付期 |
| 超时 8h | 扣保证金 10% |
| 每超 8h | 继续扣 10%，累计上限 50% |
| 超时 72h | 订单重新发布到众包大厅 |
| 连续超时 3 次 | 暂停接单权限 |

## API 路由

### 认证

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/auth/login` | 账号密码登录 |
| POST | `/api/v1/auth/register` | 注册 |
| POST | `/api/v1/auth/oauth/{provider}` | 第三方登录 |
| POST | `/api/v1/auth/logout` | 退出 |

### 用户

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/user/profile` | 个人信息 |
| GET | `/api/v1/user/wallet` | 钱包信息 |
| GET | `/api/v1/user/team` | 推广团队 |
| POST | `/api/v1/user/withdraw` | 提现申请 |

### 模板

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/templates` | 模板列表 |
| GET | `/api/v1/templates/{id}` | 模板详情 |
| GET | `/api/v1/templates/{id}/preview` | 预览图 |

### 订单

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/orders` | 创建订单 |
| GET | `/api/v1/orders` | 订单列表 |
| GET | `/api/v1/orders/{order_no}` | 订单详情 |
| POST | `/api/v1/orders/{order_no}/review` | 验收 |
| POST | `/api/v1/orders/{order_no}/refund` | 退款申请 |

### 制作者

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/creator/apply` | 入驻申请 |
| GET | `/api/v1/creator/orders` | 制作者订单列表 |
| POST | `/api/v1/creator/claim/{order_no}` | 抢单 |
| POST | `/api/v1/creator/deliver/{order_no}` | 交付 |

### WebSocket

| 路径 | 说明 |
|------|------|
| WS `/api/v1/ws/chat/{order_id}` | 订单聊天 |

### 后台管理 (`/api/v1/admin/`)

| 路径 | 说明 |
|------|------|
| `dashboard/stats` | 仪表盘统计 |
| `users/*` | 用户管理 |
| `orders/*` | 订单管理 |
| `applications/*` | 入驻申请审核 |
| `withdrawals/*` | 提现审核 |
| `refunds/*` | 退款审核 |
| `audit/logs` | 审计日志 |
| `commission/*` | 分佣管理 |
| `config/*` | 系统配置 |

## 定时任务

APScheduler 在启动时自动注册以下定时任务：

| 任务 | 频率 | 说明 |
|------|------|------|
| 违约金检查 | 每 30 分钟 | 检查超时订单，扣除违约金 |
| 自动验收 | 每 1 小时 | 冻结期到期的订单自动验收 |
| 佣金释放 | 每 1 小时 | 释放冻结期到期的佣金 |

## 部署

### 生产环境 Docker Compose

```bash
# 1. 配置 .env
cp .env.example .env
# 编辑 .env 设置 DATABASE_URL, JWT_SECRET, PAYJS_*, S3_*

# 2. 启动
docker compose up -d

# 3. 数据库迁移
docker compose exec api alembic upgrade head
```

### S3 交付文件路径规则

```
deliveries/YYYY/MM/DD/order_no_filename
```

例如：`deliveries/2026/07/16/ORD20260716120000_resume.pdf`

## 许可证

Private
