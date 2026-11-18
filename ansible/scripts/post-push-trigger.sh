#!/bin/sh
# ==============================================================================
# Git Post-Push Hook Script
# Purpose: Trigger Gitea Action Workflow 'pull-docker-compose.yml' after git push
# ==============================================================================

GITEA_URL="${GITEA_URL:-http://gitea.local:3000}"
REPO_OWNER="${REPO_OWNER:-openlab}"
REPO_NAME="${REPO_NAME:-workflows}"
WORKFLOW_FILE="${WORKFLOW_FILE:-pull-docker-compose.yml}"

if [ -n "${GITEA_TOKEN}" ]; then
  TOKEN="${GITEA_TOKEN}"
elif [ -f "$HOME/.gitea_token" ]; then
  TOKEN="$(cat "$HOME/.gitea_token" | tr -d '\n\r')"
elif [ -f "/usr/local/bin/openlab/.gitea_token" ]; then
  TOKEN="$(cat "/usr/local/bin/openlab/.gitea_token" | tr -d '\n\r')"
elif [ -f "/usr/local/bin/openlab/.gitea_token" ]; then
  TOKEN="$(cat "/usr/local/bin/openlab/.gitea_token" | tr -d '\n\r')"
fi

if [ -z "${TOKEN}" ]; then
  echo "❌ [Git Hook Error] Gitea API Token not found."
  exit 1
fi

echo "🚀 [Git Hook] Triggering Workflow '${WORKFLOW_FILE}' via Gitea API..."

RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST "${GITEA_URL}/api/v1/repos/${REPO_OWNER}/${REPO_NAME}/actions/workflows/${WORKFLOW_FILE}/dispatches" \
  -H "Authorization: token ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"ref":"main"}')

if [ "${RESPONSE}" = "204" ] || [ "${RESPONSE}" = "200" ] || [ "${RESPONSE}" = "201" ]; then
  echo "✅ [Git Hook] Workflow '${WORKFLOW_FILE}' triggered successfully! (HTTP ${RESPONSE})"
else
  echo "⚠️ [Git Hook] Workflow dispatch response HTTP: ${RESPONSE}"
fi
