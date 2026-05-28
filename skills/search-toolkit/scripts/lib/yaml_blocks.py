"""YAML 顶层文本块切分（极简，注释安全）。

按「行首无缩进且含冒号」的顶层 key 把 YAML 文本切块，每块含该行 + 缩进续行 +
之后的纯空行/注释（直到下一个顶层 key）。**按文本块操作、不 round-trip 序列化**，
以保住用户的注释和排版。

足够 routing.yaml / limits.yaml / pricing.yaml 这类扁平 + 一层嵌套的配置文件。
供 seed_user_config.py（merge）与 promote.py（晋升）共用。
"""

from __future__ import annotations

import re

_TOP_LEVEL_KEY = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:")

PREAMBLE_KEY = "__preamble__"


def split_top_level_blocks(text: str) -> dict[str, str]:
    """把 YAML 文本按顶层 key 切块，返回 {key: 文本块（含尾部空行）}。

    文件开头的注释 / 空行 / metadata 归到特殊 key `__preamble__`。
    """
    lines = text.splitlines(keepends=True)
    blocks: dict[str, str] = {}
    current_key: str | None = None
    current_buf: list[str] = []
    for line in lines:
        is_top = bool(_TOP_LEVEL_KEY.match(line)) and line[0] not in (" ", "\t")
        if is_top:
            if current_key is not None:
                blocks[current_key] = "".join(current_buf)
            m = _TOP_LEVEL_KEY.match(line)
            assert m is not None
            current_key = m.group(1)
            current_buf = [line]
        else:
            if current_key is None:
                blocks.setdefault(PREAMBLE_KEY, "")
                blocks[PREAMBLE_KEY] += line
            else:
                current_buf.append(line)
    if current_key is not None:
        blocks[current_key] = "".join(current_buf)
    return blocks
