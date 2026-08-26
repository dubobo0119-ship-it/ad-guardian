// 违规知识库页
const BASE = 'http://127.0.0.1:8000';

Page({
  data: { violations: [], channels: [] },

  onLoad() {
    wx.request({
      url: BASE + '/api/violations',
      success: res => this.setData({ violations: res.data }),
      fail: () => wx.showToast({ title: '请先启动后端服务', icon: 'none' })
    });
    wx.request({
      url: BASE + '/api/channels',
      success: res => this.setData({ channels: res.data })
    });
  }
});
