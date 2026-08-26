# -*- coding: utf-8 -*-
"""广告卫士 —— Streamlit 交互网页版

启动方式(在 ad-guardian 目录下):
    streamlit run app.py

页面结构(三个标签页):
- 一键举报 : 一句话描述+截图 → 自动识别违规类型/时间 → 确认信息 → 生成文书 → 复制去举报
- 违规知识库: 8 类违规广告的现象、法规依据、举报渠道速查
- 自救指南 : 不等举报生效,先保护自己的 3 个设置(关传感器权限等)

设计原则:
- 面向普通用户(尤其长辈),全程说人话,法规依据折叠在详情里
- 文书措辞客观("涉嫌"而非"违法"),提高受理成功率
- 自动化优先:用户只说一句话+传截图,系统推断其余字段,用户只做确认
"""

import streamlit as st

from adguardian import (
    VIOLATIONS, CHANNELS, COMMON_APPS,
    match_channels, evidence_tips, build_report,
    infer_violation, extract_shot_time,
)
from adguardian.vision import analyze_screenshot, VisionError

st.set_page_config(page_title="广告卫士", page_icon="🛡️", layout="centered")

st.title("🛡️ 广告卫士")
st.caption("遇到关不掉的广告、摇一摇乱跳转?这里帮你取证、生成举报文书,直达官方举报渠道。")

tab_report, tab_kb, tab_self = st.tabs(["📝 一键举报", "📚 违规知识库", "🧰 自救指南"])

# ============================================================
# 标签页一:一键举报
# ============================================================
with tab_report:
    st.subheader("第 1 步:告诉我们发生了什么")
    desc = st.text_area(
        "用一句话描述你遇到的广告",
        placeholder="例:手机就拿在手里走路,一打开这个 App 就自己跳到淘宝去了",
    )
    shots = st.file_uploader(
        "上传截图(可选,系统会自动读取拍摄时间;开启 AI 后可直接看图识别)",
        type=["png", "jpg", "jpeg"], accept_multiple_files=True,
    )

    with st.expander("🤖 AI 设置(可选:免费多模态模型看图识别,准确率更高)"):
        use_ai = st.checkbox("启用 AI 视觉识别")
        api_key = st.text_input(
            "智谱 API 密钥(免费注册:open.bigmodel.cn → 个人中心 → API密钥)",
            type="password",
        )
        st.caption("密钥只保存在你的浏览器里,不会上传到任何地方;截图仅发给智谱官方接口做识别。")

    if st.button("🔍 智能识别", type="primary", use_container_width=True):
        st.session_state.inferred = infer_violation(desc)
        st.session_state.shot_time = ""
        st.session_state.vision_result = None
        st.session_state.vision_error = ""
        if shots:
            st.session_state.shot_time = extract_shot_time(shots[0])
            if use_ai:
                try:
                    shots[0].seek(0)
                    st.session_state.vision_result = analyze_screenshot(
                        shots[0].read(), api_key)
                except VisionError as e:
                    st.session_state.vision_error = str(e)

    inferred = st.session_state.get("inferred", [])
    vision = st.session_state.get("vision_result")
    if st.session_state.get("vision_error"):
        st.warning(f"AI 识别未成功:{st.session_state.vision_error}(已自动退回文字识别)")

    st.divider()
    st.subheader("第 2 步:确认违规类型")
    if vision:
        with st.container(border=True):
            st.markdown("**🤖 AI 看图分析结果**")
            if vision.get("has_violation"):
                st.markdown(f"判断:**{vision.get('category', '')}**")
                st.markdown(f"关闭按钮:{vision.get('close_button', '无法判断')}")
                st.markdown(f"倒计时:{vision.get('countdown', '无法判断')}")
                if vision.get("deceptive_text"):
                    st.markdown(f"诱骗文案:「{vision['deceptive_text']}」")
                if vision.get("summary"):
                    st.info(vision["summary"])
            else:
                st.markdown("这张截图里没有发现明显的违规广告(如果是跳转瞬间,建议改用录屏取证)")

    # 双引擎融合:AI 看图结果优先,文字识别候选次之,去重后供用户确认
    cand_keys = []
    if vision and vision.get("key"):
        cand_keys.append(vision["key"])
    for k, _, _ in inferred:
        if k not in cand_keys:
            cand_keys.append(k)

    if cand_keys:
        top_key = cand_keys[0]
        src = "AI 看图" if (vision and vision.get("key") == top_key) else "文字识别"
        st.success(f"**识别结果:{VIOLATIONS[top_key].name}**(来源:{src})")
        if len(cand_keys) > 1:
            others = " / ".join(VIOLATIONS[k].name for k in cand_keys[1:])
            st.caption(f"其他可能:{others}")
        if st.session_state.get("shot_time"):
            st.caption(f"已从截图中读取拍摄时间:{st.session_state.shot_time}")
        keys = cand_keys + ["manual"]
        labels = {k: VIOLATIONS[k].name for k in keys if k != "manual"}
        labels["manual"] = "都不对,我手动选"
        idx = st.radio("识别对了吗?(不对可切换)", range(len(keys)),
                       format_func=lambda i: labels[keys[i]],
                       label_visibility="collapsed")
        chosen_key = keys[idx]
    else:
        if desc.strip() and "inferred" in st.session_state:
            st.warning("没有从描述中识别出特征词,请手动选择下方类型")
        chosen_key = "manual"

    if chosen_key == "manual":
        v_keys = list(VIOLATIONS.keys())
        v_names = [VIOLATIONS[k].name for k in v_keys]
        idx = st.radio("手动选择类型", range(len(v_keys)),
                       format_func=lambda i: v_names[i], label_visibility="collapsed")
        chosen_key = v_keys[idx]

    v = VIOLATIONS[chosen_key]
    st.info(f"**现象**:{v.symptom}")

    with st.expander("取证要点(先固定证据,再生成文书)"):
        for i, e in enumerate(evidence_tips(v.key), 1):
            st.markdown(f"{i}. {e}")
        st.caption("提示:手机自带录屏功能在「下拉控制中心」里,截图会自动带时间戳。")

    st.divider()
    st.subheader("第 3 步:确认基本信息(已尽量帮你自动填好)")
    c1, c2 = st.columns(2)
    with c1:
        options = ["手动输入..."] + COMMON_APPS
        guess = str(vision.get("app_guess", "")).strip() if vision else ""
        default_idx = options.index(guess) if guess in options else 0
        app_pick = st.selectbox("被举报 App", options, index=default_idx)
        if guess and guess not in options:
            st.caption(f"AI 猜测是「{guess}」,可在下方手动输入")
        if app_pick == "手动输入...":
            app_name = st.text_input("输入 App 名称", value=guess,
                                     placeholder="如:某某天气")
        else:
            app_name = app_pick
    with c2:
        device = st.text_input("你的手机型号", placeholder="如:小米 14 / HyperOS 2.0")
    when = st.text_input("事发时间", value=st.session_state.get("shot_time", ""),
                         placeholder="上传截图可自动读取;也可手动填,如:2026-08-26 08:30")
    detail_default = desc.strip()
    if vision and vision.get("summary"):
        detail_default = (detail_default + "\n" if detail_default else "") \
                         + f"[AI 看图记录]{vision['summary']}"
    detail = st.text_area("补充描述(已自动带上你的描述和 AI 观察)",
                          value=detail_default)

    st.divider()
    if st.button("生成举报文书", type="primary", use_container_width=True):
        if not app_name.strip():
            st.error("请先填写被举报 App 的名称")
        else:
            text = build_report(app_name, v.key, when or "未填写",
                                device or "未填写", detail)
            st.subheader("第 4 步:复制文书,前往举报渠道提交")
            st.code(text, language=None)
            st.success("文书已生成!长按/选中上方文字复制,粘贴到下面的举报渠道即可。")

            chs = match_channels(v.key)
            for ch in chs:
                with st.container(border=True):
                    st.markdown(f"**{ch.name}**")
                    st.markdown(f"受理范围:{ch.scope}")
                    st.markdown(f"入口:{ch.entry}")
                    steps_md = "\n".join(f"{i}. {s}" for i, s in enumerate(ch.steps, 1))
                    with st.expander("操作步骤"):
                        st.markdown(steps_md)
                    st.caption(f"处理时限:{ch.sla}")

