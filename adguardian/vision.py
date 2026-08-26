# -*- coding: utf-8 -*-
"""多模态 AI 截图识别(智谱 GLM-4V-Flash,长期免费档)

职责:
- analyze_screenshot : 上传截图 → 视觉模型分析 → 结构化识别结果

为什么选智谱:
- glm-4v-flash 完全免费,注册只需手机号(开放平台开放凭证)
- 对中文界面/广告文案识别效果好,返回稳定
- OpenAI 兼容格式,后续换其他免费视觉模型(如硅基流动)只改 URL/模型名

安全说明:
- API 密钥只保存在用户本地(环境变量 / 浏览器会话),代码不收集不上传
- 截图仅发送给智谱官方接口用于识别
"""

import base64
import io
import json
import os
import re

import requests
from PIL import Image

API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
MODEL = "glm-4v-flash"
ENV_KEY = "ADGUARDIAN_ZHIPU_KEY"

# 架构设计:AI 只负责"陈述看到的事实"(小模型观察能力够用),
# 违规判定交给下方 judge_from_observation() 规则代码——
# 确定性、可解释,避免小模型"看到了问题却不敢下结论"
PROMPT = """请仔细观察这张手机截图,如实报告你看到的广告界面事实。
只需陈述事实,不要做合规判断。逐项检查并回答:
1. 这是不是一个占据整个屏幕的开屏/全屏广告页面?
2. 关闭/跳过按钮的情况:没有 / 有但极小或颜色与背景接近难以看清 / 清晰明显 / 无法判断
3. 有没有倒计时文字(如"3s""3秒后跳过")?
4. 有没有诱骗用户点击的文案?如"恭喜获得""领取红包""XX元券""内存已满"
   "检测到病毒""免费领""立即领取"等,有则把原文一字不差抄录下来,没有则留空
5. 有没有虚假夸大的宣传文案?如"零风险""高收益""稳赚""包治"等,有则抄录原文,没有留空
6. 有没有正在下载、强制跳转的痕迹(如下载进度条、非用户主动打开的落地页)?
7. 如果能看出是哪个 App,写出名称;不确定留空
8. 用一句话客观描述这张截图的内容(包含你看到的按钮、文案、布局)

严格输出 JSON,不要输出任何其他文字,格式如下:
{
  "fullscreen_ad": true,
  "close_button": "没有 / 极小或难以看清 / 清晰明显 / 无法判断",
  "countdown": "有 / 无 / 无法判断",
  "deceptive_text": "诱骗文案原文或空字符串",
  "exaggerated_claims": "夸大文案原文或空字符串",
  "redirection_or_download": "有 / 无 / 无法判断",
  "app_guess": "App 名称或空字符串",
  "summary": "一句话客观描述截图内容"
}"""


def judge_from_observation(obs: dict) -> dict:
    """根据 AI 观察到的事实,用确定性规则判定违规类型(可解释、可单测)

    判定优先级:诱骗文案 > 关闭入口问题 > 虚假夸大 > 强制跳转/静默下载;
    全都不命中才算无违规。
    返回:{"has_violation": bool, "key": str, "category": str, "reason": str}
    """
    deceptive = str(obs.get("deceptive_text", "")).strip()
    close_btn = str(obs.get("close_button", ""))
    exaggerated = str(obs.get("exaggerated_claims", "")).strip()
    redirect = str(obs.get("redirection_or_download", ""))

    if deceptive:
        return {"has_violation": True, "key": "bait",
                "category": "诱导欺骗点击",
                "reason": f"AI 在截图中识别到诱骗文案:「{deceptive}」"}
    if ("没有" in close_btn) or ("极小" in close_btn) or ("难以看清" in close_btn):
        return {"has_violation": True, "key": "no_close",
                "category": "无关闭按钮或关闭按钮隐蔽",
                "reason": f"AI 观察到关闭按钮状态:{close_btn}"}
    if exaggerated:
        return {"has_violation": True, "key": "false_ad",
                "category": "广告内容虚假夸大",
                "reason": f"AI 识别到夸大文案:「{exaggerated}」"}
    if "有" in redirect:
        return {"has_violation": True, "key": "forced_redirect",
                "category": "强制跳转或静默下载",
                "reason": "AI 观察到强制跳转/静默下载痕迹"}
    return {"has_violation": False, "key": "", "category": "无违规广告",
            "reason": "未命中任何违规特征"}


