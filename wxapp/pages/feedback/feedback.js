// 意见反馈页:使用者提意见,开发者在后台查看(接口走云托管「云调用」)
const req = require('../../utils/cloud.js').req;

Page({
  data: {
    content: '',
    contact: '',
    submitting: false
  },

  onContent(e) { this.setData({ content: e.detail.value }); },
  onContact(e) { this.setData({ contact: e.detail.value }); },

  submit() {
    const { content, contact } = this.data;
    if (!content.trim()) {
      wx.showToast({ title: '请先写下你的意见', icon: 'none' });
      return;
    }
    this.setData({ submitting: true });
    req('/api/feedback', 'POST', { content: content.trim(), contact: contact.trim() })
      .then(res => {
        if (res && res.ok) {
          this.setData({ content: '', contact: '' });
          wx.showToast({ title: '感谢你的反馈!', icon: 'success' });
        } else {
          wx.showToast({ title: '提交失败,请稍后再试', icon: 'none' });
        }
      })
      .catch(() => wx.showToast({ title: '网络异常,请稍后再试', icon: 'none' }))
      .finally(() => this.setData({ submitting: false }));
  }
});
