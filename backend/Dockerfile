FROM python:3.12-slim

# ── 换用国内镜像源 ──
#
# 原版直接用 deb.debian.org 与 deb.nodesource.com，这两个在国内会被连接重置
# （实测 curl 报 "Recv failure: Connection reset by peer"），
# 结果是：在国内服务器上完全无法构建这个镜像。
# 换成阿里云镜像后，Mac 与国内服务器都能顺利构建。
RUN set -eux; \
    if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
        sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources; \
    else \
        sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list; \
    fi

# ── 安装 Node.js（用于运行 ima_api.cjs）──
#
# 不再用 deb.nodesource.com 的一键脚本，改为从阿里云镜像下载官方二进制包。
# 用 TARGETARCH 适配架构，这样 Mac(arm64) 与云服务器(amd64) 都能构建同一个 Dockerfile。
ARG NODE_VERSION=20.20.2
RUN set -eux; \
    case "${TARGETARCH:-amd64}" in \
        amd64) node_arch=x64 ;; \
        arm64) node_arch=arm64 ;; \
        *) echo "不支持的架构: ${TARGETARCH}" >&2; exit 1 ;; \
    esac; \
    apt-get update; \
    apt-get install -y --no-install-recommends curl ca-certificates xz-utils; \
    curl -fsSL "https://mirrors.aliyun.com/nodejs-release/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-${node_arch}.tar.xz" \
        -o /tmp/node.tar.xz; \
    tar -xJf /tmp/node.tar.xz -C /usr/local --strip-components=1; \
    rm -f /tmp/node.tar.xz; \
    apt-get clean; \
    rm -rf /var/lib/apt/lists/*; \
    node -v; \
    npm -v

WORKDIR /app

# ── 安装 Python 依赖（pip 也走阿里云，国内快很多）──
RUN pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/ \
    && pip config set global.trusted-host mirrors.aliyun.com

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建必要目录
RUN mkdir -p /app/config

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
