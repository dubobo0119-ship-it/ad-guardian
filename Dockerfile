# 广告卫士 —— 微信云托管部署镜像
# 构建方式(推荐在云托管控制台用"代码部署"自动构建,本地无需装 Docker):
#   控制台 → 新建服务 → 部署方式选"代码包部署" → 上传本目录(或关联仓库)
# 若本地已有 Docker,也可手动验证:
#   docker build -t adguardian .
#   docker run -p 80:80 adguardian

FROM python:3.9-slim

WORKDIR /app

# 依赖:接口层三件套 + AI 看图所需
RUN pip install --no-cache-dir \
    fastapi "uvicorn[standard]" python-multipart \
    requests pillow \
    -i https://mirrors.cloud.tencent.com/pypi/simple

# 只拷贝运行必需的文件
COPY adguardian ./adguardian
COPY api.py ./

# AI 看图识别的智谱密钥(可选功能)不写死在镜像里,避免泄露进镜像历史。
# 运行时通过环境变量注入:
#   本地: $env:ADGUARDIAN_ZHIPU_KEY='你的密钥'; python api.py
#   云托管: 服务设置 → 环境变量 → 添加 ADGUARDIAN_ZHIPU_KEY
# 未配置时接口仍可运行,仅 /api/analyze 降级返回失败提示。

# 云托管默认监听 80 端口(容器内必须绑 0.0.0.0,不能像本地那样只绑 127.0.0.1)
EXPOSE 80
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "80"]
