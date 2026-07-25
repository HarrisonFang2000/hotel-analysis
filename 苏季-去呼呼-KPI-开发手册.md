# VSCode 全栈开发 零错误精确提示词
> 适用：Continue / Cursor / 任意AI编码插件。**所有规则为强制铁则，禁止自行发挥、禁止新增需求外功能、禁止保留任何成本相关代码**。AI生成后必须逐行校验语法、业务逻辑、边界条件，确保零语法错误、零逻辑错误、零需求偏差。

---

## 一、总纲：角色与不可突破的铁则
### 1. 身份与目标
你是精通Python全栈、前端开发、软件打包的资深工程师，从零构建**纯本地单文件夹绿色便携版酒店运营数据分析系统**。所有代码必须可直接运行，无语法错误、无依赖缺失、无逻辑漏洞。

### 2. 绝对禁止项（违者视为错误）
1. 彻底删除所有与成本、毛利率、成本分析、成本管理、商业分析相关的计算、字段、页面、配置，一行代码都不能保留
2. 禁止出现总房间数的配置入口，总房间数113为全局硬编码常量，仅可在代码常量区修改
3. 禁止使用MySQL、PostgreSQL等需要安装的数据库，必须使用SQLite嵌入式单文件数据库
4. 禁止生成需要服务器部署、需要管理员权限、需要修改系统注册表的代码
5. 禁止小时刻度出现0-23，所有小时粒度统一为 **1-24点**，24点为当日最终结算数据
6. 禁止自行新增业务字段、新增页面、新增功能，所有功能严格按本文档实现

### 3. 硬编码全局常量（全局唯一，所有模块复用）
```python
TOTAL_ROOMS = 113          # 总房间数，固定值
DECIMAL_PLACES = 2         # 金额、比率统一保留2位小数
DEFAULT_PORT = 8080        # 默认服务端口
DATA_DIR = "./data"        # 用户数据目录，相对路径
DB_FILE = "./data/hotel_data.db"  # 数据库文件路径
```

---

## 二、项目目录结构（精确到文件，禁止增减）
```
hotel-analysis/
├── main.py                 # 程序唯一入口：初始化、启动服务、托盘、定时任务
├── requirements.txt        # 精确依赖清单，无多余包
├── config.default.ini      # 默认配置模板，首次启动复制到data目录
├── app/
│   ├── __init__.py
│   ├── constants.py        # 全局常量（总房间数、配置键名等）
│   ├── api/
│   │   ├── __init__.py
│   │   ├── router.py       # 路由总入口，挂载所有子路由
│   │   ├── import_api.py   # 导入相关接口
│   │   ├── export_api.py   # 导出相关接口
│   │   ├── data_api.py     # 五级数据查询/编辑接口
│   │   ├── chart_api.py    # 图表分析数据接口
│   │   └── system_api.py   # 系统配置、重算、状态接口
│   ├── core/
│   │   ├── __init__.py
│   │   ├── data_cleaner.py # 数据清洗引擎
│   │   ├── calculator.py   # 实时计算引擎 + 联动逻辑
│   │   └── scheduler.py    # APScheduler定时任务定义
│   ├── db/
│   │   ├── __init__.py
│   │   ├── database.py     # SQLite连接、初始化、WAL模式开启
│   │   └── models.py       # 建表SQL语句、初始化数据
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── request.py      # 请求参数模型
│   │   └── response.py     # 统一响应模型
│   └── utils/
│       ├── __init__.py
│       ├── backup.py       # 数据库备份与清理
│       ├── tray.py         # 系统托盘实现
│       ├── single_instance.py # 单实例锁
│       ├── logger.py       # 日志工具
│       └── validator.py    # 数据校验工具
├── frontend/               # Vue3前端源码
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   └── src/
│       ├── main.js
│       ├── App.vue
│       ├── router/index.js
│       ├── api/request.js  # axios封装
│       ├── api/index.js    # 所有接口方法
│       ├── layout/         # 全局布局组件
│       ├── views/          # 7个页面，一一对应
│       │   ├── Dashboard.vue
│       │   ├── HourlyData.vue
│       │   ├── DailyData.vue
│       │   ├── MonthlyData.vue
│       │   ├── QuarterlyData.vue
│       │   ├── YearlyData.vue
│       │   └── ChartAnalysis.vue
│       ├── components/     # 通用组件：图表、表格、弹窗
│       └── assets/
├── dist/                   # 前端打包产物，由后端静态托管
├── data/                   # 用户数据目录，打包后保留在根目录
│   ├── import/             # 导入临时文件
│   ├── export/             # 导出文件留存
│   ├── backup/             # 数据库备份
│   └── logs/               # 运行日志
├── build.spec              # PyInstaller打包配置
└── README.md               # 使用说明
```

