# -*- coding: utf-8 -*-
"""广告卫士 —— 核心包

模块职责:
- rules : 违规广告知识库(类型、法规依据、举报渠道)
- report: 举报文书生成器(匹配渠道 + 生成文案 + 取证要点)
"""

from .rules import VIOLATIONS, CHANNELS, get_violation, get_channel
from .report import match_channels, evidence_tips, build_report
from .auto import infer_violation, extract_shot_time, suggest_apps, COMMON_APPS
