"""站点 → 抓取能力 mapping（fetch.py 与「读 URL 拦截 hook」共用的单一事实源）。

配置是一份**行式纯文本**清单（grep / wc -l / sort -u 友好），一行一条：

    <域名>|<能力>

- `#` 起头或空行忽略；能力列可省，默认 real-browser
- 能力（capability）当前实装值只有 `real-browser`（命中 → 真实浏览器升级层、跳过普通链）；
  `jina` / `raw` 由 fetch.py 按 Content-Type 自动判定、无需登记，其余值留作后续扩展
- 匹配：host 等于 <域名>，或以 `.<域名>` 结尾

清单位置：active `~/.config/search-crew/site-fetch.txt`；缺失 / 空 / 读失败 → 内置默认。
读 txt 是纯 stdlib、无副作用、不触发 config seed，可安全用于 hook（要求快、fail-open）。
"""

from __future__ import annotations

import os
import urllib.parse
from pathlib import Path

REAL_BROWSER = "real-browser"

# 内置默认：有实测证据「普通链成功但残缺 / 强风控」的站点，全部 real-browser
_DEFAULT: tuple[tuple[str, str], ...] = (
    ("mp.weixin.qq.com", REAL_BROWSER),
    ("feishu.cn", REAL_BROWSER),
    ("larksuite.com", REAL_BROWSER),
    ("notion.so", REAL_BROWSER),
    ("notion.site", REAL_BROWSER),
    ("yuque.com", REAL_BROWSER),
)


def parse_lines(text: str) -> list[tuple[str, str]]:
    """解析行式清单文本为 [(域名, 能力), ...]。`#` 注释与空行忽略。"""
    out: list[tuple[str, str]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        dom, _, cap = line.partition("|")
        dom = dom.strip().lower()
        cap = cap.strip() or REAL_BROWSER
        if dom:
            out.append((dom, cap))
    return out


def load_mapping(path: str | os.PathLike | None) -> list[tuple[str, str]]:
    """读 txt 清单；path 为 None / 不存在 / 空 / 读失败 → 内置默认。"""
    if path:
        p = Path(path)
        if p.exists():
            try:
                parsed = parse_lines(p.read_text(encoding="utf-8"))
                if parsed:
                    return parsed
            except Exception:
                pass
    return list(_DEFAULT)


def _active_txt() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or "~/.config"
    return Path(base).expanduser() / "search-crew" / "site-fetch.txt"


def active_mapping() -> list[tuple[str, str]]:
    """加载用户态 active 清单（缺失则内置默认）。fetch.py 与 hook 的统一入口。"""
    return load_mapping(_active_txt())


def _host_matches(host: str, match: str) -> bool:
    return host == match or host.endswith(f".{match}")


def capability_for_host(host: str, mapping: list[tuple[str, str]] | None = None) -> str | None:
    """host 命中清单则返回能力，否则 None。mapping 为 None 时用内置默认。"""
    host = (host or "").strip().lower()
    if not host:
        return None
    for match, cap in (mapping if mapping is not None else _DEFAULT):
        if _host_matches(host, match):
            return cap
    return None


def capability_for_url(url: str, mapping: list[tuple[str, str]] | None = None) -> str | None:
    """从 url 取 host 再查能力。url 无法解析时返回 None。"""
    try:
        host = urllib.parse.urlsplit(url).hostname or ""
    except Exception:
        return None
    return capability_for_host(host, mapping)
