FROM soulter/astrbot:latest

RUN apt-get update && apt-get install -y     autoconf bison flex gcc g++ git     libprotobuf-dev libnl-route-3-dev     libtool make pkg-config protobuf-compiler     && cd /tmp     && git clone --depth 1 https://github.com/google/nsjail.git     && cd nsjail     && make     && mv nsjail /usr/local/bin/     && cd /     && rm -rf /tmp/nsjail     && apt-get clean     && rm -rf /var/lib/apt/lists/*

# 安装 JRE 21
RUN apt-get update && apt-get install -y     openjdk-21-jre-headless     && apt-get clean     && rm -rf /var/lib/apt/lists/*

# 安装中文字体
RUN apt-get update && apt-get install -y     fonts-wqy-microhei     fonts-wqy-zenhei     fonts-noto-cjk     fontconfig     && fc-cache -fv     && apt-get clean     && rm -rf /var/lib/apt/lists/*

# 配置 subuid 和 subgid 用于用户命名空间
RUN echo 'root:100000:65536' >> /etc/subuid     && echo 'root:100000:65536' >> /etc/subgid