---

## 三、数据库层 精确设计（零错误SQLite语法）
### 1. 数据库全局配置
- 必须开启 **WAL预写日志模式**，提升并发性能、降低断电损坏概率
- 必须开启 **外键约束**，保证数据一致性
- 所有时间字段统一用 `TEXT` 类型，存储格式 `YYYY-MM-DD HH:MM:SS`（本地时间）
- 所有日期字段统一用 `TEXT` 类型，存储格式 `YYYY-MM-DD`
- 所有数值计算用 `REAL` 类型，业务层统一控制小数位数

### 2. 建表语句（逐字精确，禁止修改语法）
```sql
-- 1. 系统配置表
CREATE TABLE IF NOT EXISTS sys_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_key TEXT NOT NULL UNIQUE,
    config_value TEXT NOT NULL DEFAULT '',
    config_desc TEXT NOT NULL DEFAULT '',
    update_time TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

-- 初始配置数据（首次启动插入）
INSERT OR IGNORE INTO sys_config (config_key, config_value, config_desc) VALUES
('collection_interval', '60', '数据采集间隔，单位分钟，取值范围10-1440'),
('dev_mode', '0', '开发模式开关，0关闭1开启，开启后显示对账校验'),
('port', '8080', '本地服务端口'),
('auto_backup_hours', '6', '自动备份间隔，单位小时');

-- 2. 小时数据表（核心明细表）
CREATE TABLE IF NOT EXISTS hourly_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data_date TEXT NOT NULL,
    data_hour INTEGER NOT NULL CHECK (data_hour >= 1 AND data_hour <= 24),
    sold_rooms INTEGER NOT NULL DEFAULT 0 CHECK (sold_rooms >= 0 AND sold_rooms <= 113),
    available_rooms INTEGER NOT NULL DEFAULT 113 CHECK (available_rooms >= 0 AND available_rooms <= 113),
    occupancy_rate REAL NOT NULL DEFAULT 0 CHECK (occupancy_rate >= 0 AND occupancy_rate <= 100),
    min_price REAL DEFAULT 0 CHECK (min_price >= 0),
    revpar REAL NOT NULL DEFAULT 0 CHECK (revpar >= 0),
    total_revenue REAL NOT NULL DEFAULT 0 CHECK (total_revenue >= 0),
    data_source INTEGER NOT NULL DEFAULT 1, -- 1自动导入 2手动录入 3手动修改
    create_time TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    update_time TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE (data_date, data_hour)
);
CREATE INDEX IF NOT EXISTS idx_hourly_date ON hourly_data(data_date);

-- 3. 日报数据表
CREATE TABLE IF NOT EXISTS daily_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data_date TEXT NOT NULL UNIQUE,
    min_price REAL DEFAULT 0 CHECK (min_price >= 0),
    sold_rooms INTEGER NOT NULL DEFAULT 0 CHECK (sold_rooms >= 0 AND sold_rooms <= 113),
    remain_rooms INTEGER NOT NULL DEFAULT 113 CHECK (remain_rooms >= 0 AND remain_rooms <= 113),
    occupancy_rate REAL NOT NULL DEFAULT 0 CHECK (occupancy_rate >= 0 AND occupancy_rate <= 100),
    revpar REAL NOT NULL DEFAULT 0 CHECK (revpar >= 0),
    total_revenue REAL NOT NULL DEFAULT 0 CHECK (total_revenue >= 0),
    data_source INTEGER NOT NULL DEFAULT 1, -- 1自动生成 2手动修改
    create_time TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    update_time TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_daily_date ON daily_data(data_date DESC);

-- 4. 月报数据表
CREATE TABLE IF NOT EXISTS monthly_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data_year INTEGER NOT NULL,
    data_month INTEGER NOT NULL CHECK (data_month >= 1 AND data_month <= 12),
    days INTEGER NOT NULL CHECK (days >= 28 AND days <= 31),
    sold_rooms INTEGER NOT NULL DEFAULT 0 CHECK (sold_rooms >= 0),
    occupancy_rate REAL NOT NULL DEFAULT 0 CHECK (occupancy_rate >= 0 AND occupancy_rate <= 100),
    revpar REAL NOT NULL DEFAULT 0 CHECK (revpar >= 0),
    total_revenue REAL NOT NULL DEFAULT 0 CHECK (total_revenue >= 0),
    create_time TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    update_time TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE (data_year, data_month)
);

-- 5. 季报数据表
CREATE TABLE IF NOT EXISTS quarterly_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data_year INTEGER NOT NULL,
    data_quarter INTEGER NOT NULL CHECK (data_quarter >= 1 AND data_quarter <= 4),
    days INTEGER NOT NULL CHECK (days >= 90 AND days <= 92),
    sold_rooms INTEGER NOT NULL DEFAULT 0 CHECK (sold_rooms >= 0),
    occupancy_rate REAL NOT NULL DEFAULT 0 CHECK (occupancy_rate >= 0 AND occupancy_rate <= 100),
    revpar REAL NOT NULL DEFAULT 0 CHECK (revpar >= 0),
    total_revenue REAL NOT NULL DEFAULT 0 CHECK (total_revenue >= 0),
    create_time TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    UNIQUE (data_year, data_quarter)
);

-- 6. 年报数据表
CREATE TABLE IF NOT EXISTS yearly_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data_year INTEGER NOT NULL UNIQUE,
    valid_days INTEGER NOT NULL DEFAULT 0 CHECK (valid_days >= 0),
    sold_rooms INTEGER NOT NULL DEFAULT 0 CHECK (sold_rooms >= 0),
    occupancy_rate REAL NOT NULL DEFAULT 0 CHECK (occupancy_rate >= 0 AND occupancy_rate <= 100),
    revpar REAL NOT NULL DEFAULT 0 CHECK (revpar >= 0),
    total_revenue REAL NOT NULL DEFAULT 0 CHECK (total_revenue >= 0),
    create_time TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

-- 7. 导入记录表
CREATE TABLE IF NOT EXISTS import_record (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_name TEXT NOT NULL,
    report_type TEXT NOT NULL, -- daily_room / hourly_room / other_consume / income_check
    data_date TEXT,
    import_status INTEGER NOT NULL DEFAULT 1, -- 1成功 2失败
    error_msg TEXT DEFAULT '',
    create_time TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

-- 8. 操作日志表
CREATE TABLE IF NOT EXISTS operation_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name TEXT NOT NULL,
    record_id INTEGER NOT NULL,
    before_value TEXT NOT NULL DEFAULT '{}', -- JSON格式修改前数据
    after_value TEXT NOT NULL DEFAULT '{}',  -- JSON格式修改后数据
    operator TEXT NOT NULL DEFAULT 'local',
    create_time TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_log_table ON operation_log(table_name, record_id);
```

