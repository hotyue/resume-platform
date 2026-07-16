# 简历模板付费平台 — 系统架构设计文档

**版本**: v0.11.0 | **更新**: 2026-07-16

---

## 一、项目概述

简历模板付费下载与众包定制服务平台。核心商业模式：

- **模板下载**: ¥1.99/份，自动交付 PDF
- **定制服务**: ¥19.99/份，制作者接单 → 24h 交付 → 买家验收
- **推广分佣**: 二级推广体系，推广者获得下级消费分佣
- **制作者分佣**: 制作者获得订单金额 30% + 推广链 10%

目标平台：移动端 H5，适配抖音/小红书等短视频平台内置浏览器。

---

## 二、技术架构

### 2.1 整体架构

```
┌──────────────────────────────────────────────────────────────┐
│                        用户端 (H5)                           │
│  Vue 3 + Vant 4 + Pinia + Vue Router + Axios + WebSocket    │
└──────────────────────────┬───────────────────────────────────┘
                           │ HTTP / WebSocket
┌──────────────────────────▼───────────────────────────────────┐
│                      后端 API 层                              │
│  FastAPI 0.104 + Uvicorn                                     │
│                                                              │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐           │
│  │ auth    │ │ user    │ │ creator │ │ orders  │  路由层    │
│  │ routes  │ │ routes  │ │ routes  │ │ routes  │           │
│  ├─────────┤ ├─────────┤ ├─────────┤ ├─────────┤           │
│  │templates│ │  ws     │ │ admin/* │ │ (9个子路由)          │
│  │ routes  │ │ routes  │ │ routes  │                      │
│  └─────────┘ └─────────┘ └─────────┘                      │
│                                                              │
│  ┌─────────┐ ┌────────────┐ ┌────────┐ ┌────────┐         │
│  │  auth   │ │ commission │ │ payjs  │ │storage │ 工具层   │
│  │  utils  │ │    logic   │ │  client│ │   S3   │         │
│  └─────────┘ └────────────┘ └────────┘ └────────┘         │
│                                                              │
│  ┌─────────────────────────────────────────────────┐        │
│  │  APScheduler: 违约金检查 / 自动验收 / 佣金释放    │        │
│  └─────────────────────────────────────────────────┘        │
└──────────────────────────┬───────────────────────────────────┘
                           │ SQLAlchemy ORM
┌──────────────────────────▼───────────────────────────────────┐
│                    数据持久层                                  │
│  PostgreSQL 15 (生产) / SQLite (开发)                         │
│  Alembic 1.13 迁移管理                                       │
└──────────────────────────────────────────────────────────────┘

┌───────────────┐     ┌───────────────┐
│  S3 兼容存储   │     │  PayJS 支付    │
│  (交付文件)    │     │  (Native 二维码)│
└───────────────┘     └───────────────┘
```

### 2.2 技术选型

#### 后端

| 层级 | 选型 | 版本 | 说明 |
|------|------|------|------|
| Web 框架 | FastAPI | 0.104.1 | 异步、自动文档生成 |
| ORM | SQLAlchemy | 2.0.23 | Declarative 2.0 风格 |
| 数据验证 | Pydantic | 2.4.2 | 请求/响应模型 |
| 数据库 | PostgreSQL | 15 | 生产环境 |
| 数据库 | SQLite | — | 开发环境 |
| 迁移 | Alembic | 1.13.1 | 数据库版本管理 |
| 认证 | python-jose | 3.5.0 | JWT 签发与验证 |
| 密码 | passlib | 1.7.4 | bcrypt 哈希 |
| 定时任务 | APScheduler | 3.10.4 | 违约金/自动验收/佣金释放 |
| 对象存储 | boto3 | 1.43.46 | S3 兼容服务 |
| 支付 | PayJS SDK | — | Native 支付 / 未配置时模拟 |
| WebSocket | websockets | ≥12.0 | 订单聊天 |

#### 前端

| 层级 | 选型 | 版本 | 说明 |
|------|------|------|------|
| 框架 | Vue | 3.5.39 | Composition API |
| 构建 | Vite | 8.1.1 | 热更新、快速开发 |
| UI | Vant | 4.10.0 | 移动端组件库 |
| 状态 | Pinia | 3.0.4 | 轻量状态管理 |
| 路由 | Vue Router | 5.1.0 | 路由守卫检查登录态 |
| HTTP | Axios | 1.18.1 | Token 自动注入拦截器 |

