// 接口双通道:优先云托管「云调用」(永不过期);初始化失败时自动降级为 HTTPS 公网域名
const ENV = 'prod-d7gx1z8bf5676a8b4';   // 云托管环境 ID
const SERVICE = 'adguardian';            // 服务名
// 公网访问域名(保底通道;若正式发布前更换了域名只需改这里)
const FALLBACK = 'https://adguardian-303063-11-1475315058.sh.run.tcloudbase.com';

let inited = false;      // 云调用初始化成功标记(首次成功后固定走云调用)
let cloudBroken = false; // 云调用不可用标记(一次失败后永久降级,不再重试)

function tryInit() {
  if (inited || cloudBroken) return inited;
  return new Promise(resolve => {
    try {
      wx.cloud.init({
        env: ENV,
        success: () => { inited = true; resolve(true); },
        fail: () => { cloudBroken = true; resolve(false); }
      });
    } catch (e) { cloudBroken = true; resolve(false); }
  });
}

// 降级通道:wx.request 直连公网域名(开发期需在本地设置勾选"不校验合法域名")
function fallbackReq(path, method, data) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: FALLBACK + path,
      method: method || 'GET',
      data: data,
      timeout: 60000,
      success: res => resolve(res.data),
      fail: err => reject(err)
    });
  });
}

// 普通请求:返回 Promise,resolve 业务返回的 JSON(自动选通道+失败降级)
function req(path, method, data) {
  return tryInit().then(ok => {
    if (!ok) return fallbackReq(path, method, data);
    return wx.cloud.callContainer({
      config: { env: ENV },
      serviceName: SERVICE,
      path: path,
      method: method || 'GET',
      data: data || {},
      timeout: 60000
    }).then(res => res.data)
      .catch(() => { cloudBroken = true; return fallbackReq(path, method, data); });
  });
}

// 上传文件(截图识别用):返回 Promise,resolve 业务返回的 JSON(自动选通道+失败降级)
function upload(path, filePath) {
  return tryInit().then(ok => {
    if (!ok) return fallbackUpload(path, filePath);
    return wx.cloud.callContainer({
      config: { env: ENV },
      serviceName: SERVICE,
      path: path,
      method: 'POST',
      filePath: filePath,
      name: 'file'
    }).then(res => (typeof res.data === 'string' ? JSON.parse(res.data) : res.data))
      .catch(() => { cloudBroken = true; return fallbackUpload(path, filePath); });
  });
}

function fallbackUpload(path, filePath) {
  return wx.uploadFile({
    url: FALLBACK + path,
    filePath: filePath,
    name: 'file'
  }).then(res => JSON.parse(res.data));
}

module.exports = { req, upload };