### 3. 数据库初始化规则
1. 程序启动时自动检测data目录，不存在则创建所有子目录
2. 检测数据库文件，不存在则执行建表语句+插入初始配置
3. 执行 `PRAGMA journal_mode=WAL;` `PRAGMA foreign_keys=ON;`
4. 首次启动将config.default.ini复制到data/config.ini

---

## 四、后端核心引擎 精确设计（零逻辑错误）
### 1. 数据清洗引擎（data_cleaner.py）
#### 报表识别规则（优先级从高到低）
1. **Sheet名称匹配**：
   - 包含「日租房」「过夜房」→ 识别为 `日租房概况`
   - 包含「钟点房」「小时房」→ 识别为 `钟点房概况`
   - 包含「其他消费」「额外消费」→ 识别为 `其他消费概况`
   - 包含「应收收入」「营业收入」→ 识别为 `应收收入报表`（仅开发模式启用）
2. **表头关键字匹配**：Sheet名称无法识别时，扫描第一行列名：
   - 同时包含「房型」「间夜数」「房费合计」→ 日租房
   - 同时包含「房型」「小时数」「房费合计」→ 钟点房
   - 同时包含「消费项目」「金额」→ 其他消费

#### 字段映射与清洗规则
| 原始字段示例 | 标准化字段 | 清洗规则 |
|--------------|------------|----------|
| 间夜数/房间数/出租数量 | room_count | 转整数，空值→0，非负校验 |
| 房费合计/总房费/消费金额 | total_fee | 去除¥、人民币符号、千分位逗号，转浮点数，空值→0，非负校验 |
| 最低房价/起售价 | min_price | 同上，日租房取当日最低值 |
| 统计日期/报表日期 | report_date | 统一转YYYY-MM-DD格式，优先从表头提取，其次从文件名提取，失败则提示用户输入 |

