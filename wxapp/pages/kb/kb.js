// 违规知识库页:接口走云托管「云调用」
const req = require('../../utils/cloud.js').req;

Page({
  data: { violations: [], channels: [] },

  onLoad() {
    req('/api/violations').then(list => {
      this.setData({ violations: list });
    }).catch(() => wx.showToast({ title: '网络异常,请稍后再试', icon: 'none' }));
    req('/api/channels').then(list => {
      this.setData({ channels: list });
    }).catch(() => {});
  }
});
