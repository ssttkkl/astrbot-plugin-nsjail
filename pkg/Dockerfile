FROM soulter/astrbot:latest

# 第1层：安装 JRE 和字体（经常变动的依赖）
RUN apt-get update && apt-get install -y \
    openjdk-21-jre-headless \
    fonts-wqy-microhei \
    fonts-wqy-zenhei \
    fonts-noto-cjk \
    fontconfig \
    && fc-cache -fv \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 第2层：安装 nsjail（编译耗时，很少变动）
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

# 第3层：修改 AstrBot 代码
RUN sed -i '/if runtime == "none":/,/Computer Use in the AstrBot WebUI -> Config."/d' /AstrBot/astrbot/core/astr_main_agent.py

# 第4层：安装 Python 工具
RUN apt-get update && apt-get install -y python3-virtualenv python3.13-venv \
    && pip3 install --no-cache-dir --break-system-packages uv pdm poetry \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 第5层：安装 Playwright
RUN pip3 install --no-cache-dir --break-system-packages playwright \
    && playwright install --with-deps chromium

# 第6层：安装 Node.js 工具
RUN npm install -g yarn

# 第7层：创建目录
RUN mkdir -p /AstrBot/data

# 第8层：配置用户命名空间
RUN echo 'root:100000:65536' >> /etc/subuid \
    && echo 'root:100000:65536' >> /etc/subgid