#### 校验与错误处理
1. 表头缺失必填字段 → 导入失败，返回「缺少字段：xxx」
2. 房间数>113或为负数 → 该行标记异常，导入失败，返回「第x行房间数超出范围」
3. 金额为负数 → 该行标记异常，返回「第x行金额不能为负」
4. 同一日期同一报表已存在 → 弹窗提示「该日期报表已存在，是否覆盖？」，默认取消
5. 开发模式额外校验：三类报表房费合计与应收收入报表差值>0.1% → 告警提示，不阻断导入

#### 导入合并逻辑
1. 同一日期的三张报表全部导入后，自动汇总计算：
   - 当日已售房间数 = 日租房房间数 + 钟点房房间数
   - 当日累计房费 = 日租房房费 + 钟点房房费 + 其他消费金额
2. 按导入报表的时间粒度，写入对应小时数据（默认写入当日24点结算数据）
3. 导入完成后触发计算引擎，同步更新关联的上层聚合数据

### 2. 实时计算引擎（calculator.py）
#### 精确计算公式（所有模块复用，禁止私自修改）
```python
# 工具函数：保留指定小数位
def round2(value):
    return round(float(value), 2)

# 【小时级计算】输入：sold_rooms, total_revenue → 输出全字段
def calc_hourly(sold_rooms, total_revenue, min_price=0):
    available = TOTAL_ROOMS - sold_rooms
    occupancy = round2(sold_rooms / TOTAL_ROOMS * 100)
    revpar = round2(total_revenue / TOTAL_ROOMS)
    return {
        "sold_rooms": sold_rooms,
        "available_rooms": available,
        "occupancy_rate": occupancy,
        "min_price": min_price,
        "revpar": revpar,
        "total_revenue": total_revenue
    }

# 【日报级计算】输入：sold_rooms, total_revenue, min_price → 输出全字段
def calc_daily(sold_rooms, total_revenue, min_price=0):
    remain = TOTAL_ROOMS - sold_rooms
    occupancy = round2(sold_rooms / TOTAL_ROOMS * 100)
    revpar = round2(total_revenue / TOTAL_ROOMS)
    return {
        "sold_rooms": sold_rooms,
        "remain_rooms": remain,
        "occupancy_rate": occupancy,
        "min_price": min_price,
        "revpar": revpar,
        "total_revenue": total_revenue
    }

# 【月报级计算】输入：year, month, sold_rooms, total_revenue → 输出全字段
def calc_monthly(year, month, sold_rooms, total_revenue):
    import calendar
    days = calendar.monthrange(year, month)[1]  # 自动处理大小月、闰年2月
    occupancy = round2(sold_rooms / (TOTAL_ROOMS * days) * 100)
    revpar = round2(total_revenue / (TOTAL_ROOMS * days))
    return {
        "days": days,
        "sold_rooms": sold_rooms,
        "occupancy_rate": occupancy,
        "revpar": revpar,
        "total_revenue": total_revenue
    }

# 【季报级计算】输入：year, quarter, 三个月的sold_rooms和total_revenue之和 → 输出全字段
def calc_quarterly(year, quarter, total_sold, total_revenue):
    # 计算当季总天数
    import calendar
    months = [(quarter-1)*3 + 1, (quarter-1)*3 + 2, (quarter-1)*3 + 3]
    total_days = sum([calendar.monthrange(year, m)[1] for m in months])
    occupancy = round2(total_sold / (TOTAL_ROOMS * total_days) * 100)
    revpar = round2(total_revenue / (TOTAL_ROOMS * total_days))
    return {
        "days": total_days,
        "sold_rooms": total_sold,
        "occupancy_rate": occupancy,
        "revpar": revpar,
        "total_revenue": total_revenue
    }

# 【年报级计算】输入：year, 全年sold_rooms和total_revenue之和, valid_days → 输出全字段
def calc_yearly(year, total_sold, total_revenue, valid_days):
    occupancy = round2(total_sold / (TOTAL_ROOMS * valid_days) * 100)
    revpar = round2(total_revenue / (TOTAL_ROOMS * valid_days))
    return {
        "valid_days": valid_days,
        "sold_rooms": total_sold,
        "occupancy_rate": occupancy,
        "revpar": revpar,
        "total_revenue": total_revenue
    }
```