---

## 三、数据模型设计

### 3.1 ER 关系图

```
┌──────────┐     1:N     ┌──────────┐     1:N     ┌───────────┐
│   User   │─────────────│  Order   │────────────│  Delivery  │
└──────────┘              └──────────┘             └───────────┘
     │                         │                         │
     │ parent_id              │ creator_id              │ order_no
     │ (自关联推广树)           │                         │
     ▼                         ▼                         ▼
┌──────────┐          ┌──────────┐              ┌───────────┐
│ User     │          │ Creator  │              │   Review  │
│(parent)  │          │Applicat. │              └───────────┘
└──────────┘          └──────────┘
     │                         │
     │ 1:N                    │ 1:N
     ▼                         ▼
┌──────────┐          ┌──────────┐
│Commission│          │ Commission│
│ Record   │          │  Pending  │
└──────────┘          └──────────┘

User ──1:N── WithdrawRequest
User ──1:N── RechargeRecord
User ──1:N── CreatorAuditLog
User ──1:N── ThirdPartyAuth
  Order ──1:N── RefundRequest
  Order ──1:N── OrderMessage
  Template ──1:N── Order
```

### 3.2 数据表详情

#### 用户模块

**`users` — 用户表**

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INT PK | 用户 ID |
| `username` | VARCHAR(50) UNIQUE | 用户名 |
| `password_hash` | VARCHAR(256) | 密码哈希 (bcrypt) |
| `role` | VARCHAR(20) | `user` / `creator` / `admin` |
| `wallet_balance` | FLOAT | 钱包余额 |
| `deposit_frozen` | FLOAT | 制作者保证金冻结额 |
| `parent_id` | INT FK → users.id | 推广上级 |
| `team_size` | INT | 团队人数 |
| `alipay_account` | VARCHAR(100) | 支付宝提现账户 |
| `wechat_account` | VARCHAR(100) | 微信提现账户 |
| `wechat_openid` | VARCHAR(100) | 微信 OpenID |
| `alipay_user_id` | VARCHAR(100) | 支付宝 USERID |
| `total_withdrawn` | FLOAT | 累计提现 |
| `frozen_withdraw` | FLOAT | 提现冻结额（待审核） |
| `frozen_commission` | FLOAT | 分佣冻结额 |
| `referral_commission` | FLOAT | 推广分佣累计（只读） |
| `making_commission` | FLOAT | 制作分佣累计（只读） |
| `created_at` | DATETIME | 注册时间 |

> **可提现余额** = `wallet_balance - deposit_frozen - frozen_withdraw`

**`third_party_auth` — 第三方登录授权**

| 字段 | 类型 | 说明 |
|------|------|------|
| `user_id` | INT FK | 用户 |
| `provider` | VARCHAR(20) | `wechat` / `alipay` |
| `openid` | VARCHAR(100) | 第三方唯一标识 |
| `union_id` | VARCHAR(100) | 微信 UnionID |
| `token` | TEXT | 第三方 access_token |

#### 订单模块

**`orders` — 订单表**

| 字段 | 类型 | 说明 |
|------|------|------|
| `order_no` | VARCHAR(32) UNIQUE | 订单号 |
| `user_id` | INT | 下单用户 |
| `template_id` | INT FK → templates.id | 模板 |
| `order_type` | VARCHAR(20) | `download` / `custom_service` |
| `amount` | FLOAT | 订单金额 |
| `status` | VARCHAR(20) | 订单状态（见状态机） |
| `ref_user_id` | INT | 推广邀请人 |
| `custom_requirements` | TEXT | 定制需求描述 |
| `creator_id` | INT | 接单制作者 |
| `claimed_at` | DATETIME | 接单时间（交付周期起点） |
| `penalty_deducted` | FLOAT | 已扣违约金总额 |
| `penalty_count` | INT | 违约金扣款次数 |
| `delivered_at` | DATETIME | 交付时间 |
| `accepted_at` | DATETIME | 验收时间 |
| `freeze_until` | DATETIME | 佣金冻结到期 |
| `commission_distributed` | BOOLEAN | 下载订单分佣标记 |
| `created_at` | DATETIME | 下单时间 |

**订单状态枚举**：

