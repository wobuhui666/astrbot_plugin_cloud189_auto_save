"""天翼云盘分享链接解析,对齐 cloud189-auto-save/src/utils/Cloud189Utils.js 的 parseCloudShare。"""
from __future__ import annotations

import re

URL_RE = re.compile(r"https?://cloud\.189\.cn/\S+", re.IGNORECASE)
ACCESS_CODE_PATTERNS = [
    re.compile(r"[（(]访问码[:：]?\s*([A-Za-z0-9]{4,8})\s*[)）]"),
    re.compile(r"访问码[:：]?\s*([A-Za-z0-9]{4,8})"),
    re.compile(r"提取码[:：]?\s*([A-Za-z0-9]{4,8})"),
    re.compile(r"\(访问码[:：]?\s*([A-Za-z0-9]{4,8})\)", re.IGNORECASE),
]


def parse_cloud_share(text: str) -> tuple[str | None, str | None]:
    """从一段文本中抽取 cloud.189.cn 链接与访问码。

    返回 (url, access_code),提取不到链接时返回 (None, None)。
    """
    if not text:
        return None, None
    blob = str(text)
    url_match = URL_RE.search(blob)
    if not url_match:
        return None, None
    url = url_match.group(0).rstrip("，。,. )")
    code = None
    for pattern in ACCESS_CODE_PATTERNS:
        m = pattern.search(blob)
        if m:
            code = m.group(1).strip()
            break
    # url 自身末尾如果带 ?code=xxxx 也算访问码
    if not code:
        m = re.search(r"[?&]code=([A-Za-z0-9]{4,8})", url)
        if m:
            code = m.group(1)
    return url, code