#### 数据联动触发链路（事务包裹，失败全回滚）
```
触发场景1：小时数据新增/修改
    ↓
1. 重算当前小时行所有字段
2. 判断当前小时是否为24点
    ├─ 是 → 执行【日报重算】→ 执行【月报重算】→ 执行【季报重算】→ 执行【年报重算】
    └─ 否 → 仅更新当前小时行，不触发上层
    ↓
3. 写入操作日志
4. 提交事务 / 异常回滚

触发场景2：日报数据新增/修改
    ↓
1. 重算当前日报行所有字段
2. 执行【月报重算】→ 执行【季报重算】→ 执行【年报重算】
3. 写入操作日志
4. 提交事务 / 异常回滚

触发场景3：月报数据修改
    ↓
1. 重算当前月报行所有字段
2. 执行【季报重算】→ 执行【年报重算】
3. 写入操作日志
4. 提交事务 / 异常回滚
```

#### 上层重算精确逻辑
- **日报重算**：取当日24点的小时数据，用其sold_rooms、total_revenue、min_price更新日报；若当日无24点数据则不生成
- **月报重算**：汇总当月所有日报的sold_rooms之和、total_revenue之和，调用calc_monthly重算全字段
- **季报重算**：汇总当季三个月报的sold_rooms之和、total_revenue之和，调用calc_quarterly重算全字段
- **年报重算**：汇总当年所有月报的sold_rooms之和、total_revenue之和，统计当年有数据的天数（valid_days），调用calc_yearly重算全字段

### 3. 定时调度引擎（scheduler.py）
使用APScheduler的BackgroundScheduler，时区设为本地时区，所有任务精确到秒。

| 任务ID | 执行时间 | 执行逻辑 | 重试规则 | 补执行规则 |
|--------|----------|----------|----------|------------|
| daily_aggregate | 每天 00:01:00 | 取前一天24点小时数据，生成/更新前一天日报；失败触发月报重算 | 失败后每5分钟重试1次，最多3次 | 程序重启时检测昨日日报是否存在，不存在则自动补算 |
| monthly_aggregate | 每月1日 00:01:00 | 汇总上月所有日报，生成/更新上月月报；失败触发季报、年报重算 | 失败后每10分钟重试1次，最多3次 | 重启时检测上月月报是否存在，不存在则补算 |
| quarterly_aggregate | 1/4/7/10月1日 00:02:00 | 汇总上季度三个月报，生成/更新上季度季报 | 失败后每30分钟重试1次，最多3次 | 重启时检测上季度季报是否存在，不存在则补算 |
| yearly_aggregate | 每年1月1日 00:03:00 | 汇总上年12个月报，生成/更新上年年报 | 失败后每小时重试1次，最多3次 | 重启时检测上年年报是否存在，不存在则补算 |
| auto_backup | 每6小时执行一次（02:00, 08:00, 14:00, 20:00） | 复制数据库文件到backup目录，文件名格式：backup_YYYYMMDD_HHMM.db | 无重试 | 保留最近30天备份，超过自动删除 |
| log_clean | 每天 04:00:00 | 删除30天前的日志文件、清空import临时目录、清理过期备份 | 无重试 | - |

