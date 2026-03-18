FROM soulter/astrbot:latest

# 第1层：安装 nsjail（编译耗时，很少变动）
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
    && rm -rf /tmp/nsjail \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 第2层：安装 JRE 和字体
RUN apt-get update && apt-get install -y \
    openjdk-21-jre-headless \
    fonts-wqy-microhei \
    fonts-wqy-zenhei \
    fonts-noto-cjk \
    fontconfig \
    && fc-cache -fv \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 第3层：配置中文 locale
RUN apt-get update && apt-get install -y locales \
    && sed -i 's/^# *zh_CN.UTF-8/zh_CN.UTF-8/' /etc/locale.gen \
    && locale-gen zh_CN.UTF-8 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV LANG=zh_CN.UTF-8 \
    LC_ALL=zh_CN.UTF-8

# 第4层：安装 Python 工具和 Playwright
RUN apt-get update && apt-get install -y python3-virtualenv python3.13-venv \
    && pip3 install --no-cache-dir --break-system-packages uv pdm poetry \
    && pip3 install --no-cache-dir --break-system-packages playwright \
    && playwright install --with-deps chromium \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 第5层：安装 Node.js 工具
RUN npm install -g yarn