```
pending           待支付
paid              已支付
awaiting_claim    待抢单（定制订单进入众包大厅）
claimed           已抢单
in_progress       制作中
delivered         已交付（等待验收）
accepted          买家确认通过
rejected          买家拒绝（退回制作）
refund_requested  已申请退款
refunded          已退款
completed         已完成（佣金已发放）
cancelled         已取消
```

**`templates` — 简历模板**

| 字段 | 类型 | 说明 |
|------|------|------|
| `category` | VARCHAR(100) | 分类 |
| `name` | VARCHAR(200) | 模板名称 |
| `jpg_path` | VARCHAR(500) | 预览图路径 |
| `doc_path` | VARCHAR(500) | 模板文件路径 |
| `price` | FLOAT | 价格（默认 ¥1.99） |
| `is_active` | BOOLEAN | 是否上架 |

**`deliveries` — 交付记录**

| 字段 | 类型 | 说明 |
|------|------|------|
| `order_no` | VARCHAR(32) | 订单号 |
| `file_url` | VARCHAR(500) | 旧字段（兼容） |
| `pdf_key` | VARCHAR(500) | S3 中 PDF 路径 |
| `word_key` | VARCHAR(500) | S3 中 Word 路径 |
| `pdf_filename` | VARCHAR(200) | PDF 原始文件名 |
| `word_filename` | VARCHAR(200) | Word 原始文件名 |
| `pdf_size` | INT | PDF 文件大小（字节） |
| `word_size` | INT | Word 文件大小（字节） |
| `remark` | TEXT | 交付备注 |
| `created_at` | DATETIME | 交付时间 |

> S3 路径规则：`deliveries/YYYY/MM/DD/order_no_filename`

**`reviews` — 买家验收记录**

| 字段 | 类型 | 说明 |
|------|------|------|
| `order_no` | VARCHAR(32) | 订单号 |
| `result` | VARCHAR(20) | `pass` / `reject` |
| `buyer_remark` | TEXT | 买家备注 |

**`order_messages` — 订单聊天消息**

| 字段 | 类型 | 说明 |
|------|------|------|
| `order_id` | INT FK | 订单 |
| `sender_id` | INT | 发送方用户 |
| `content` | TEXT | 消息内容 |
| `attachment_url` | VARCHAR(512) | 附件 URL |
| `msg_type` | VARCHAR(20) | `text` / `image` / `file` / `system` |
| `is_read` | BOOLEAN | 已读标记 |
| `created_at` | DATETIME | 发送时间 |

#### 分佣模块

**`commission_config` — 分佣比例配置**

| 字段 | 类型 | 说明 |
|------|------|------|
| `level` | INT UNIQUE | 级别 (1, 2) |
| `rate` | FLOAT | 分佣比例 |

> 默认：L1 = 30%, L2 = 10%

**`commission_records` — 分佣明细**

| 字段 | 类型 | 说明 |
|------|------|------|
| `order_no` | VARCHAR(32) | 订单号 |
| `user_id` | INT FK | 获佣用户 |
| `level` | INT | 分佣级别 |
| `amount` | FLOAT | 分佣金额 |
| `rate` | FLOAT | 分佣比例 |

**`commission_pending` — 待发放佣金（冻结期管理）**

| 字段 | 类型 | 说明 |
|------|------|------|
| `order_no` | VARCHAR(32) | 订单号 |
| `user_id` | INT FK | 待发放用户 |
| `role_type` | VARCHAR(20) | `creator` / `referrer` |
| `amount` | FLOAT | 冻结金额 |
| `rate` | FLOAT | 冻结比例 |
| `freeze_until` | DATETIME | 冻结到期 |
| `status` | VARCHAR(20) | `pending` / `released` |
| `released_at` | DATETIME | 释放时间 |

#### 制作者模块

**`creator_applications` — 入驻申请**

| 字段 | 类型 | 说明 |
|------|------|------|
| `user_id` | INT FK UNIQUE | 申请人 |
| `real_name` | VARCHAR(50) | 真实姓名 |
| `phone` | VARCHAR(20) | 手机号 |
| `wechat` | VARCHAR(50) | 微信号 |
| `specialty` | VARCHAR(200) | 擅长领域 |
| `portfolio_desc` | TEXT | 作品集描述 |
| `experience` | TEXT | 工作经验 |
| `status` | VARCHAR(20) | `pending` / `approved` / `rejected` |
| `review_remark` | VARCHAR(500) | 审核备注 |