### 4. 启动流程与系统托盘
#### 启动顺序（严格按顺序执行，一步失败则弹窗提示并退出）
1. 初始化单实例锁（用文件锁实现，锁文件放在data目录），检测到已运行则弹窗提示「程序已在运行」并退出
2. 检查并创建data目录下所有子目录
3. 初始化数据库，执行建表和初始数据
4. 读取config.ini配置
5. 初始化日志系统
6. 启动APScheduler定时任务
7. 检测端口是否被占用，被占用则自动+1直到找到可用端口
8. 启动FastAPI服务（后台线程，不阻塞主线程）
9. 注册系统托盘图标和菜单
10. 自动打开默认浏览器访问 http://127.0.0.1:端口
11. 进入托盘消息循环，等待退出指令

#### 系统托盘右键菜单（精确项）
1. 打开系统 → 调用默认浏览器打开系统页面
2. 打开数据目录 → 打开资源管理器定位到data文件夹
3. 重启服务 → 重启FastAPI和定时任务
4. 退出程序 → 弹窗确认「确认退出？定时任务将停止运行」，确认后：停止定时任务→关闭数据库→删除锁文件→退出进程

---

## 五、API接口 精确规范（字段名完全统一）
### 统一响应格式
```json
{
    "code": 200,
    "message": "success",
    "data": {}
}
```
错误码：400参数错误、500服务器错误、404资源不存在

### 接口清单（精确到参数和返回字段）
#### 1. 导入导出类
| 接口 | 方法 | 路径 | 请求参数 | 返回data |
|------|------|------|----------|---------|
| 报表导入 | POST | /api/import/report | form-data: file (Excel文件) | {success_count: 0, fail_count: 0, details: [{row:1, error:"xxx"}]} |
| 小时数据导出 | GET | /api/export/hourly | date: string (YYYY-MM-DD) | 文件流，文件名：小时报表_YYYYMMDD.xlsx |
| 日报数据导出 | GET | /api/export/daily | startDate, endDate | 文件流，文件名：日报表_起始日期_结束日期.xlsx |
| 月报数据导出 | GET | /api/export/monthly | year: int | 文件流，文件名：月报表_YYYY.xlsx |

#### 2. 数据查询类
| 接口 | 方法 | 路径 | 请求参数 | 返回data |
|------|------|------|----------|---------|
| 实时仪表盘 | GET | /api/dashboard/realtime | 无 | {occupancy_rate, sold_rooms, revpar, trend: [{hour, total_revenue, revpar}]} |
| 小时数据列表 | GET | /api/hourly/list | date: string | 数组，24条，字段同hourly_data表 |
| 日报分页列表 | GET | /api/daily/list | page: int, pageSize: int, startDate?: string, endDate?: string | {list: [], total: int} |
| 月报列表 | GET | /api/monthly/list | year: int | 数组，字段同monthly_data表 |
| 季报列表 | GET | /api/quarterly/list | 无 | 数组，字段同quarterly_data表 |
| 年报列表 | GET | /api/yearly/list | 无 | 数组，字段同年yearly_data表 |

#### 3. 数据编辑类
| 接口 | 方法 | 路径 | 请求参数 | 返回data |
|------|------|------|----------|---------|
| 更新小时数据 | PUT | /api/hourly/{id} | body: {sold_rooms?, min_price?, total_revenue?} | 更新后的完整小时数据 |
| 更新日报数据 | PUT | /api/daily/{id} | body: {sold_rooms?, min_price?, total_revenue?} | 更新后的完整日报数据 |
| 更新月报数据 | PUT | /api/monthly/{id} | body: {sold_rooms?, total_revenue?} | 更新后的完整月报数据 |
| 一键记录当前小时 | POST | /api/hourly/record | 无 | 新增/更新的小时数据 |
| 删除日报 | DELETE | /api/daily/{id} | 无 | {success: true} |

#### 4. 系统操作类
| 接口 | 方法 | 路径 | 请求参数 | 返回data |
|------|------|------|----------|---------|
| 获取系统配置 | GET | /api/config/list | 无 | 配置项数组 |
| 更新系统配置 | PUT | /api/config | body: {key, value} | {success: true} |
| 重算指定日报 | POST | /api/daily/recalculate | date: string | 重算后的日报数据 |
| 重算指定月报 | POST | /api/monthly/recalculate | year: int, month: int | 重算后的月报数据 |
| 全量重算 | POST | /api/recalculate/all | 无 | {task_id: "xxx"}，立即返回，后台执行 |
| 获取系统状态 | GET | /api/system/status | 无 | {running: true, last_backup_time, db_size} |

