# astrbot_plugin_cloud189_auto_save

把 [cloud189-auto-save](https://github.com/1373535745/cloud189-auto-save) 自带的 Telegram 机器人完整复刻为 **AstrBot 全平台插件**。  
通过 HTTP API 调用现有后端,所以无需修改后端代码,即可在 **QQ / Telegram / 微信 / Discord / Lark / 钉钉** 等所有 AstrBot 适配的平台上得到与 TG 机器人一致的体验。

---

## ✨ 功能 — 完整复刻 33 条命令

| 类别 | 命令 |
|------|------|
| 基础 | `/start` `/help` `/accounts` `/silent [on\|off]` `/cancel` `/cloud189_ping` |
| 任务 | `/tasks [page]` `/tasks_failed` `/tasks_pending` `/tasks_processing` `/detail_<id>` `/execute_<id>` `/execute_all` ★ `/strm_<id>` `/emby_<id>` `/retry_<id>` ★ `/dt_<id>` ★ |
| 目录 | `/fl` `/fs`(多轮目录树浏览) `/df_<id>` ★ |
| 搜索 / 追剧 | `/search_cs`(CloudSaver 搜索模式) `/tmdb 标题 [年]` `/series 标题 [年]` `/lazy_series 标题 [年]` |
| 统计 / 日志 / 订阅 | `/stats` `/logs [task_id]` `/subs [page]` `/subs_refresh_<id>` |
| PT 站 | `/pt_search` `/pt_subs [page]` `/pt_detail_<id>` `/pt_releases_<id> [page]` `/pt_refresh_<id>` ★ `/pt_toggle_<id>` ★ `/pt_retry_<id>` ★ `/pt_del_<id>` ★ |
| 自动识别 | 任意消息含 `cloud.189.cn` 分享链接 → 自动列出常用目录 / 静默模式直接保存 |

★ = 仅管理员可用。

跨平台兼容方案:Telegram 原本依赖 inline 键盘 + `callback_data`,QQ/微信不支持。本插件改成 **"列表编号 + 多轮 session_waiter"** 的方式,所有交互纯文本完成。

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
| `admin_user_ids` | 管理员 sender_id 列表,管理员才能执行带 ★ 的命令 |
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
| `/tmdb` | `GET /api/tmdb/search?keyword=&year=` |
| `/subs` `/subs_refresh_<id>` | `GET /api/subscriptions`、`POST /api/subscriptions/<id>/refresh` |
| `/pt_search` | `GET /api/pt/sources/presets`、`/api/pt/sources/search`、`/api/pt/sources/groups` |
| `/pt_subs` `/pt_detail_<id>` | `GET /api/pt/subscriptions`、`/api/pt/subscriptions/<id>/releases` |
| `/pt_refresh_<id>` | `POST /api/pt/subscriptions/<id>/refresh` |
| `/pt_toggle_<id>` | `PUT /api/pt/subscriptions/<id>` |
| `/pt_retry_<id>` | `POST /api/pt/releases/<id>/retry` |
| `/pt_del_<id>` | `DELETE /api/pt/releases/<id>?deleteFiles=true` |

后端鉴权位置:`cloud189-auto-save/src/index.js:402-405`,所有 `/api/*` 走 `authenticateSession` 中间件,`x-api-key` 等于 `system.apiKey` 即可绕过 session。

---

## ⚠️ 已知差异(与原 TG 机器人对比)

1. **inline 按钮 → 编号交互**:为兼容 QQ/微信等不支持按钮的平台,所有"是/否"、"翻页"、"目录选择"全部改为回复编号或关键字(`y` `yc` `n` `back` `save` `cancel`)。
2. **/emby_<id>**:后端没有独立的 Emby 通知端点,本插件等价于重新执行任务,由后端流水线触发刮削。
3. **/df_<id>**:后端没有 `DELETE /api/favorites/<id>`,本插件读全量后用 `POST /api/saveFavorites` 整体覆盖剔除。
4. **/logs**:Telegram 原版直接读 `/tmp/cloud189-app.log`,本插件需要在配置里显式指定 `log_file_path`,且需要与后端同机部署。
5. **会话作用域**:用 `event.unified_msg_origin` 区分,跨群组/跨平台彼此独立。

---

## 🛠 开发

```
astrbot_plugin_cloud189/
├── metadata.yaml           # 插件元信息
├── _conf_schema.json       # 后台可视化配置
├── requirements.txt
├── main.py                 # Star 子类 + 全部 @filter.command
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
    ├── search.py           # /search_cs /tmdb /series /lazy_series
    ├── stats_logs_subs.py  # /stats /logs /subs
    └── pt.py               # PT 全套
```

---

## License

跟随 cloud189-auto-save 主仓的 LICENSE。
