FROM nikolaik/python-nodejs:python3.11-nodejs20


USER root


RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        git \
        jq \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*


RUN useradd --create-home --shell /bin/bash agent \
    && mkdir -p /workspace \
    && chown -R agent:agent /workspace


WORKDIR /workspace


USER agent


CMD ["/bin/bash"]
