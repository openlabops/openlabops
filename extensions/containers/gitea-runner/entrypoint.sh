#!/bin/bash
# ==============================================================================
# OpenLabOps Gitea Act Runner Entrypoint Script
# ==============================================================================
set -e

REG_FILE="/data/.runner"
GITEA_INSTANCE_URL="${GITEA_INSTANCE_URL:-http://gitea.lab:3000}"
GITEA_RUNNER_REGISTRATION_TOKEN="${GITEA_RUNNER_REGISTRATION_TOKEN:-}"
GITEA_RUNNER_NAME="${GITEA_RUNNER_NAME:-openlab-act-runner}"
GITEA_RUNNER_LABELS="${GITEA_RUNNER_LABELS:-ansible:host,ubuntu-latest:docker://node:20-bookworm,alpine-latest:docker://alpine:3.20,native:host}"

if [ ! -f "$REG_FILE" ]; then
    if [ -z "$GITEA_RUNNER_REGISTRATION_TOKEN" ]; then
        echo "[*] Runner registration file $REG_FILE not found and GITEA_RUNNER_REGISTRATION_TOKEN is empty."
        echo "    Waiting for registration token via /data/token, environment, or direct registration..."
        while [ ! -f "$REG_FILE" ] && [ -z "${GITEA_RUNNER_REGISTRATION_TOKEN:-}" ]; do
            if [ -f "/data/token" ]; then
                GITEA_RUNNER_REGISTRATION_TOKEN=$(cat /data/token | tr -d '[:space:]')
                rm -f /data/token
                break
            fi
            sleep 2
        done
    fi

    if [ ! -f "$REG_FILE" ] && [ -n "${GITEA_RUNNER_REGISTRATION_TOKEN:-}" ]; then
        echo "[*] Registering Act Runner to Gitea at ${GITEA_INSTANCE_URL}..."
        act_runner register \
            --no-interactive \
            --instance "${GITEA_INSTANCE_URL}" \
            --token "${GITEA_RUNNER_REGISTRATION_TOKEN}" \
            --name "${GITEA_RUNNER_NAME}" \
            --labels "${GITEA_RUNNER_LABELS}"
        echo "[✓] Act Runner registered successfully."
    fi
fi

echo "[*] Starting Act Runner daemon..."
EXTRA_ARGS=""
if [ -n "${CONFIG_FILE:-}" ] && [ -f "${CONFIG_FILE}" ]; then
    EXTRA_ARGS="--config ${CONFIG_FILE}"
elif [ -f "/data/config.yaml" ]; then
    EXTRA_ARGS="--config /data/config.yaml"
fi

exec act_runner "$@" $EXTRA_ARGS

