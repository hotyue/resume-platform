# Admin 后端拆分对比报告 (v0.10.1 → v0.10.2)

对比基线：commit `2704e8c^` 拆分前 → 当前 `backend/routers/admin/` 拆分后代码

---

## 1. GET /api/v1/admin/applications (入驻申请列表)

| 对比项 | 拆分前 (main.py:829) | 拆分后 (applications.py:14) | 是否一致 |
|--------|---------------------|---------------------------|---------|
| 查询参数 | `status`, `page`, `page_size` | **仅 `status`** — 缺少 `page` 和 `page_size` | ❌ **不一致** |
| 分页逻辑 | 有 (`offset/limit`) | **无分页** — 返回全部结果 `.all()` | ❌ **不一致** |
| 返回格式 | `{"total", "page", "page_size", "applications": [...]}` | **扁平列表** `[...]` — 无 total/page/page_size 包装 | ❌ **不一致** |
| 返回字段 | id, user_id, username, real_name, phone, wechat, specialty, portfolio_desc, experience, status, created_at, review_remark, reviewed_at | 同拆分前 | ✅ 一致 |
| 排序 | `created_at desc` | `created_at desc` | ✅ 一致 |

---

## 2. POST /api/v1/admin/applications/review (审核入驻申请)

| 对比项 | 拆分前 (main.py:847) | 拆分后 (applications.py:36) | 是否一致 |
|--------|---------------------|---------------------------|---------|
| 请求体字段名 | `request_id` | **`application_id`** ⚠️ 字段名不同 | ❌ **不一致** |
| 请求体类型 | Pydantic `ReviewApplicationReq` | 原始 `dict` | ❌ **不一致** |
| 审批通过逻辑 | `pass` (无操作) | **`user.deposit_frozen = 0.0`** (解冻保证金) | ❌ **不一致** |
| 返回格式 | `{"id", "status"}` | `{"id", "status", "message": "审核完成"}` | ❌ **不一致** |
| 错误提示 | `"已处理"` | `"该申请已处理（当前状态: {a.status}）"` | ❌ **不一致** |

---

## 3. GET /api/v1/admin/orders (订单列表)

| 对比项 | 拆分前 (main.py:867) | 拆分后 (orders.py:14) | 是否一致 |
|--------|---------------------|---------------------|---------|
| 查询参数 | `status`, `search`, `page`, `page_size` | 同拆分前 + `page_size` 有 `ge=1, le=100` 校验 | ✅ 一致 |
| 分页逻辑 | 有 (`offset/limit`) | 同拆分前 | ✅ 一致 |
| 返回字段 | id, order_no, amount, status, order_type, template_name, user_name, creator_id, created_at | 同拆分前 **+** `template_category`, `ref_user_id` | ⚠️ **扩展** (新增字段，非缺失) |
| 排序 | `created_at desc` | 同拆分前 | ✅ 一致 |

---

## 4. GET /api/v1/admin/orders/{order_no} (订单详情)

| 对比项 | 拆分前 (main.py:889) | 拆分后 (orders.py:53) | 是否一致 |
|--------|---------------------|---------------------|---------|
| 返回 `refunds` 数组 | 有 (id, refund_amount, creator_deduction, reason, status, created_at) | **缺失** ❌ | ❌ **不一致** |
| 返回 `order.commission_distributed` | 有 | **缺失** ❌ | ❌ **不一致** |
| 返回 `order.custom_requirements` | 有 | 有 | ✅ 一致 |
| 返回 `template` 字段 | `id, name` | **`id, name, category`** (新增) | ⚠️ 扩展 |
| 返回 `user` 字段 | `id, username` | **`id, username, role`** (新增) | ⚠️ 扩展 |
| 返回 `commission` 字段 | `user_id, level, amount` | **`id, user_id, level, amount, rate`** (新增) | ⚠️ 扩展 |
| `user` 查询 | `if order.user_id else None` | `db.query().first()` (无 None 保护) | ❌ **不一致** |

---

## 5. GET /api/v1/admin/withdrawals (提现列表)

| 对比项 | 拆分前 (main.py:919) | 拆分后 (withdrawals.py:15) | 是否一致 |
|--------|---------------------|--------------------------|---------|
| 查询参数 | `status`, `page`, `page_size` | 同拆分前 + `page_size` 有 `ge=1, le=100` 校验 | ✅ 一致 |
| 返回字段 | id, user_id, username, amount, payment_info, account_type, status, transfer_proof, created_at | 同拆分前 **+** `admin_remark`, `reviewed_at` | ⚠️ 扩展 |
| 分页逻辑 | 有 | 有 | ✅ 一致 |

---

## 6. POST /api/v1/admin/withdrawals/review (审核提现)