#### 5. 图表分析类
| 接口 | 方法 | 路径 | 请求参数 | 返回data |
|------|------|------|----------|---------|
| 趋势预测数据 | GET | /api/chart/trend | dimension: day/week/month/quarter/year, date?: string | 适配ECharts的x轴、系列数据 |
| 热度矩阵数据 | GET | /api/chart/heatmap | dimension: day/week/month/quarter/year, date?: string | 二维数组+色带配置 |
| 星期规律数据 | GET | /api/chart/week | range: 1m/3m/1y | 周一到周日的指标均值 |
| 定价象限数据 | GET | /api/chart/price | range: 1m/3m/1y | 散点数据+象限中线值 |

---

## 六、前端页面 精确设计（像素级交互规范）
### 全局规范
- 构建工具：Vite，UI库：Element Plus，图表：ECharts 5
- 布局：顶部60px固定工具栏 + 左侧220px固定导航 + 右侧自适应主内容区
- 所有数值右对齐，文本左对齐，表头居中
- 可编辑单元格：双击进入编辑状态，回车保存，ESC取消，失焦自动保存
- 非法输入：单元格边框变红，右侧显示错误提示，不允许保存
- 所有请求统一封装，错误自动弹出Message提示

### 页面1：实时仪表盘 Dashboard.vue
1. 顶部3张等宽指标卡片，间距20px，卡片高度120px
   - 卡片1：当日实时出租率 → 数值两位小数+%，下方环比昨日
   - 卡片2：当日已售房间数 → 整数，下方环比昨日
   - 卡片3：当日单房收益 → 数值两位小数，前缀¥，下方环比昨日
2. 下方趋势图，高度400px，标题：当日经营数据实时趋势
   - 双Y轴：左轴累计房费（柱状图，色值#1677ff），右轴单房收益（折线图，色值#fa8c16，带圆点标记）
   - X轴：1-24点，刻度间隔4小时
   - 已过时间显示实色，未到时间显示灰色虚线占位
   - tooltip配置：`position: 'top'`，不遮挡图形，显示全部指标
3. 无数据时显示空状态，提供「导入数据」快捷按钮

### 页面2：小时数据 HourlyData.vue
1. 顶部操作栏，高度48px
   - 左侧：主按钮「一键记录」、次要按钮「重算当日」
   - 右侧：日期选择器（单日选择，默认当天）、采集间隔数字输入框（带单位分钟，范围10-1440，修改后自动保存）
2. 中间表格，固定24行，按小时升序
   - 列：时间（HH:00）、已售（可编辑，整数，0-113校验）、可售、出租率、起售价格（可编辑，非负）、单房收益、累计房费（可编辑，非负）、操作
   - 24:00行背景色浅橙，标注「当日结算」标签，操作列删除按钮禁用
   - 编辑后本行立即刷新计算结果，24点编辑后提示「已同步更新对应日报数据」
3. 底部图表，高度400px
   - 双Y轴组合图，同仪表盘样式
   - 支持鼠标滚轮横向缩放、左键拖拽平移
   - 点击柱状图自动高亮对应表格行

### 页面3：日报数据 DailyData.vue
1. 顶部操作栏
   - 左侧：新增、批量删除、导出
   - 右侧：日期范围选择器、搜索框
2. 中间表格，日期降序
   - 列：日期、起售价格、售出房间、剩余房间、出租率、单房收益、累计房费、数据来源、操作
   - 点击行首箭头可展开，显示当日24小时明细
   - 售出房间、累计房费、起售价格可编辑
3. 底部图表，高度450px
   - 默认显示近30天数据
   - 双Y轴，柱状累计房费，折线单房收益
   - 支持缩放拖拽，tooltip显示全量数据

### 页面4：月报数据 MonthlyData.vue
1. 顶部操作栏：重算上月、年份筛选
2. 中间表格
   - 列：周期（YYYY年MM月）、天数、已售房间数、出租率、单房收益、累计房费、操作
   - 点击任意一行，底部图表切换为该月每日明细
3. 底部图表：当月每日数据双Y轴组合图

