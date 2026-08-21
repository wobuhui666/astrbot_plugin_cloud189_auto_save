# astrbot_plugin_cloud189_auto_save

**有问题? 询问[deepwiki](https://deepwiki.com/wobuhui666/astrbot_plugin_cloud189_auto_save)**

把 [cloud189-auto-save](https://github.com/wobuhui666/cloud189-auto-save) 的机器人能力同步到 **AstrBot 全平台插件**。
插件通过 HTTP API 调用现有后端，支持 **QQ / Telegram / 微信 / Discord / Lark / 钉钉** 等 AstrBot 平台，并注册 LLM Tools 供大模型按自然语言调用。

---

## ✨ 功能

| 类别 | 命令 |
|------|------|
| 基础 | `/start` `/help` `/accounts` `/silent [on\|off]` `/cancel` `/cloud189_ping` |
| 任务 | `/tasks [page]` `/tasks_failed` `/tasks_pending` `/tasks_processing` `/detail_<id>` `/execute_<id>` `/execute_all` ★ `/strm_<id>` `/emby_<id>` `/retry_<id>` ★ `/dt_<id>` ★ |
| 目录 | `/fl` `/fs`(多轮目录树浏览) `/df_<id>` ★ |
| 搜索 / 影巢 | `/search_cs` `/tmdb 标题 [年]` `/hdhive 关键词` `/hdhive_resources movie\|tv TMDB_ID` `/hdhive_checkin` |
| Agent 追剧 | `/series 标题 [年]` `/lazy_series 标题 [年]` `/series_intents` `/series_pause ID` ★ `/series_resume ID` ★ `/series_run ID` ★ |
| 统计 / 日志 / 历史 | `/stats` `/logs [task_id]` `/history [关键词] [页码]` `/history_detail ID` |
| 订阅 | `/subs [page]` `/subs_refresh_<id>` |
| PT 站 | `/pt_status` `/pt_search` `/pt_subs [page]` `/pt_detail_<id>` `/pt_releases_<id> [page]` `/pt_refresh_<id>` ★ `/pt_toggle_<id>` ★ `/pt_retry_<id>` ★ `/pt_del_<id>` ★ |
| 自动识别 | 任意消息含 `cloud.189.cn` 分享链接 → 自动列出常用目录 / 静默模式直接保存 |

★ = 仅管理员可用。

跨平台兼容方案:Telegram 原本依赖 inline 键盘 + `callback_data`,QQ/微信不支持。本插件改成 **"列表编号 + 多轮 session_waiter"** 的方式,所有交互纯文本完成。

### LLM 自然语言调用

AstrBot 启用支持 Tool Calling 的聊天模型后，模型可自动使用以下工具：

| 工具 | 能力 | 权限 |
|------|------|------|
| `cloud189_query_tasks` | 查询任务列表与详情 | 白名单 |
| `cloud189_system_status` | 系统统计、PT 全局任务、PT 总下载速度和天翼总上传速度 | 白名单 |
| `cloud189_search_media` | 聚合搜索 CloudSaver、影巢、TMDB | 白名单 |
| `cloud189_list_auto_series` | 查询自动追剧 Intent | 白名单 |
| `cloud189_query_history` | 查询统一审计历史及详情 | 白名单 |
| `cloud189_create_auto_series` | 按后端 Agent、来源和画质设置创建追剧 | 管理员 |
| `cloud189_control_auto_series` | 暂停、恢复、立即运行追剧 | 管理员 |
| `cloud189_execute_task` | 执行已有任务 | 管理员 |
| `cloud189_hdhive_checkin` | 执行影巢签到 | 管理员 |

查询工具校验 `allowed_user_ids`，写工具同时校验 `admin_user_ids`。LLM 不会自动删除任务、删除云端文件或消费影巢积分。

---

## 📦 安装

1. 克隆/下载本目录到 AstrBot 实例的 `data/plugins/astrbot_plugin_cloud189_auto_save/`
2. 安装依赖:`pip install -r requirements.txt`(只需要 `aiohttp`)
3. 在 AstrBot 后台 → 插件管理 → 加载此插件
4. 进入插件配置页(右上角齿轮),填写 `api_base_url`、`api_key`(参考下文)

---

## ⚙️ 配置项(`_conf_schema.json` 全部字段)

| 字段 | 说明 |
|------|------|
| `api_base_url` | cloud189-auto-save 后端地址,默认 `http://localhost:3000` |
| `api_key` | 后端 `system.apiKey`,作 `x-api-key` 请求头(在后端网页"设置 → 系统 → API Key"生成) |
| `request_timeout_seconds` | HTTP 请求超时,默认 30 |
| `default_account_id` | 默认天翼云盘账号 ID,留 0 自动用第一个;可被 `/accounts` 切换覆盖 |
| `allowed_user_ids` | 白名单 sender_id 列表,留空表示所有人都能用 |
| `admin_user_ids` | 管理员 sender_id 列表,管理员才能执行带 ★ 的命令和 LLM 写操作 |
| `silent_mode` | 静默模式:收到分享链接时直接用默认目录创建任务,不再询问 |
| `log_file_path` | `/logs` 命令读取的日志文件路径(仅当插件与后端**同机部署**时有效),如 `/tmp/cloud189-app.log` |
| `log_max_lines` | `/logs` 返回的最大行数,默认 30 |
| `session_idle_seconds` | 会话空闲清理阈值,默认 1800 秒 |
| `search_timeout_seconds` | 搜索/PT 搜索多轮等待超时,默认 180 秒 |
| `page_size` | 列表分页每页条数,默认 5 |

> 怎么拿 `sender_id`?给机器人发 `/help` 后查看 AstrBot 控制台日志,或开 debug 后看消息事件里的 `sender_id`。
> 各平台的 sender_id 不一样:QQ/TG 是数字,微信是 `wxid_xxx`。

---

## 🧪 验证

```bash
# 1. 后端
cd cloud189-auto-save
yarn dev    # 监听 :3000
# 在网页"设置→系统"里生成 API Key,记下来

# 2. AstrBot
ln -s $(pwd)/../astrbot_plugin_cloud189 path/to/AstrBot/data/plugins/astrbot_plugin_cloud189_auto_save
# 在 AstrBot 后台重载插件,填 api_base_url / api_key

# 3. 在任一平台私聊机器人
/cloud189_ping  →  ✅ 后端可达,version = ...
/help           →  打印命令清单
/accounts       →  列出账号,回复 1 选中
/tasks          →  列表
/pt_status      →  PT 全局任务和总传输速度
/history        →  统一审计历史
粘贴一条 cloud.189.cn 分享链接 → 列出常用目录 → 回复编号 → 任务创建并执行
```

---

## 🔌 后端依赖与对应 API

| 命令 | 后端端点 |
|------|----------|
| `/accounts` | `GET /api/accounts` |
| `/tasks*` | `GET /api/tasks?status=` |
| `/execute_<id>` | `POST /api/tasks/<id>/execute` |
| `/execute_all` | `POST /api/tasks/executeAll` |
| `/strm_<id>` | `POST /api/tasks/strm` |
| `/dt_<id>` | `DELETE /api/tasks/<id>?deleteCloud=true` |
| `/retry_<id>` | `PUT /api/tasks/<id>` + `POST /api/tasks/<id>/execute` |
| `/fl` | `GET /api/favorites/<accountId>` |
| `/fs` 浏览 | `GET /api/folders/<accountId>?folderId=...` |
| `/fs` 保存 | `POST /api/saveFavorites` |
| `cloud.189.cn` | `POST /api/share/parse`、`POST /api/tasks` |
| `/search_cs` | `GET /api/cloudsaver/search?keyword=` |
| `/series` `/lazy_series` | `POST /api/auto-series` |
| `/series_intents` `/series_pause` `/series_resume` `/series_run` | `/api/auto-series/intents*` |
| `/tmdb` | `GET /api/tmdb/search?keyword=&year=` |
| `/hdhive*` | `/api/hdhive/search`、`/api/hdhive/resources`、`/api/hdhive/checkin` |
| `/history*` | `GET /api/audit-runs`、`GET /api/audit-runs/<id>` |
| `/subs` `/subs_refresh_<id>` | `GET /api/subscriptions`、`POST /api/subscriptions/<id>/refresh` |
| `/pt_search` | `GET /api/pt/sources/presets`、`/api/pt/sources/search`、`/api/pt/sources/groups` |
| `/pt_status` | `GET /api/pt/releases`（含 `transferStats`） |
| `/pt_subs` `/pt_detail_<id>` | `GET /api/pt/subscriptions`、`/api/pt/subscriptions/<id>/releases` |
| `/pt_refresh_<id>` | `POST /api/pt/subscriptions/<id>/refresh` |
| `/pt_toggle_<id>` | `PUT /api/pt/subscriptions/<id>` |
| `/pt_retry_<id>` | `POST /api/pt/releases/<id>/retry` |
| `/pt_del_<id>` | `DELETE /api/pt/releases/<id>?deleteFiles=true` |

所有 `/api/*` 走后端 `authenticateSession` 中间件，`x-api-key` 等于 `system.apiKey` 时可作为插件鉴权。

---

## ⚠️ 已知差异(与原 TG 机器人对比)

1. **inline 按钮 → 编号交互**:为兼容 QQ/微信等不支持按钮的平台,所有"是/否"、"翻页"、"目录选择"全部改为回复编号或关键字(`y` `yc` `n` `back` `save` `cancel`)。
2. **/emby_<id>**:后端没有独立的 Emby 通知端点,本插件等价于重新执行任务,由后端流水线触发刮削。
3. **/df_<id>**:后端没有 `DELETE /api/favorites/<id>`,本插件读全量后用 `POST /api/saveFavorites` 整体覆盖剔除。
4. **/logs**:Telegram 原版直接读 `/tmp/cloud189-app.log`,本插件需要在配置里显式指定 `log_file_path`,且需要与后端同机部署。
5. **会话作用域**:用 `event.unified_msg_origin` 区分,跨群组/跨平台彼此独立。
6. **影巢积分资源**:插件只展示已解锁链接和资源信息；未解锁资源必须在网页端确认积分后操作，命令和 LLM Tool 都不会自动消费积分。

---

## 🛠 开发

```
astrbot_plugin_cloud189/
├── metadata.yaml           # 插件元信息
├── _conf_schema.json       # 后台可视化配置
├── requirements.txt
├── main.py                 # Star 子类、命令与 @filter.llm_tool
├── api/
│   ├── client.py           # Cloud189ApiClient(aiohttp)
│   └── errors.py
├── core/
│   ├── session.py          # PluginSession + SessionStore
│   ├── auth.py             # 白名单 / 管理员
│   ├── templates.py        # 文本模板(对齐 templates.js)
│   └── share_parser.py     # parse_cloud_share()
└── handlers/
    ├── _common.py          # 权限、wait_one、分页
    ├── basics.py           # /start /help /accounts /cancel /silent
    ├── tasks.py            # 任务系列
    ├── folders.py          # /fl /fs /df_*
    ├── share.py            # cloud.189.cn 自动识别
    ├── search.py           # 搜索、追剧 Intent 与控制
    ├── hdhive.py           # 影巢搜索、资源查询、签到
    ├── history.py          # 统一审计历史
    ├── llm_tools.py        # 非交互 LLM Tool 实现
    ├── stats_logs_subs.py  # /stats /logs /subs
    └── pt.py               # PT 搜索、订阅与总传输状态
```

---

## License

跟随 cloud189-auto-save 主仓的 LICENSE。