| 对比项 | 拆分前 (main.py:937) | 拆分后 (withdrawals.py:43) | 是否一致 |
|--------|---------------------|--------------------------|---------|
| 请求体类型 | Pydantic `ReviewWithdrawReq` | 原始 `dict` | ❌ **不一致** |
| 请求体字段 | `request_id`, `status`, `remark`, `transfer_proof` | 同拆分前 | ✅ 一致 |
| 批准逻辑 | 扣余额 + 解冻 + 累加 total_withdrawn | 同拆分前 | ✅ 一致 |
| 拒绝逻辑 | 解冻 (frozen_withdraw) | 同拆分前 | ✅ 一致 |
| 返回格式 | `{"id", "status"}` | `{"id", "status", "message": "审核完成"}` | ❌ **不一致** |

---

## 7. GET /api/v1/admin/commission-config (分佣配置旧接口)

| 对比项 | 拆分前 (main.py:966) | 拆分后 | 是否一致 |
|--------|---------------------|-------|---------|
| 端点存在 | ✅ 存在，返回 `load_all_configs(db)` | **❌ 完全缺失** — 该端点已删除 | ❌ **不一致** |

---

## 8. PUT /api/v1/admin/commission-config (更新分佣配置旧接口)

| 对比项 | 拆分前 (main.py:971) | 拆分后 | 是否一致 |
|--------|---------------------|-------|---------|
| 端点存在 | ✅ 存在，验证 level 1/2，更新分佣比例 | **❌ 完全缺失** — 该端点已删除 | ❌ **不一致** |

---

## 9. GET /api/v1/admin/config (系统配置)

| 对比项 | 拆分前 (main.py:989) | 拆分后 (config.py:43) | 是否一致 |
|--------|---------------------|---------------------|---------|
| 返回数据 | 8 个键: download_price, custom_price, creator_rate, level1/2/3_rate, deposit_amount, auto_accept_hours | **15 个键** (新增 delivery_hours, penalty_hours, penalty_rate, penalty_max, consecutive_fail_limit, min_withdraw, deposit_threshold) | ⚠️ **扩展** |
| auto_accept_hours 默认值 | 168 | 168 | ✅ 一致 |
| level3_rate 默认值 | 0.00 | 0.05 | ❌ **不一致** |
| 配置自动创建 | 调用 `get_config()` 自动创建带 description 的配置 | 用 `DEFAULT_CONFIGS` 回退但不自动创建数据库记录 | ❌ **不一致** |

---

## 10. PUT /api/v1/admin/config (更新系统配置) ⚠️ 关键安全差异

| 对比项 | 拆分前 (main.py:994) | 拆分后 (config.py:55) | 是否一致 |
|--------|---------------------|---------------------|---------|
| valid_keys 白名单 | ✅ 有: 8 个固定键名 | ✅ 有: `list(DEFAULT_CONFIGS.keys())` 15 个键名 | ✅ 一致 (白名单扩大) |
| auto_accept_hours 范围校验 | ✅ 24-720 小时 | ✅ 24-720 小时 | ✅ 一致 |
| 值 ≥ 0 校验 | ✅ `elif req.value < 0` | ✅ `if float(value) < 0` | ✅ 一致 |
| `updated_at` 更新 | ✅ `cfg.updated_at = datetime.now()` | ✅ `config.updated_at = datetime.now()` | ✅ 一致 |
| 请求体类型 | Pydantic `UpdateSystemConfigReq` (key: str, value: float) | 原始 `dict` | ❌ **不一致** |
| 返回格式 | `{"key", "value", "message": "配置已更新"}` | 同拆分前 | ✅ 一致 |

---

## 11. GET /api/v1/config/public (公开配置，无需认证)

| 对比项 | 拆分前 (main.py:1015) | 拆分后 | 是否一致 |
|--------|---------------------|-------|---------|
| 端点存在 | ✅ 存在，返回 `{"creator_rate", "deposit_amount"}` | **❌ 完全缺失** — 前端依赖此接口展示公开配置 | ❌ **不一致** |

---

## 12. GET /api/v1/admin/refunds (退款列表)

| 对比项 | 拆分前 (main.py:1024) | 拆分后 (refunds.py:15) | 是否一致 |
|--------|---------------------|----------------------|---------|
| 查询参数 | `status`, `page`, `page_size` | 同拆分前 | ✅ 一致 |
| 返回格式 | `{"total", "page", "page_size", "refunds": [...]}` | 同拆分前 | ✅ 一致 |
| 返回字段 | id, order_no, buyer, creator, refund_amount, creator_deduction, reason, status, created_at | 同拆分前 | ✅ 一致 |
| 业务逻辑 | 查询 RefundRequest + 关联 User | 同拆分前 | ✅ 一致 |