**`creator_audit_log` — 制作者审计日志**

| 字段 | 类型 | 说明 |
|------|------|------|
| `user_id` | INT FK | 制作者 |
| `order_no` | VARCHAR(32) | 相关订单 |
| `action` | VARCHAR(50) | 操作类型 |
| `detail` | TEXT | 详情（JSON） |
| `penalty_amount` | FLOAT | 违约金金额 |

> `action` 枚举：`penalty_deducted`, `order_republished`, `cycle_reset`, `creator_exit_success`, `creator_exit_forced`, `admin_intervened`

#### 财务模块

**`withdraw_requests` — 提现申请**

| 字段 | 类型 | 说明 |
|------|------|------|
| `user_id` | INT FK | 申请人 |
| `amount` | FLOAT | 提现金额 |
| `payment_info` | VARCHAR(200) | 收款信息 |
| `account_type` | VARCHAR(20) | `alipay` / `wechat` |
| `status` | VARCHAR(20) | `pending` / `approved` / `rejected` |
| `transfer_proof` | VARCHAR(200) | 转账凭证 |
| `admin_remark` | VARCHAR(500) | 审核备注 |

**`refund_requests` — 退款申请**

| 字段 | 类型 | 说明 |
|------|------|------|
| `order_no` | VARCHAR(32) | 订单号 |
| `buyer_id` | INT | 买家 |
| `creator_id` | INT | 制作者 |
| `refund_amount` | FLOAT | 平台退款额 |
| `creator_deduction` | FLOAT | 制作者扣款额 |
| `reason` | TEXT | 退款原因 |
| `status` | VARCHAR(20) | `pending` / `approved` / `rejected` |

**`recharge_records` — 充值记录**

| 字段 | 类型 | 说明 |
|------|------|------|
| `user_id` | INT FK | 用户 |
| `amount` | FLOAT | 充值金额 |
| `method` | VARCHAR(20) | `manual` / `payjs` |
| `status` | VARCHAR(20) | `pending` / `completed` / `failed` |

#### 系统模块

**`system_config` — 系统配置（后台可改）**

| 字段 | 类型 | 说明 |
|------|------|------|
| `key` | VARCHAR(50) UNIQUE | 配置键 |
| `value` | FLOAT | 配置值 |
| `description` | VARCHAR(200) | 说明 |

---

## 四、业务流程设计

### 4.1 定制订单状态机

```
                    ┌─────────────────────────────────────┐
                    │           买家下单 + 支付             │
                    └──────────────┬──────────────────────┘
                                   ▼
┌──────────────────┐      ┌──────────────────┐     ┌──────────────────┐
│    pending       │─────▶│      paid        │─────▶│ awaiting_claim   │
│     待支付        │      │     已支付        │     │     待抢单        │
└──────────────────┘      └──────────────────┘     └────────┬─────────┘
                                   ▲                        │
                                   │                   制作者抢单
                                   │                        │
                                   │                        ▼
                                   │               ┌──────────────────┐
                                   │               │     claimed      │
                                   │               │────▶ in_progress  │
                                   │               │     已抢单        │
                                   │               │     制作中(24h)   │
                                   │               └────────┬─────────┘
                                   │                        │
                                   │                   制作者交付
                                   │                        │
                                   │                        ▼
                                   │               ┌──────────────────┐
                                   │               │    delivered     │
                                   │               │    已交付         │
                                   │               │  等待买家验收(7d)  │
                                   │               └──────┬──────┬─────┘
                                   │                      │      │
                              退款  │                  通过   拒绝
                                   │                      │      │
                                   ▼                      ▼      ▼
                            ┌───────────┐         ┌──────────┐ ┌──────────┐
                            │ refunded  │         │ accepted │ │ rejected │
                            │   已退款   │         │ 买家确认  │ │  买家拒绝 │
                            └───────────┘         └────┬─────┘ │ 退回制作  │
                                                       │       └────┬─────┘
                                                       │            │
                                                       ▼            │
                                                ┌──────────┐        │
                                                │ completed │        │
                                                │  已完成    │◀───────┘
                                                │ (佣金发放) │
                                                └──────────┘
```

### 4.2 定制订单完整流程

