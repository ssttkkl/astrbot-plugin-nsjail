FROM soulter/astrbot:latest

# 安装 nsjail 依赖
RUN apt-get update && apt-get install -y \
    autoconf bison flex gcc g++ git \
    libprotobuf-dev libnl-route-3-dev \
    libtool make pkg-config protobuf-compiler \
    debootstrap \
    && cd /tmp \
    && git clone --depth 1 https://github.com/google/nsjail.git \
    && cd nsjail \
    && make \
    && mv nsjail /usr/local/bin/ \
    && cd / \
    && rm -rf /tmp/nsjail

# 创建最小的 chroot 环境（不包含 nodejs/npm）
RUN mkdir -p /nsjail-root && \
    debootstrap --variant=minbase \
    --include=python3,python3-pip,python3-venv,python3-numpy,python3-scipy,python3-pandas,python3-matplotlib,bash,coreutils,curl,wget \
    stable /nsjail-root http://deb.debian.org/debian

# 在 chroot 环境中安装 Node.js（使用 NodeSource）
RUN chroot /nsjail-root bash -c '\
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs'

# 在 chroot 环境中安装额外的 Python 包
RUN chroot /nsjail-root pip3 install --no-cache-dir --break-system-packages \
    sympy \
    scikit-learn \
    seaborn \
    plotly

# 创建 AstrBot 目录结构（用于挂载 skills 目录）
RUN mkdir -p /nsjail-root/AstrBot/data

# 清理
RUN rm -rf /nsjail-root/var/cache/apt/* /nsjail-root/var/lib/apt/lists/* && \
    apt-get clean && rm -rf /var/lib/apt/lists/*
