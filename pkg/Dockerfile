FROM soulter/astrbot:latest

# 安装 nsjail 依赖和构建工具
RUN apt-get update && apt-get install -y \
    autoconf bison flex gcc g++ git \
    libprotobuf-dev libnl-route-3-dev \
    libtool make pkg-config protobuf-compiler \
    gawk procps xxd \
    dnsutils iputils-ping wget iproute2 netcat-openbsd \
    debianutils telnet \
    && cd /tmp \
    && git clone --depth 1 https://github.com/google/nsjail.git \
    && cd nsjail \
    && make \
    && mv nsjail /usr/local/bin/ \
    && cd / \
    && rm -rf /tmp/nsjail

# 安装 Python 包管理工具和虚拟环境
RUN apt-get install -y python3-virtualenv \
    && pip3 install --no-cache-dir --break-system-packages uv pdm poetry

# 安装 Playwright 及其依赖
RUN pip3 install --no-cache-dir --break-system-packages playwright \
    && playwright install --with-deps chromium

# 安装 Node.js 包管理工具（npm 通常随 Node.js 自带）
RUN npm install -g yarn

# 创建 AstrBot 目录结构（用于挂载 skills 目录）
RUN mkdir -p /AstrBot/data

# 清理
RUN apt-get clean && rm -rf /var/lib/apt/lists/*