```
买家                          平台                        制作者
 │                             │                             │
 │  ① 选择模板 + 填写需求       │                             │
 │────────────────────────────▶│                             │
 │  ② 支付 ¥19.99              │                             │
 │────────────────────────────▶│                             │
 │                             │  ③ 发布到众包大厅            │
 │                             │─────────────────────────────▶│
 │                             │                             │  ④ 看到可抢订单
 │                             │                             │
 │                             │  ⑤ 抢单 + 冻结保证金 ¥20     │
 │                             │◀────────────────────────────│
 │                             │                             │
 │                             │  ⑥ 开始制作 (24h 倒计时)     │
 │                             │─────────────────────────────▶│
 │                             │                             │
 │                             │  ⑦ 上传交付文件 (PDF+Word)   │
 │                             │◀────────────────────────────│
 │  ⑧ 收到交付通知              │                             │
 │◀────────────────────────────│                             │
 │                             │                             │
 │  ⑨ 验收（通过/拒绝）         │                             │
 │────────────────────────────▶│                             │
 │                             │                             │
 │  ⑩ 通过 → 佣金冻结 → 释放   │  ⑩ 通过 → 佣金冻结 → 释放   │
 │                             │                             │
 │  ⑪ 拒绝 → 退回制作者重做    │                             │
 │                             │─────────────────────────────▶│
```

### 4.3 分佣体系设计

#### 分佣类型

| 类型 | 触发条件 | 次数 | 推广链归属 | L1 本人 | L2 上级 |
|------|---------|------|-----------|---------|---------|
| **推荐分佣** | 用户首次下单 | 一次性 | 下单用户的推广链 | 30% | 10% |
| **订单分佣**（定制） | 非首单定制订单 | 无限次 | 制作者的推广链 | 30% | 10% |
| **订单分佣**（下载） | 非首单下载订单 | 无限次 | 下单用户的推广链 | 30% | 10% |

> ⚠️ 首单互斥规则：用户首次下单只走推荐分佣，不触发订单分佣。
> 原三级推广 (level3_rate = 5%) 已停用，归平台所有。

#### 推广链计算

```
用户 A (被推广)
  └── 上级 B (L1, 30%)
        └── 上上级 C (L2, 10%)
```

推广链从被推广人的 `parent_id` 向上追溯，最多 2 级。

#### 佣金冻结机制

订单验收通过后，佣金不立即发放，而是进入 `commission_pending` 冻结期：

| 角色 | 冻结期 | 说明 |
|------|--------|------|
| 制作者 | 7 天 | 等待买家确认 |
| 推广人 | 7 天 | 同上 |

冻结期到期后自动释放到钱包余额。

### 4.4 违约金规则

| 阶段 | 时间 | 规则 |
|------|------|------|
| 正常交付期 | 接单后 0-24h | 无惩罚 |
| 首次违约 | 接单后 32h | 扣保证金 10% |
| 持续违约 | 每超 8h | 再扣 10% |
| 违约金上限 | — | 累计不超过订单金额 50% |
| 严重超时 | 接单后 72h | 订单重新发布到众包大厅 |
| 连续超时 | 累计 3 次 | 暂停接单权限 |

违约金从制作者 `wallet_balance` 中扣除，不足则扣至 0。

### 4.5 退款流程

```
买家申请退款                    管理员审核
      │                             │
      │  提交退款申请                │
      │────────────────────────────▶│
      │                             │
      │                             │  判断退款分配：
      │                             │    平台承担部分 + 制作者扣款
      │                             │
      │                    ┌────────┴────────┐
      │                    │                 │
      │               批准退款           拒绝退款
      │                    │                 │
      │◀───────────────────│                 │
      │  退款到账           │                 │
      │                    │                 │
      │                    │◀────────────────│
      │                    │   通知结果       │
```

退款金额分配：
- `refund_amount`: 平台承担的退款额
- `creator_deduction`: 从制作者保证金中扣除

---

## 五、API 设计

### 5.1 路由分层

```
/api/v1/
├── auth/           — 认证路由
├── user/           — 用户路由
├── creator/        — 制作者路由
├── orders/         — 订单路由
├── templates/      — 模板路由
├── ws/             — WebSocket 路由
└── admin/          — 后台管理路由
    ├── dashboard/  — 仪表盘
    ├── users/      — 用户管理
    ├── orders/     — 订单管理
    ├── applications/ — 入驻审核
    ├── withdrawals/ — 提现审核
    ├── refunds/    — 退款审核
    ├── audit/      — 审计日志
    ├── commission/ — 分佣管理
    └── config/     — 系统配置
```