### 页面5：季报数据 QuarterlyData.vue
1. 表格：周期、天数、已售房间数、出租率、单房收益、累计房费、操作
2. 底部图表：季度维度柱状+折线组合图，默认近8个季度

### 页面6：年报数据 YearlyData.vue
1. 表格：周期、有效天数、已售房间数、出租率、单房收益、累计房费、操作
2. 底部图表：年度维度柱状+折线组合图

### 页面7：图表分析 ChartAnalysis.vue
1. 顶部Tab栏：趋势预测、热度矩阵、星期规律、定价象限
2. 每个Tab内顶部为维度切换单选组（日/周/月/季度/年）
3. 趋势预测：
   - 实际数据实线，预测数据虚线+半透明填充
   - 日粒度预测未来24小时，周粒度预测未来7天，月粒度预测未来15天
   - 预测算法：Holt-Winters指数平滑，捕捉周期规律
4. 热度矩阵：
   - 色带：#165dff → #ffffff → #ff4d4f
   - 日维度：横轴1-24小时，纵轴近7天日期
   - 悬浮显示具体数值
5. 星期规律：
   - 柱状图，横轴周一至周日
   - 自动标注最高值、最低值
6. 定价象限：
   - 散点图，横轴平均房价，纵轴出租率
   - 十字中线划分四象限，标注象限策略说明

---

## 七、打包配置 精确规范
### 1. requirements.txt 精确依赖清单（无多余包）
```
fastapi==0.111.0
uvicorn==0.30.1
pandas==2.2.2
openpyxl==3.1.5
APScheduler==3.10.4
pystray==0.19.5
Pillow==10.4.0
python-multipart==0.0.9
configparser==7.2.0
```

### 2. PyInstaller build.spec 精确配置
```python
# -*- mode: python ; coding: utf-8 -*-
import sys
import os

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('dist', 'dist'),  # 前端静态文件
        ('config.default.ini', '.'),
    ],
    hiddenimports=[
        'uvicorn.logging',
        'apscheduler.triggers.cron',
        'pystray._win32',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', 'test', 'unittest', 'pydoc', 'doctest',
        'matplotlib', 'scipy', 'numpy.test',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='酒店数据分析系统',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # 隐藏控制台黑框
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='酒店数据分析系统',
)
```

### 3. 打包后目录处理
- 打包完成后，将 `data` 目录模板复制到输出文件夹根目录
- 最终文件夹结构：
  ```
  酒店数据分析系统/
  ├─ 酒店数据分析系统.exe
  ├─ data/
  │  ├─ import/
  │  ├─ export/
  │  ├─ backup/
  │  └─ logs/
  └─ 内部运行时文件（用户无需关心）
  ```

---

## 八、稳定性与异常处理规范
1. **所有数据库写操作必须使用事务**，异常自动回滚，禁止部分写入
2. **全局异常捕获**，FastAPI添加全局异常中间件，所有错误写入日志，返回友好提示
3. **单实例锁**：使用文件锁，禁止多实例同时运行，避免数据库损坏
4. **启动自检**：启动时校验数据库完整性，损坏则自动从最近备份恢复
5. **日志分级**：DEBUG/INFO/WARNING/ERROR，错误日志自动记录堆栈信息
6. **内存优化**：定时清理Pandas缓存、临时文件，避免内存持续增长
7. **断电保护**：WAL模式保证异常断电后数据不损坏，重启自动校验

---

## 九、开发输出与校验要求
### 输出顺序
1. 先生成后端所有代码，从常量、数据库、核心引擎到API接口
2. 再生成前端所有代码，从布局到每个页面
3. 最后生成打包配置、依赖清单、说明文档

### 生成后强制自检（AI必须自行检查）
1. 所有小时刻度是否为1-24，有无出现0点
2. 所有计算公式是否正确，大小月、闰年是否自动处理
3. 是否有残留的成本、毛利率相关代码
4. SQLite语法是否正确，有无MySQL专属语法
5. 联动逻辑是否符合自下而上的触发规则
6. 所有接口字段名前后端是否完全一致
7. 打包配置是否包含所有必要资源，有无多余依赖
8. 所有边界条件（空数据、最大值、最小值）是否有校验

确认零错误后，输出完整代码。