---

## 13. POST /api/v1/admin/refunds/review (审核退款)

| 对比项 | 拆分前 (main.py:1044) | 拆分后 (refunds.py:42) | 是否一致 |
|--------|---------------------|----------------------|---------|
| 请求体字段 | `refund_id`, `status`, `remark` | 同拆分前 | ✅ 一致 |
| 请求体类型 | Pydantic `ReviewRefundReq` | 原始 `dict` | ❌ **不一致** |
| 批准逻辑 | 订单状态 → refunded, 买家余额 + refund_amount, 制作者余额 - creator_deduction | 同拆分前 | ✅ 一致 |
| 返回格式 | `{"id", "status"}` | `{"id", "status"}` | ✅ 一致 |

---

## 14. GET /api/v1/admin/users (用户列表)

| 对比项 | 拆分前 (main.py:1075) | 拆分后 (users.py:14) | 是否一致 |
|--------|---------------------|--------------------|---------|
| 查询参数 | `search`, `role`, `page`, `page_size` | 同拆分前 (参数顺序交换) | ✅ 一致 |
| 默认 page_size | **50** | **20** | ❌ **不一致** |
| 排序 | `m.User.id` **升序** | `m.User.id.desc()` **降序** | ❌ **不一致** |
| 返回 `deposit_frozen` 字段 | **有** (round) | **缺失** ❌ | ❌ **不一致** |
| 返回 `parent_id` 字段 | **有** | **缺失** ❌ | ❌ **不一致** |
| 返回 `wallet_balance` | **round(u.wallet_balance, 2)** | **原始值** (未四舍五入) | ❌ **不一致** |
| 返回 `team_size` | 有 | 有 | ✅ 一致 |
| 返回 `created_at` | `str(u.created_at) if u.created_at else "N/A"` | `str(u.created_at)` (无 N/A 回退) | ❌ **不一致** |

---

## 15. PUT /api/v1/admin/users/{user_id} (更新用户) ⚠️ 安全差异

| 对比项 | 拆分前 (main.py:1088) | 拆分后 (users.py:41) | 是否一致 |
|--------|---------------------|--------------------|---------|
| 请求体类型 | Pydantic `UpdateUserReq` | 原始 `dict` | ❌ **不一致** |
| role 校验 | ✅ **只允许 "user" 或 "admin"** | ❌ **无校验** — 任意字符串均可设置 | ❌ **不一致** |
| wallet_balance >= 0 校验 | ✅ **有** | ❌ **无校验** — 可设负值 | ❌ **不一致** |
| 返回格式 | `{"id", "role", "wallet_balance"}` (round) | `{"id", "username", "role", "wallet_balance"}` (未round) | ❌ **不一致** |

---

## 16. GET /api/v1/admin/audit-logs (审计日志)

| 对比项 | 拆分前 (main.py:1098) | 拆分后 (audit.py:14) | 是否一致 |
|--------|---------------------|--------------------|---------|
| 查询参数 | `user_id`, `order_no`, `action`, `page`, `page_size` | **缺少 `order_no`** 查询参数 ❌ | ❌ **不一致** |
| 默认 page_size | **50** | **20** | ❌ **不一致** |
| 返回字段 | id, user_id, order_no, action, detail, penalty_amount, created_at (isoformat) | 同拆分前 | ✅ 一致 |
| 返回格式 | `{"logs": [...], "total": total}` | 同拆分前 | ✅ 一致 |

---

## 17. GET /api/v1/admin/dashboard (仪表盘)

| 对比项 | 拆分前 (main.py:1115) | 拆分后 (dashboard.py:15) | 是否一致 |
|--------|---------------------|------------------------|---------|
| total_users | ✅ 有 | ✅ 有 | ✅ 一致 |
| total_orders | ✅ 有 | ✅ 有 | ✅ 一致 |
| total_revenue | ✅ 有 (round) | ✅ 有 (round) | ✅ 一致 |
| today_orders | ✅ 有 | ✅ 有 | ✅ 一致 |
| today_revenue | ✅ 有 (round) | ✅ 有 (round) | ✅ 一致 |
| month_orders | ✅ 有 | ✅ 有 | ✅ 一致 |
| month_revenue | ✅ 有 (round) | ✅ 有 (round) | ✅ 一致 |
| total_commission_paid | ✅ 有 (round) | ✅ 有 (round) | ✅ 一致 |
| pending_orders | ✅ 有 | ✅ 有 | ✅ 一致 |
| pending_withdrawals | ✅ 有 | ✅ 有 | ✅ 一致 |
| pending_applications | ✅ 有 | ✅ 有 | ✅ 一致 |
| pending_refunds | ✅ 有 | ✅ 有 | ✅ 一致 |
| role_stats | ✅ 有 (user, admin, creator, promoter) | ✅ 有 | ✅ 一致 |
| order_status_stats | ✅ 有 | ✅ 有 | ✅ 一致 |
| daily_trend | ✅ 有 (7天) | ✅ 有 (7天) | ✅ 一致 |

