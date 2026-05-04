"""统一异常 + 友好错误信息(对齐后端 errors.js)。"""
from __future__ import annotations


class ApiError(Exception):
    """后端 API 返回 success=false 或 HTTP 错误时抛出。"""

    def __init__(self, message: str | None, status: int | None = None):
        super().__init__(message or "未知错误")
        self.message = message or "未知错误"
        self.status = status

    def __str__(self) -> str:
        if self.status:
            return f"[HTTP {self.status}] {self.message}"
        return self.message


def friendly_error(error: BaseException) -> str:
    """把任意异常转成用户友好的错误文案,对齐 telegramBot/errors.js。"""
    msg = str(error) or error.__class__.__name__
    lower = msg.lower()
    if "timeout" in lower or "timed out" in lower:
        return "⏱ 请求超时,请稍后重试或检查后端是否正常"
    if "econnrefused" in lower or "connection refused" in lower or "cannot connect" in lower:
        return "🔌 无法连接到 cloud189-auto-save 后端,请检查 api_base_url 配置以及后端是否启动"
    if "401" in msg or "未登录" in msg or "unauthor" in lower:
        return "🔐 鉴权失败,请检查插件配置 api_key 是否与后端 system.apiKey 一致"
    if "404" in msg:
        return "❓ 后端找不到对应资源(可能是 ID 不存在或后端版本不匹配)"
    if "folder already exists" in lower:
        return "⚠️ 该目录下已有同名文件夹"
    if "share" in lower and ("invalid" in lower or "无效" in msg):
        return "⚠️ 分享链接无效或已失效"
    if "access code" in lower or "提取码" in msg or "访问码" in msg:
        return "🔑 分享链接需要访问码,请在链接末尾追加 :访问码 后重发"
    if "cloudsaver" in lower:
        return "🔍 CloudSaver 调用失败,请检查后端 CloudSaver 配置"
    return f"❌ 出错了:{msg}"
