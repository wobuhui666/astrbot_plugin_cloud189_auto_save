"""白名单与管理员校验。

跨平台 sender_id 不同(QQ 数字、TG 数字、微信 wxid),
统一在 _conf_schema.json 里以字符串形式配置,运行时把
event.get_sender_id() 也字符串化做精确比对。
"""
from __future__ import annotations

from typing import Iterable


def _normalize(items: Iterable) -> list[str]:
    out: list[str] = []
    for item in items or []:
        if item is None:
            continue
        text = str(item).strip()
        if text:
            out.append(text)
    return out


def is_allowed(sender_id: str, allowed: Iterable | None) -> bool:
    """allowed 为空表示所有人都允许。"""
    allow_list = _normalize(allowed or [])
    if not allow_list:
        return True
    return str(sender_id) in allow_list


def is_admin(sender_id: str, admins: Iterable | None) -> bool:
    """admins 为空表示没有管理员(所有需要管理员的命令均被拒)。"""
    admin_list = _normalize(admins or [])
    return str(sender_id) in admin_list