### 5.2 认证机制

- **JWT Token**：24 小时有效期，HttpOnly Cookie / Authorization Header
- **密码存储**：bcrypt 哈希 (passlib)
- **路由守卫**：
  - `requires_auth`: 检查 Token 有效性
  - `requires_creator`: 检查 role = creator
  - `requires_admin`: 检查 role = admin

### 5.3 WebSocket 聊天

连接地址：`ws://host/api/v1/ws/chat/{order_id}`

消息协议：

```json
{
  "type": "text",
  "content": "消息内容",
  "sender_id": 123,
  "timestamp": "2026-07-16T12:00:00"
}
```

消息类型：`text`, `image`, `file`, `system`

所有消息持久化到 `order_messages` 表，作为纠纷仲裁依据。

---

## 六、安全设计

### 6.1 认证与授权

| 层级 | 措施 |
|------|------|
| 传输 | HTTPS (生产环境) |
| 认证 | JWT 24h 有效期，定期轮换 JWT_SECRET |
| 密码 | bcrypt 哈希，不可逆 |
| 权限 | 路由级 role 检查 (user/creator/admin) |
| CSRF | CORS 白名单限制 |

### 6.2 数据安全

| 项目 | 措施 |
|------|------|
| 敏感配置 | 环境变量，不入库 |
| 数据库 | PostgreSQL 连接池，参数化查询 |
| 文件上传 | 类型白名单 (.pdf, .docx)，大小限制 10MB |
| 支付回调 | 签名验证 (PayJS MD5) |

### 6.3 审计

所有制作者操作记录到 `creator_audit_log`：
- 违约金扣款
- 订单重新发布
- 制作者退出
- 管理员干预

---

## 七、定时任务

APScheduler 在应用启动时自动注册：

| 任务 | 频率 | 触发器 | 说明 |
|------|------|--------|------|
| `check_delivery_penalties` | 每 30 分钟 | interval | 检查超时订单，按 8h 周期扣违约金，72h 重新发布 |
| `auto_accept_orders` | 每 1 小时 | interval | 冻结期到期的 delivered 订单自动验收 |
| `release_frozen_commissions` | 每 1 小时 | interval | 释放冻结期到期的佣金到钱包 |

---

## 八、部署架构

### 8.1 Docker Compose (生产)

```yaml
services:
  api:
    build: ./backend
    ports: ["8000:8000"]
    depends_on: [db]
    volumes: [./assets:/app/assets]
    environment:
      - DATABASE_URL=postgresql://...
      - JWT_SECRET=...
      - PAYJS_MCHID=...
      - S3_ENDPOINT=...

  db:
    image: postgres:15-alpine
    volumes: [pgdata:/var/lib/postgresql/data]

  frontend:
    image: node:20-alpine
    ports: ["5173:5173"]
    volumes: [./frontend:/app]
```

### 8.2 外部依赖

| 服务 | 用途 | 替代方案 |
|------|------|---------|
| PostgreSQL 15 | 主数据库 | SQLite (开发) |
| S3 兼容存储 | 交付文件存储 | 本地文件系统 |
| PayJS | 微信支付 Native | 模拟支付 (未配置时) |

---

## 九、前端页面结构

### 9.1 路由与页面

| 路由 | 页面 | 权限 | 说明 |
|------|------|------|------|
| `/` | ResumeList | 公开 | 模板列表（首页） |
| `/login` | Login | 公开 | 账号密码登录 |
| `/register` | Register | 公开 | 注册 |
| `/auth/callback/:provider` | OAuthCallback | 公开 | 第三方登录回调 |
| `/crowd` | CrowdHall | 登录 | 众包大厅 |
| `/creator` | CreatorCenter | 登录 | 制作者中心 |
| `/user` | UserCenter | 登录 | 用户中心 |
| `/my-orders` | MyCustomOrders | 登录 | 我的定制订单 |
| `/chat/:order_id` | OrderChat | 登录 | 订单聊天 |
| `/admin` | AdminPanel | admin | 后台管理 |

### 9.2 Tabbar 底部导航

```
首页 | 众包大厅 | 我的定制订单 | 制作者中心 | 用户中心
```

### 9.3 后台管理子页面

