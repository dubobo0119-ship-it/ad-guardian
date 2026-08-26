# -*- coding: utf-8 -*-
"""举报文书生成器

职责:
1. match_channels : 根据违规类型的标签自动匹配官方举报渠道(按相关度排序)
2. evidence_tips  : 输出该违规类型的取证要点清单
3. build_report   : 把用户填写的案情组装成结构化举报文书

文书模板设计原则:
- 客观陈述事实,不做主观定性("涉嫌"而非"违法"),避免举报材料因措辞被驳回
- 自动引用知识库中的法规条款,提升受理效率
- 留出证据清单占位,提醒用户附上截图/录屏
"""

from datetime import date

from .rules import VIOLATIONS, CHANNELS, get_violation


def match_channels(v_key: str) -> list:
    """返回该违规类型对应的举报渠道列表(按标签重合度降序)

    例:虚假关闭按钮(标签 miit+samr)→ 同时匹配 12321 和 12315,
        因为"关不掉"归工信部管,"欺骗性设计"也触犯广告法归市监管。
    """
    v = get_violation(v_key)
    scored = []
    for ch in CHANNELS.values():
        overlap = len(set(v.tags) & set(ch.tags))
        if overlap > 0:
            scored.append((overlap, ch))
    scored.sort(key=lambda x: -x[0])
    return [ch for _, ch in scored]


def evidence_tips(v_key: str) -> list:
    """取证要点清单(界面直接展示给用户)"""
    return get_violation(v_key).evidence


def build_report(app_name: str, v_key: str, when: str, device: str,
                 detail: str = "") -> str:
    """生成结构化举报文书

    参数:
        app_name : 被举报 App 名称
        v_key    : 违规类型 key
        when     : 事发时间(字符串,如 2026-08-26 08:30)
        device   : 手机型号与系统版本
        detail   : 用户补充描述(可选)
    返回:
        可直接复制粘贴到举报平台的纯文本文书
    """
    v = get_violation(v_key)
    channels = match_channels(v_key)

    lines = []
    lines.append("【举报对象】")
    lines.append(f"应用名称:{app_name}")
    lines.append(f"使用设备:{device}")
    lines.append(f"事发时间:{when}")
    lines.append("")

    lines.append("【违规事实】")
    lines.append(f"本人于上述时间正常使用该应用时,出现以下情形:{v.symptom}。")
    if detail.strip():
        lines.append(f"补充描述:{detail.strip()}")
    lines.append("")

    lines.append("【涉嫌违反的规定】")
    for i, b in enumerate(v.basis, 1):
        lines.append(f"{i}. {b}")
    lines.append("")

    lines.append("【证据材料】")
    lines.append("本人已留存以下证据,可随举报提交:")
    for i, e in enumerate(v.evidence, 1):
        lines.append(f"{i}. {e}")
    lines.append("")

    lines.append("【诉求】")
    lines.append("请依法核查上述违规行为,督促该应用整改,并将处理结果告知本人。")
    lines.append("")

    lines.append("【建议受理渠道】")
    for ch in channels:
        lines.append(f"- {ch.name}(受理范围:{ch.scope})")
        lines.append(f"  入口:{ch.entry}")
    lines.append("")
    lines.append(f"举报人提交日期:{date.today().isoformat()}")

    return "\n".join(lines)