# AI 返回的类别 → 知识库违规类型映射
CATEGORY_MAP = {
    "摇一摇": "shake",
    "无关闭": "no_close",
    "关闭按钮隐蔽": "no_close",
    "虚假关闭": "fake_close",
    "假关闭": "fake_close",
    "套娃": "nested",
    "连环弹窗": "nested",
    "倒计时": "fake_countdown",
    "诱导": "bait",
    "诱骗": "bait",
    "欺骗点击": "bait",
    "强制跳转": "forced_redirect",
    "静默下载": "forced_redirect",
    "虚假夸大": "false_ad",
    "虚假宣传": "false_ad",
}


class VisionError(Exception):
    """识别失败(网络/密钥/返回格式),携带可直接展示给用户的原因"""


def _compress(image_bytes: bytes, max_side: int = 1024) -> bytes:
    """压缩截图:限制最长边并转 JPEG,减小请求体积"""
    img = Image.open(io.BytesIO(image_bytes))
    img = img.convert("RGB")
    if max(img.size) > max_side:
        ratio = max_side / max(img.size)
        img = img.resize((int(img.width * ratio), int(img.height * ratio)))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return buf.getvalue()


def _map_category(category: str) -> str:
    """AI 自由文本类别 → 知识库 key;无法对应时返回空串"""
    for kw, key in CATEGORY_MAP.items():
        if kw in category:
            return key
    return ""


def _parse_json(text: str) -> dict:
    """宽容解析模型输出:剥掉可能的 markdown 代码块,再取首尾大括号"""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    raise VisionError("AI 返回格式异常,请重试")


def analyze_screenshot(image_bytes: bytes, api_key: str = "") -> dict:
    """分析一张截图,返回结构化识别结果

    返回:{"has_violation": bool, "category": str, "key": str(知识库key,可能为空),
          "close_button": str, "countdown": str, "deceptive_text": str,
          "app_guess": str, "summary": str}
    """
    key = api_key.strip() or os.environ.get(ENV_KEY, "").strip()
    if not key:
        raise VisionError(
            "请先填写 API 密钥:注册智谱开放平台(bigmodel.cn,免费)→"
            "个人中心→API密钥,粘贴到本页「AI 设置」即可,全程不花钱"
        )

    try:
        payload_img = base64.b64encode(_compress(image_bytes)).decode()
    except Exception:
        raise VisionError("图片无法解析,请上传 png/jpg 格式截图")

    resp = requests.post(
        API_URL,
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": MODEL,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image_url",
                     "image_url": {"url": f"data:image/jpeg;base64,{payload_img}"}},
                    {"type": "text", "text": PROMPT},
                ],
            }],
            "temperature": 0.1,
        },
        timeout=60,
        # 智谱是国内接口,用户若开着系统代理(如 VPN 软件),
        # 走代理反而会被拦断(报 ProxyError/SSL EOF),强制直连更稳。
        proxies={"http": None, "https": None},
    )
    if resp.status_code == 401:
        raise VisionError("API 密钥无效,请检查是否复制完整")
    if resp.status_code != 200:
        raise VisionError(f"接口调用失败({resp.status_code}),请稍后重试")

    try:
        content = resp.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError):
        raise VisionError("接口返回异常,请稍后重试")

    result = _parse_json(content)
    # 模型只陈述事实,违规判定由确定性规则完成(见 judge_from_observation)
    result.update(judge_from_observation(result))
    return result
