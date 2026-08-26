# -*- coding: utf-8 -*-
"""阶段一验证脚本:知识库完整性 + 渠道匹配逻辑 + 文书生成

预期:
- 8 类违规、4 个渠道全部可索引,每条都有法规依据与取证要点
- 单一标签违规(如摇一摇→miit)匹配 2 个渠道;双标签违规(如假关闭→miit+samr)匹配 3 个且多标签渠道排前
- 生成的举报文书包含全部结构块且可直接复制使用

运行方式(在 ad-guardian 目录下):
    python demo.py
"""

import sys

# Windows 终端 GBK 编码保险:强制 stdout 用 UTF-8,避免中文/特殊字符乱码报错
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from adguardian import VIOLATIONS, CHANNELS, match_channels, build_report
from adguardian.auto import infer_violation, suggest_apps


def main():
    print("=" * 56)
    print("知识库完整性检查")
    print("=" * 56)
    assert len(VIOLATIONS) == 8, "违规类型应为 8 类"
    assert len(CHANNELS) == 4, "举报渠道应为 4 个"
    for v in VIOLATIONS.values():
        assert v.symptom and v.basis and v.evidence and v.tags, v.key
        print(f"[违规] {v.key:<15} {v.name}  依据{len(v.basis)}条/取证{len(v.evidence)}步")
    for ch in CHANNELS.values():
        assert ch.scope and ch.entry and ch.steps, ch.key
        print(f"[渠道] {ch.key:<12} {ch.name}")

    print("\n" + "=" * 56)
    print("渠道匹配逻辑验证")
    print("=" * 56)
    r1 = match_channels("shake")          # 单标签 → 应匹配 2 个(12321/工信部直通)
    r2 = match_channels("fake_close")    # 双标签 → 应匹配 3 个且重合度高的在前
    print(f"摇一摇跳转 → {[c.name.split('(')[0] for c in r1]}")
    print(f"虚假关闭   → {[c.name.split('(')[0] for c in r2]}")
    assert len(r1) == 2 and len(r2) == 3, "渠道匹配数量不符"

    print("\n" + "=" * 56)
    print("举报文书生成示例(摇一摇误触)")
    print("=" * 56)
    text = build_report(
        app_name="某某天气",
        v_key="shake",
        when="2026-08-26 08:30",
        device="小米 14 / HyperOS 2.0",
        detail="手机正常拿在手里走路,未做任何摇晃动作,打开该应用即被跳转至某购物 App。",
    )
    print(text)
    for block in ("【举报对象】", "【违规事实】", "【涉嫌违反的规定】",
                  "【证据材料】", "【诉求】", "【建议受理渠道】"):
        assert block in text, f"文书缺少 {block}"

    print("\n" + "=" * 56)
    print("自然语言识别引擎验证")
    print("=" * 56)
    cases = [
        ("手机就拿在手里走路,一打开就自己跳到淘宝去了", "shake"),
        ("广告全屏铺满,关不掉,也没有关闭按钮", "no_close"),
        ("点了关闭按钮反而开始下载了", "fake_close"),
        ("弹窗一个接一个,关不完", "nested"),
        ("写着3秒后跳过,数完了还在播", "fake_countdown"),
        ("弹出恭喜获得100元券,点进去是广告", "bait"),
        # 组合词规则用例(中间插字也能命中)
        ("点了那个关闭按钮,结果反而跳到别的页面了", "fake_close"),
        ("我什么都没点,它自己就下载了一个 App", "forced_redirect"),
    ]
    for text, expect in cases:
        got = infer_violation(text)
        assert got and got[0][0] == expect, f"识别错误: {text} -> {got}"
        print(f"[{expect:<14}] {text}  命中:{'、'.join(got[0][2])}")
    assert infer_violation("今天天气不错") == [], "无关文本不应命中"
    assert "墨迹天气" in suggest_apps("天气"), "App 联想失败"
    print("(无关文本返回空、App 联想均正常)")
    print("\n全部验证通过")


if __name__ == "__main__":
    main()
