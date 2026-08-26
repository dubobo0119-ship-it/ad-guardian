// 云托管「云调用」封装:小程序直连云容器,不走公网域名(默认域名会过期,此通道永不过期)
const ENV = 'prod-d7gx1z8bf5676a8b4';   // 云托管环境 ID
const SERVICE = 'adguardian';            // 服务名

let inited = false;
function ensureInit() {
  if (inited) return;
  wx.cloud.init({ env: ENV });
  inited = true;
}

// 普通请求:返回 Promise,resolve 业务返回的 JSON
function req(path, method, data) {
  ensureInit();
  return wx.cloud.callContainer({
    config: { env: ENV },
    serviceName: SERVICE,
    path: path,
    method: method || 'GET',
    data: data || {},
    timeout: 60000
  }).then(res => res.data);
}

// 上传文件(截图识别用):返回 Promise,resolve 业务返回的 JSON
function upload(path, filePath) {
  ensureInit();
  return wx.cloud.callContainer({
    config: { env: ENV },
    serviceName: SERVICE,
    path: path,
    method: 'POST',
    filePath: filePath,
    name: 'file'
  }).then(res => (typeof res.data === 'string' ? JSON.parse(res.data) : res.data));
}

module.exports = { req, upload };