---

## 18. GET /api/v1/admin/stats (数据概览)

| 对比项 | 拆分前 (main.py:1170) | 拆分后 (dashboard.py:65) | 是否一致 |
|--------|---------------------|------------------------|---------|
| 所有字段 | total_users, creator_count, promoter_count, pending_approvals, total_revenue, total_commission, pending_withdrawals | 同拆分前 | ✅ 一致 |

---

## 19. 新端点: POST /api/v1/admin/commission/release-frozen

拆分后新增的端点，拆分前无对应端点（此功能在拆分前由定时任务 `_delivery_check_loop` 处理）。

| 对比项 | 拆分前 | 拆分后 (commission.py:14) | 是否一致 |
|--------|-------|-------------------------|---------|
| 端点存在 | ❌ 无 | ✅ 新增 | ⚠️ 新增功能 |

---

## 差异汇总

### 功能缺失 (拆分前有，拆分后丢失)

| # | 端点 | 缺失内容 |
|---|------|---------|
| 1 | GET /applications | **分页功能** — 无 page/page_size 参数，返回全部结果 |
| 2 | GET /orders/{order_no} | **`refunds` 数组** — 不返回关联退款记录 |
| 3 | GET /orders/{order_no} | **`commission_distributed`** 字段 |
| 4 | GET /commission-config | **整个端点缺失** |
| 5 | PUT /commission-config | **整个端点缺失** |
| 6 | GET /config/public | **整个端点缺失** — 前端无法获取公开配置项 |
| 7 | GET /users | **`deposit_frozen`** 字段 |
| 8 | GET /users | **`parent_id`** 字段 |
| 9 | GET /audit-logs | **`order_no` 查询参数** — 无法按订单号筛选日志 |

### 行为不一致 (拆分前 vs 拆分后逻辑不同)

| # | 端点 | 差异 |
|---|------|------|
| 1 | POST /applications/review | 字段名 `request_id` → `application_id` (**BREAKING**) |
| 2 | POST /applications/review | 审批通过不再 `pass`，改为 `user.deposit_frozen = 0.0` |
| 3 | GET /users | 排序从 `id ASC` → `id DESC` (**BREAKING**) |
| 4 | GET /users | 默认 page_size 从 50 → 20 |
| 5 | GET /audit-logs | 默认 page_size 从 50 → 20 |
| 6 | PUT /users/{user_id} | **无角色校验** — 可设置任意角色值 (原限制为 "user"/"admin") |
| 7 | PUT /users/{user_id} | **无余额 >= 0 校验** — 可设置负余额 |
| 8 | PUT /users/{user_id} | 返回新增 `username` 字段，wallet_balance 不再 round |
| 9 | GET /users | wallet_balance 不再 round |
| 10 | GET /users | created_at 不再有 N/A 回退 |
| 11 | GET /config | level3_rate 默认值从 0.00 变为 0.05 |

### 请求体类型退化 (Pydantic → 原始 dict)

下列端点从类型安全的 Pydantic model 退化为原始 `dict` 解析，丧失类型校验和自动文档生成：

- POST /applications/review
- POST /withdrawals/review
- POST /refunds/review
- PUT /config
- PUT /users/{user_id}

### 返回值格式差异

| # | 端点 | 差异 |
|---|------|------|
| 1 | GET /applications | 返回扁平列表而非 `{"total", "page", "page_size", "applications"}` |
| 2 | POST /applications/review | 新增 `message: "审核完成"` 字段 |
| 3 | POST /withdrawals/review | 新增 `message: "审核完成"` 字段 |
| 4 | GET /withdrawals | 新增 `admin_remark`, `reviewed_at` 字段 |
| 5 | GET /orders/{order_no} | commission 新增 `id`, `rate` 字段；template 新增 `category` 字段；user 新增 `role` 字段 |

### 安全风险

| # | 风险描述 |
|---|---------|
| 1 | **PUT /users/{user_id} 缺少角色校验** — 可设置任意角色值，包括不存在的角色 |
| 2 | **PUT /users/{user_id} 缺少余额校验** — 可设置负值，导致系统负债 |
| 3 | **PUT /config 不再使用 Pydantic** — value 类型从 float 变为任意类型 |
| 4 | **POST /applications/review 字段名变更** — 前端需适配 `request_id` → `application_id` |