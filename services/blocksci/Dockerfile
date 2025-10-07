FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# Install dependencies
RUN apt-get update && apt-get install -y \
    cmake \
    build-essential \
    libtool \
    autotools-dev \
    automake \
    pkg-config \
    libssl-dev \
    libevent-dev \
    bsdmainutils \
    python3 \
    python3-pip \
    python3-dev \
    libboost-all-dev \
    libgmp-dev \
    libsparsehash-dev \
    libjsoncpp-dev \
    libjsonrpccpp-dev \
    libleveldb-dev \
    libsnappy-dev \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Note: BlockSci compilation is complex and time-consuming
# This is a simplified version. For production, use pre-built images
# or compile BlockSci separately

# Install Python packages
RUN pip3 install --no-cache-dir \
    jupyter \
    pandas \
    numpy \
    matplotlib \
    networkx

WORKDIR /app

# Create data directory
RUN mkdir -p /data/blocksci

# For now, this container serves as a placeholder
# Users should either:
# 1. Build BlockSci from source: https://github.com/citp/BlockSci
# 2. Use a pre-built BlockSci image
# 3. Use alternative Python analysis tools

CMD ["tail", "-f", "/dev/null"]
