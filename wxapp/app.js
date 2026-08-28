// 广告卫士小程序入口:全局初始化云能力(官方要求全局只 init 一次)
App({
  onLaunch() {
    if (wx.cloud) {
      wx.cloud.init({
        env: 'prod-d7gx1z8bf5676a8b4',
        traceUser: false,
        fail: err => console.warn('云环境初始化失败,接口将自动降级为公网域名:', err)
      });
    }
  }
});
