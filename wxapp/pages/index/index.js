// 接口走微信云托管「云调用」(永不过期,无需配置域名白名单)
const cloud = require('../../utils/cloud.js');
const req = cloud.req;

Page({
  data: {
    desc: '',
    shotPath: '',
    useAI: true,
    violations: [],       // 知识库全量(手动选择用)
    candidates: [],       // 文字识别候选 [{key, name, score, hits}]
    chosenIdx: -1,        // 用户最终确认的类型在 candidates 中的下标
    vision: null,         // AI 看图结果
    visionError: '',
    apps: [],
    appIdx: 0,
    appNameManual: '',
    device: '',
    when: '',
    detail: '',
    reportText: '',
    channels: [],
    evidence: [],
    recognizing: false
  },

  onLoad() {
    req('/api/violations').then(list => {
      this.setData({ violations: list });
    }).catch(() => wx.showToast({ title: '网络异常,请稍后再试', icon: 'none' }));
    req('/api/apps').then(apps => {
      this.setData({ apps: ['手动输入...'].concat(apps) });
    }).catch(() => {});
  },

  onDesc(e) { this.setData({ desc: e.detail.value }); },
  onUseAI(e) { this.setData({ useAI: e.detail.value }); },
  onDevice(e) { this.setData({ device: e.detail.value }); },
  onWhen(e) { this.setData({ when: e.detail.value }); },
  onDetail(e) { this.setData({ detail: e.detail.value }); },
  onAppManual(e) { this.setData({ appNameManual: e.detail.value }); },
  onAppIdx(e) { this.setData({ appIdx: Number(e.detail.value) }); },

  chooseShot() {
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      success: res => this.setData({ shotPath: res.tempFiles[0].tempFilePath })
    });
  },

  // 智能识别:文字识别必跑;勾选 AI 且有截图时追加看图识别
  smartRecognize() {
    const { desc, shotPath, useAI, violations } = this.data;
    if (!desc.trim() && !shotPath) {
      wx.showToast({ title: '先描述一下或上传截图', icon: 'none' });
      return;
    }
    this.setData({ recognizing: true, vision: null, visionError: '' });

    const textPromise = desc.trim()
      ? req('/api/infer', 'POST', { text: desc })
      : Promise.resolve([]);

    const aiPromise = (useAI && shotPath)
      ? cloud.upload('/api/analyze', shotPath)
          .catch(() => ({ ok: false, error: '网络异常' }))
      : Promise.resolve(null);

    Promise.all([textPromise, aiPromise]).then(([inferList, vision]) => {
      // 双引擎融合:AI 看图结果优先,文字识别候选次之,去重
      const candKeys = [];
      if (vision && vision.ok && vision.key) candKeys.push(vision.key);
      (inferList || []).forEach(c => {
        if (candKeys.indexOf(c.key) < 0) candKeys.push(c.key);
      });
      const nameOf = key => {
        const v = violations.find(x => x.key === key);
        return v ? v.name : key;
      };
      const candidates = candKeys.map(key => ({ key, name: nameOf(key) }));
      const visionError = (vision && !vision.ok) ? vision.error : '';
      this.setData({
        candidates: candidates,
        chosenIdx: candidates.length ? 0 : -1,
        vision: (vision && vision.ok) ? vision : null,
        visionError: visionError,
        recognizing: false,
        // AI 猜的 App 名称自动带入手动输入框
        appNameManual: (vision && vision.ok && vision.app_guess) ? vision.app_guess : this.data.appNameManual,
        // AI 观察记录自动并入补充描述
        detail: (vision && vision.ok && vision.summary)
          ? (this.data.detail ? this.data.detail + '\n' : '') + '[AI看图记录]' + vision.summary
          : this.data.detail
      });
      if (!candidates.length) {
        wx.showToast({ title: '未识别出特征,请手动选择类型', icon: 'none' });
      }
    }).catch(() => {
      this.setData({ recognizing: false });
      wx.showToast({ title: '网络异常,请稍后再试', icon: 'none' });
    });
  },

  onChooseType(e) { this.setData({ chosenIdx: Number(e.detail.value) }); },

  generateReport() {
    const d = this.data;
    const appName = d.appIdx === 0 ? d.appNameManual.trim() : d.apps[d.appIdx];
    if (!appName) {
      wx.showToast({ title: '请填写被举报 App 名称', icon: 'none' });
      return;
    }
    if (d.chosenIdx < 0) {
      wx.showToast({ title: '请先智能识别或选择违规类型', icon: 'none' });
      return;
    }
    const vKey = d.candidates[d.chosenIdx].key;
    req('/api/report', 'POST', {
      app_name: appName,
      v_key: vKey,
      when: d.when || '未填写',
      device: d.device || '未填写',
      detail: d.detail
    }).then(r => {
      if (r.error) {
        wx.showToast({ title: r.error, icon: 'none' });
        return;
      }
      this.setData({
        reportText: r.text,
        channels: r.channels,
        evidence: r.evidence,
        // 记录页需要的信息,提交时一并存入本地
        lastAppName: appName,
        lastVName: d.candidates[d.chosenIdx].name
      });
      wx.showToast({ title: '文书已生成', icon: 'success' });
    }).catch(() => wx.showToast({ title: '生成失败,请稍后再试', icon: 'none' }));
  },

  // 复制文书前先弹证据清单提醒,用户确认后再复制(④证据清单提醒)
  copyReport() {
    const list = this.data.evidence.map((s, i) => (i + 1) + '. ' + s).join('\n');
    wx.showModal({
      title: '提交前检查证据清单',
      content: '请确认已备好以下材料:\n' + list + '\n\n确定复制文书?',
      confirmText: '复制',
      success: res => {
        if (res.confirm) {
          wx.setClipboardData({
            data: this.data.reportText,
            success: () => wx.showToast({ title: '已复制,去举报渠道粘贴即可', icon: 'none', duration: 2500 })
          });
        }
      }
    });
  },

  // 渠道直达:复制入口(网址或小程序名)并引导下一步(①渠道直达)
  goChannel(e) {
    const { go, name } = e.currentTarget.dataset;
    if (!go) {
      wx.showToast({ title: '请按上方入口指引前往', icon: 'none' });
      return;
    }
    const isUrl = go.indexOf('http') === 0;
    wx.setClipboardData({
      data: go,
      success: () => {
        wx.showModal({
          title: '前往「' + name + '」',
          content: isUrl
            ? '官网链接已复制,请到手机浏览器粘贴打开。'
            : '小程序名称「' + go + '」已复制,回微信首页下拉搜索即可打开。',
          showCancel: false,
          confirmText: '知道了'
        });
      }
    });
  },

  // 我提交了:举报记录存入本地,记录页 15 个工作日后提醒查结果(③举报记录)
  markSubmitted() {
    const d = this.data;
    const records = wx.getStorageSync('reportRecords') || [];
    records.unshift({
      id: Date.now(),
      submitTime: this.fmtNow(),
      appName: d.lastAppName,
      vName: d.lastVName,
      channelNames: d.channels.map(c => c.name)
    });
    wx.setStorageSync('reportRecords', records);
    wx.showToast({ title: '已记录,15 个工作日后可去查结果', icon: 'none', duration: 2500 });
  },

  fmtNow() {
    const t = new Date();
    const p = n => (n < 10 ? '0' + n : '' + n);
    return t.getFullYear() + '-' + p(t.getMonth() + 1) + '-' + p(t.getDate())
      + ' ' + p(t.getHours()) + ':' + p(t.getMinutes());
  }
});
