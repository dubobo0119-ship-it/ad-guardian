# -*- coding: utf-8 -*-
"""端到端实测:真实调用智谱视觉模型分析违规广告截图

密钥从环境变量 ADGUARDIAN_ZHIPU_KEY 读取(不写死在代码里)。
运行:
    $env:ADGUARDIAN_ZHIPU_KEY='你的密钥'; python test_e2e.py
"""

import json
import os
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from adguardian.vision import analyze_screenshot, VisionError, _map_category

IMG = r"C:\Users\admin\.qoder-cn\vibe_images\image_1787713631.png"


def main():
    with open(IMG, "rb") as f:
        data = f.read()
    print(f"测试图片:{IMG}({len(data)//1024} KB)")

    try:
        r = analyze_screenshot(data)
    except VisionError as e:
        print("识别失败:", e)
        sys.exit(1)

    print("\n===== AI 返回的结构化识别结果 =====")
    print(json.dumps(r, ensure_ascii=False, indent=2))

    print("\n===== 对照预期 =====")
    checks = [
        ("检测到违规广告", bool(r.get("has_violation"))),
        ("映射到知识库违规类型", r.get("key") != ""),
    ]
    for name, ok in checks:
        print(f"[{'通过' if ok else '注意'}] {name}")


if __name__ == "__main__":
    main()
