# -*- coding: utf-8 -*-
"""广告卫士 —— HTTP 接口层(FastAPI)

职责:把 adguardian 核心能力暴露为 REST 接口,供微信小程序等前端调用。
核心逻辑零改动,全部复用现有包——小程序只是换了个"壳"。

启动方式(在 ad-guardian 目录下):
    python api.py          # 监听 8000 端口
    # 密钥注入(可选,网页/小程序不填密钥时使用):
    $env:ADGUARDIAN_ZHIPU_KEY='你的密钥'; python api.py

接口清单:
    GET  /api/violations          违规类型知识库
    GET  /api/channels            举报渠道库
    GET  /api/apps                常见 App 名称库(联想用)
    POST /api/infer               一句话描述 → 违规类型推断
    POST /api/analyze             截图上传 → AI 看图识别(可选)
    POST /api/report              生成举报文书 + 匹配渠道
    POST /api/feedback            提交意见反馈(追加存 data/feedback.jsonl)
    GET  /api/feedback            查看反馈列表(开发者用,浏览器直接打开)
    GET  /api/health              健康检查
"""

import json
import os
import threading
from datetime import datetime

import uvicorn
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from adguardian import (
    VIOLATIONS, CHANNELS, COMMON_APPS,
    infer_violation, match_channels, build_report,
)
from adguardian.auto import extract_shot_time
from adguardian.vision import analyze_screenshot, VisionError

app = FastAPI(title="广告卫士 API", version="1.0")

# 小程序开发阶段(开发者工具)与本地网页调试均需跨域放行;
# 正式上线后微信走 wx.request 不存在浏览器跨域,此配置无害保留
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


class InferReq(BaseModel):
    text: str


class ReportReq(BaseModel):
    app_name: str
    v_key: str
    when: str = "未填写"
    device: str = "未填写"
    detail: str = ""


class FeedbackReq(BaseModel):
    content: str
    contact: str = ""


# 反馈存储:data/feedback.jsonl,每行一条,文本编辑器/Excel 都能直接看;
# 锁保证并发追加不串行,正式上线用户量大时再换数据库。
FEEDBACK_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
FEEDBACK_FILE = os.path.join(FEEDBACK_DIR, "feedback.jsonl")
_feedback_lock = threading.Lock()


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/violations")
def get_violations():
    return [
        {"key": v.key, "name": v.name, "symptom": v.symptom, "basis": v.basis}
        for v in VIOLATIONS.values()
    ]


@app.get("/api/channels")
def get_channels():
    return [
        {"key": c.key, "name": c.name, "scope": c.scope,
         "entry": c.entry, "steps": c.steps, "sla": c.sla}
        for c in CHANNELS.values()
    ]


@app.get("/api/apps")
def get_apps():
    return COMMON_APPS


@app.post("/api/infer")
def infer(req: InferReq):
    """文字识别:一句话描述 → 候选违规类型(带命中关键词,可解释)"""
    results = infer_violation(req.text)
    return [{"key": k, "score": s, "hits": h} for k, s, h in results]


@app.post("/api/analyze")
async def analyze(file: UploadFile = File(...)):
    """AI 看图识别:上传截图 → 视觉模型观察 + 规则判定

    失败(无密钥/网络/接口异常)不抛错,返回 ok=false,前端可优雅降级到文字识别。
    """
    data = await file.read()
    try:
        result = analyze_screenshot(data)
        result["ok"] = True
        return result
    except VisionError as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/report")
def report(req: ReportReq):
    """生成举报文书 + 匹配渠道 + 取证要点,一次返回"""
    if req.v_key not in VIOLATIONS:
        return {"error": "未知的违规类型"}
    text = build_report(req.app_name, req.v_key, req.when, req.device, req.detail)
    return {
        "text": text,
        "channels": [
            {"name": c.name, "scope": c.scope, "entry": c.entry,
             "sla": c.sla, "steps": c.steps, "go": c.go}
            for c in match_channels(req.v_key)
        ],
        "evidence": VIOLATIONS[req.v_key].evidence,
    }


@app.post("/api/feedback")
def add_feedback(req: FeedbackReq):
    """接收使用者意见反馈,追加存储到本地文件"""
    content = req.content.strip()
    if not content:
        return {"ok": False, "error": "反馈内容不能为空"}
    if len(content) > 500:
        return {"ok": False, "error": "反馈内容过长(上限 500 字)"}
    record = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "content": content,
        "contact": req.contact.strip(),
    }
    with _feedback_lock:
        os.makedirs(FEEDBACK_DIR, exist_ok=True)
        with open(FEEDBACK_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return {"ok": True}


@app.get("/api/feedback")
def list_feedback():
    """开发者查看反馈:浏览器直接打开 http://127.0.0.1:8000/api/feedback"""
    if not os.path.exists(FEEDBACK_FILE):
        return []
    items = []
    with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    items.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    items.reverse()  # 最新的排前面
    return items


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