| 子页面 | 组件 | 功能 |
|--------|------|------|
| 仪表盘 | AdminDashboard | 统计概览（用户/订单/收入） |
| 用户管理 | AdminUsers | 用户列表/角色修改/余额调整 |
| 订单管理 | AdminOrders | 订单查询/状态修改 |
| 入驻审核 | AdminApplications | 入驻申请审批 |
| 提现审核 | AdminWithdrawals | 提现审批/转账凭证上传 |
| 退款审核 | AdminRefunds | 退款审批 |
| 审计日志 | AdminAuditLogs | 制作者操作记录查询 |
| 系统设置 | AdminSettings | 分佣比例/保证金/提现门槛配置 |

### 9.4 状态管理

Pinia Store: `auth.js`

```javascript
{
  token: string | null,      // JWT Token
  user: Object | null,       // 用户信息
  isLoggedIn: boolean,       // 登录态
  login(token, user) {},     // 登录
  logout() {},               // 退出
  fetchProfile() {},         // 获取个人信息
}
```

---

## 十、配置管理

### 10.1 环境变量

| 变量 | 必填 | 默认 | 说明 |
|------|------|------|------|
| `DATABASE_URL` | ✅ | `sqlite:///./resume_dev.db` | 数据库连接字符串 |
| `JWT_SECRET` | ✅ | `resume-platform-dev-secret-change-in-prod` | JWT 签名密钥 |
| `ASSETS_DIR` | — | `/root/assets` | 模板素材目录 |
| `PAYJS_MCHID` | — | *(空=模拟支付)* | PayJS 商户号 |
| `PAYJS_KEY` | — | *(空=模拟支付)* | PayJS API 密钥 |
| `PAYJS_NOTIFY_URL` | — | *(空)* | 支付回调地址 |
| `S3_ENDPOINT` | — | *(空)* | S3 兼容服务地址 |
| `S3_ACCESS_KEY` | — | *(空)* | S3 访问密钥 |
| `S3_SECRET_KEY` | — | *(空)* | S3 密钥 |
| `S3_BUCKET` | — | `resume-deliveries` | S3 存储桶名 |
| `S3_REGION` | — | `us-east-1` | S3 区域 |

### 10.2 系统配置（数据库可改）

通过后台管理 `/api/v1/admin/config/*` 动态调整：

| 配置键 | 默认值 | 说明 |
|--------|--------|------|
| `deposit_amount` | 20.00 | 制作者保证金 |
| `min_withdraw` | 50.00 | 最低提现金额 |
| `download_price` | 1.99 | 模板下载价格 |
| `custom_price` | 19.99 | 定制订单价格 |
| `level1_rate` | 0.30 | L1 分佣比例 |
| `level2_rate` | 0.10 | L2 分佣比例 |
| `auto_accept_days` | 7 | 自动验收天数 |
| `delivery_url_expires` | 172800 | 下载链接有效期（秒） |

---

## 十一、关键阈值

| 参数 | 值 | 说明 |
|------|-----|------|
| 模板下载价 | ¥1.99 | 可后台调整 |
| 定制订单价 | ¥19.99 | 可后台调整 |
| 保证金 | ¥20 | 制作者抢单时冻结 |
| 最低提现 | ¥50 | 钱包余额门槛 |
| JWT 有效期 | 24h | Token 过期自动刷新 |
| 正常交付期 | 24h | 接单后 24h 内交付 |
| 违约金周期 | 8h | 每超 8h 扣 10% |
| 违约金上限 | 50% | 累计不超过订单金额 50% |
| 严重超时 | 72h | 订单重新发布 |
| 连续超时暂停 | 3 次 | 暂停接单权限 |
| 自动验收 | 7 天 | 买家不操作自动通过 |
| L1 分佣 | 30% | 本人/直接上级 |
| L2 分佣 | 10% | 间接上级 |
| 文件上传限制 | 10MB | 单个文件最大 |
| 下载链接有效期 | 48h | 可后台调整 |

---

## 十二、版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v0.11.0 | 2026-07-16 | Alembic 迁移系统、Admin 后台子路由拆分、Admin 前端独立组件、Docker 优化 |
| v0.10.2 | — | 角标功能、我的定制订单独立 Tab |
| v0.10.1 | — | 路由拆分版初始化 |
| v0.9.x | — | 早期版本（单体 main.py） |
