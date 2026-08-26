// 举报记录页:本地存储,自动计算已过工作日,满 15 个工作日提醒查结果
function workdaysSince(dateStr) {
  const start = new Date(dateStr.replace(' ', 'T'));
  const now = new Date();
  let days = 0;
  const d = new Date(start);
  while (d < now) {
    d.setDate(d.getDate() + 1);
    const w = d.getDay();
    if (w !== 0 && w !== 6) days++;  // 跳过周末
  }
  return days;
}

Page({
  data: { records: [] },

  // 用 onShow 而非 onLoad:从举报页切回来时自动刷新
  onShow() {
    const list = wx.getStorageSync('reportRecords') || [];
    list.forEach(r => {
      r.days = workdaysSince(r.submitTime);
      r.due = r.days >= 15;
      r.channelText = (r.channelNames || []).join('、');  // 数组转顿号分隔文本便于展示
    });
    this.setData({ records: list });
  },

  removeRecord(e) {
    const id = e.currentTarget.dataset.id;
    wx.showModal({
      title: '删除这条记录?',
      success: res => {
        if (res.confirm) {
          const list = (wx.getStorageSync('reportRecords') || []).filter(r => r.id !== id);
          wx.setStorageSync('reportRecords', list);
          this.onShow();
        }
      }
    });
  }
});
