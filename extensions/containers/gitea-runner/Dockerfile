# ==============================================================================
# OpenLabOps-Ops / OpenLabOps Gitea Act Runner Dockerfile
# Standard Reproducible Build (Replaces static image archives)
# ==============================================================================
FROM alpine:3.20

LABEL maintainer="OpenLabOps Operations Hub <ops@lab>"
LABEL description="Gitea Act Runner container for OpenLabOps-Ops / OpenLabOps CI/CD"

ENV ACT_RUNNER_VERSION="v0.2.11"
ENV ACT_RUNNER_SHA256="7a5e833793286bbfd9b59ce682bd41fc3f1c096bae1bb2a09b66ab2f6dacf90c"
ENV DOCKER_HOST="unix:///var/run/docker.sock"

# Install core runtime packages (Zero unnecessary overhead)
RUN apk add --no-cache \
    bash \
    curl \
    git \
    openssh-client \
    python3 \
    py3-pip \
    ansible-core \
    docker-cli \
    rsync \
    sudo \
    ca-certificates \
    tar \
    tzdata

# Download and install official Gitea act_runner binary with SHA256 verification
RUN BIN_NAME="act_runner-${ACT_RUNNER_VERSION#v}-linux-amd64" \
    && BASE_URL="https://gitea.com/gitea/runner/releases/download/${ACT_RUNNER_VERSION}" \
    && curl -fsSL -o /usr/local/bin/act_runner "${BASE_URL}/${BIN_NAME}" \
    && echo "${ACT_RUNNER_SHA256}  /usr/local/bin/act_runner" | sha256sum -c - \
    && chmod 0755 /usr/local/bin/act_runner

# Install Ansible collections into system-wide path for non-root runner
RUN ansible-galaxy collection install ansible.posix community.general -p /usr/share/ansible/collections

# Create dedicated non-root user and least-privilege workspace/data directories
RUN adduser -D -u 1000 runner \
    && mkdir -p /data /workspace \
    && chown -R runner:runner /data /workspace \
    && chmod 0750 /data /workspace

WORKDIR /data

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod 0755 /usr/local/bin/entrypoint.sh

USER runner

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["daemon"]

