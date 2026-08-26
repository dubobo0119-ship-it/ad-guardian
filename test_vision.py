# -*- coding: utf-8 -*-
"""vision 模块离线单测(不调用网络,不消耗 API)"""

import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from adguardian.vision import (
    _parse_json, _map_category, _compress,
    VisionError, analyze_screenshot, judge_from_observation,
)


def main():
    # 1. JSON 宽容解析:纯 JSON / markdown 包裹 / 前后有杂散文字
    r1 = _parse_json('{"has_violation": true, "category": "虚假关闭按钮"}')
    assert r1["category"] == "虚假关闭按钮"

    r2 = _parse_json('```json\n{"has_violation": false}\n```')
    assert r2["has_violation"] is False

    r3 = _parse_json('好的,分析结果如下:{"category": "诱导欺骗点击"}请查收')
    assert r3["category"] == "诱导欺骗点击"

    try:
        _parse_json("完全不是 JSON")
        raise AssertionError("非法输入应抛 VisionError")
    except VisionError:
        pass
    print("JSON 宽容解析 4 例通过")

    # 2. 类别映射
    assert _map_category("无关闭按钮或关闭按钮隐蔽") == "no_close"
    assert _map_category("诱导欺骗点击") == "bait"
    assert _map_category("虚假倒计时") == "fake_countdown"
    assert _map_category("强制跳转或静默下载") == "forced_redirect"
    assert _map_category("无违规广告") == ""
    print("类别映射 5 例通过")

    # 3. 图片压缩(用 Pillow 现造一张大图)
    from PIL import Image
    import io
    big = Image.new("RGB", (3000, 4000), (200, 30, 30))
    buf = io.BytesIO()
    big.save(buf, format="PNG")
    out = _compress(buf.getvalue())
    compressed = Image.open(io.BytesIO(out))
    assert max(compressed.size) <= 1024
    print(f"图片压缩通过:3000x4000 -> {compressed.size[0]}x{compressed.size[1]}")

    # 4. 无密钥时的友好提示(不发网络请求)
    try:
        analyze_screenshot(b"", "")
        raise AssertionError("无密钥应抛 VisionError")
    except VisionError as e:
        assert "API 密钥" in str(e)
        print(f"无密钥提示正常:{str(e)[:24]}...")

    # 5. 观察事实 → 违规判定(确定性规则)
    j1 = judge_from_observation({"deceptive_text": "恭喜获得100元红包",
                                 "close_button": "极小或难以看清"})
    assert j1["key"] == "bait", "诱骗文案应优先判为诱导欺骗"
    j2 = judge_from_observation({"deceptive_text": "",
                                 "close_button": "有但极小或颜色与背景接近难以看清"})
    assert j2["key"] == "no_close"
    j3 = judge_from_observation({"deceptive_text": "",
                                 "close_button": "清晰明显",
                                 "exaggerated_claims": "零风险高收益"})
    assert j3["key"] == "false_ad"
    j4 = judge_from_observation({"deceptive_text": "",
                                 "close_button": "清晰明显",
                                 "redirection_or_download": "有"})
    assert j4["key"] == "forced_redirect"
    j5 = judge_from_observation({"deceptive_text": "",
                                 "close_button": "清晰明显",
                                 "redirection_or_download": "无"})
    assert j5["has_violation"] is False
    print("观察事实→违规判定 5 例通过")

    print("\nvision 模块单测全部通过")


if __name__ == "__main__":
    main()
