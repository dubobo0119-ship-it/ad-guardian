# -*- coding: utf-8 -*-
"""自动化模块(零外部依赖,规则引擎版)

三个能力:
1. infer_violation : 一句话描述 → 关键词规则引擎推断违规类型(带置信度)
2. extract_shot_time: 从截图 EXIF 自动提取拍摄时间(免手填事发时间)
3. suggest_apps    : 高频广告重灾区 App 名称联想

设计说明:
- 规则引擎而非大模型:零成本、可离线、结果可解释(能告诉用户"命中了哪些关键词")
- 命中规则分三档:强特征词(权重 2)、一般特征词(权重 1)、组合词对(权重 3,
  两个词同时出现才算命中,容忍中间插字,如"点了关闭[按钮]反而跳转")
- 后续若接入多模态大模型,可在本模块追加 llm_infer() 接口,上层调用方式不变
"""

from io import BytesIO

from PIL import Image
from PIL.ExifTags import Base as ExifBase


# ============================================================
# 1. 一句话 → 违规类型推断
# ============================================================

# 关键词规则库:每类违规 = 强特征词(权重2) + 一般特征词(权重1)
KEYWORD_RULES = {
    "shake": {
        "strong": ["摇一摇", "摇晃", "晃了一下", "晃了晃", "抖动", "颠簸"],
        "weak": ["没碰", "没点", "没操作", "误触", "自己跳", "自动跳"],
    },
    "no_close": {
        "strong": ["找不到关闭", "没有关闭按钮", "没有叉", "没有×", "没有跳过",
                   "关不掉", "无法关闭", "关闭按钮太小", "关闭按钮看不见"],
        "weak": ["全屏", "遮挡", "去不掉", "取消不了"],
    },
    "fake_close": {
        "strong": ["假关闭", "点了关闭反而", "点了叉", "点了×", "点关闭反而跳转",
                   "点关闭就开始下载"],
        "weak": ["关闭是假的", "越点越跳", "关闭按钮是广告"],
        "combo": [("关闭", "反而"), ("关闭", "下载"), ("叉", "跳"), ("×", "跳")],
    },
    "nested": {
        "strong": ["一个接一个", "关不完", "连续弹窗", "套娃", "弹窗不断", "连环"],
        "weak": ["又弹", "接着弹", "没完没了", "一直弹"],
    },
    "fake_countdown": {
        "strong": ["倒计时", "3秒后跳过", "跳过倒计时", "重新计时"],
        "weak": ["数完", "等倒计时", "秒数结束"],
    },
    "bait": {
        "strong": ["领红包", "领 100", "领取红包", "中奖", "100元券", "内存已满",
                   "病毒", "清理", "恭喜获得", "免费领取"],
        "weak": ["骗我点", "诱导", "假装", "冒充系统", "伪装"],
    },
    "forced_redirect": {
        "strong": ["自动下载", "静默下载", "强制跳转", "没同意就下载", "自动打开别的"],
        "weak": ["跳到别的", "跳转", "跳到应用商店", "被下载"],
        "combo": [("没同意", "下载"), ("没点", "下载"), ("没操作", "下载")],
    },
    "false_ad": {
        "strong": ["虚假宣传", "高收益", "零风险", "包治", "稳赚", "夸大"],
        "weak": ["骗人", "假的广告", "与实际不符", "诱导借贷"],
    },
}


def infer_violation(text: str, top_n: int = 3) -> list:
    """一句话描述 → 推断违规类型

    返回:按置信度降序的 [(violation_key, score, hit_words), ...],
          最多 top_n 个;全部未命中时返回空列表(调用方引导手动选择)。
    """
    if not text or not text.strip():
        return []
    results = []
    for key, rules in KEYWORD_RULES.items():
        hits, score = [], 0
        for w in rules["strong"]:
            if w in text:
                hits.append(w)
                score += 2
        for w in rules["weak"]:
            if w in text:
                hits.append(w)
                score += 1
        for a, b in rules.get("combo", []):
            if a in text and b in text:
                hits.append(f"{a}+{b}")
                score += 3
        if score > 0:
            results.append((key, score, hits))
    results.sort(key=lambda x: -x[1])
    return results[:top_n]


# ============================================================
# 2. 截图 EXIF 时间提取
# ============================================================

def extract_shot_time(uploaded_file) -> str:
    """从上传图片中提取拍摄/截图时间

    参数:uploaded_file — Streamlit file_uploader 返回的对象(有 read/seek)
    返回:'2026-08-26 08:30:12' 格式字符串;无法提取时返回空串
    """
    try:
        uploaded_file.seek(0)
        img = Image.open(BytesIO(uploaded_file.read()))
        exif = img.getexif()
        if not exif:
            return ""
        raw = (exif.get(ExifBase.DateTimeOriginal)
               or exif.get(ExifBase.DateTimeDigitized)
               or exif.get(ExifBase.DateTime))
        if not raw:
            return ""
        # EXIF 格式 '2026:08:26 08:30:12' → '2026-08-26 08:30:12'
        return raw.replace(":", "-", 2)
    except Exception:
        return ""


# ============================================================
# 3. App 名称联想库
# ============================================================

# 高频出现开屏/弹窗广告的主流 App(举报重灾区,按类别排列)
COMMON_APPS = [
    # 社交/购物/生活
    "微信", "QQ", "淘宝", "拼多多", "京东", "美团", "饿了么", "闲鱼", "支付宝",
    # 视频/阅读/资讯(开屏广告重灾区)
    "抖音", "快手", "小红书", "微博", "B站(哔哩哔哩)", "知乎", "百度",
    "UC浏览器", "QQ浏览器", "今日头条",
    # 影音/音乐
    "爱奇艺", "腾讯视频", "优酷", "芒果TV", "网易云音乐", "QQ音乐",
    "酷狗音乐", "喜马拉雅", "番茄免费小说", "七猫免费小说",
    # 工具类(广告泛滥重灾区)
    "万能钥匙", "墨迹天气", "中华万年历", "步数宝", "走路赚钱",
    "手机清理大师", "电池管家", "免费WiFi",
    # 出行/地图
    "高德地图", "百度地图", "滴滴出行", "铁路12306",
]


def suggest_apps(prefix: str = "") -> list:
    """按前缀联想 App 名称;前缀为空时返回全部"""
    if not prefix.strip():
        return COMMON_APPS
    prefix = prefix.strip()
    return [a for a in COMMON_APPS if prefix in a]