# ============================================================
# 标签页二:违规知识库
# ============================================================
with tab_kb:
    st.subheader("8 类被明令禁止的违规广告")
    st.caption("依据《广告法》《互联网广告管理办法》《互联网弹窗信息推送服务管理规定》及工信部专项整治要求整理(2026 年 8 月)。")
    for v in VIOLATIONS.values():
        with st.container(border=True):
            st.markdown(f"**{v.name}**")
            st.markdown(f"现象:{v.symptom}")
            with st.expander("法规依据"):
                for b in v.basis:
                    st.markdown(f"- {b}")

    st.divider()
    st.subheader("4 个官方举报渠道")
    for ch in CHANNELS.values():
        with st.container(border=True):
            st.markdown(f"**{ch.name}**")
            st.markdown(f"管什么:{ch.scope}")
            st.markdown(f"在哪举报:{ch.entry}")

# ============================================================
# 标签页三:自救指南
# ============================================================
with tab_self:
    st.subheader("不等举报生效,先保护自己")
    st.markdown("""
举报是治本,但要等监管处理。下面 3 个设置可以**立刻**减少骚扰:

**1. 关掉 App 的"获取设备动作与方向"权限(根治摇一摇跳转)**
- 安卓:设置 → 应用管理 → 逐个检查常用 App → 权限 → 找到「获取设备动作与方向」(或「身体传感器」)→ 改为"拒绝"或"仅使用期间允许"
- 原理:摇一摇跳转靠陀螺仪感知晃动,关掉权限它就成了"瞎子"

**2. 关闭个性化广告推荐**
- 大多数 App:设置 → 隐私 → 广告 → 关闭"个性化广告推荐"
- 效果:广告数量不变,但不会再用你的浏览记录精准"钓鱼"

**3. 手机系统自带的"广告拦截/纯净模式"**
- 华为:设置 → 隐私 → 广告与隐私 → 限制广告跟踪
- 小米:设置 → 密码与安全 → 系统安全 → 广告过滤
- 各品牌位置略有不同,可在设置里搜索"广告"

---

**免责声明**:本工具仅提供取证引导与文书模板,内容基于公开法规整理,
不构成法律意见;举报请如实陈述,不得捏造事实诬告。
""")
