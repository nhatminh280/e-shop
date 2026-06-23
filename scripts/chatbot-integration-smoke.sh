#!/usr/bin/env bash

set -euo pipefail

API_BASE_URL="${API_BASE_URL:-http://127.0.0.1:8080}"
CHAT_AGENT_URL="${CHAT_AGENT_URL:-http://127.0.0.1:8010}"
CHAT_MESSAGE="${CHAT_MESSAGE:-ao khoac den size M}"
CHAT_EMAIL="${CHAT_EMAIL:-demo.customer@eshop.local}"
CHAT_PASSWORD="${CHAT_PASSWORD:-123456}"
TRACE_ID="${TRACE_ID:-trace-chatbot-smoke}"
REQUEST_ID="${REQUEST_ID:-req-chatbot-smoke}"
CHECK_AGENT_HEALTH="${CHECK_AGENT_HEALTH:-true}"

require_bin() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "Missing required command: $1" >&2
        exit 1
    fi
}

require_bin curl
require_bin jq

check_json_health() {
    local url="$1"
    local field="$2"
    local expected="$3"
    local body

    body="$(curl -fsS "$url")"
    local actual
    actual="$(printf '%s' "$body" | jq -r "$field")"
    if [[ "$actual" != "$expected" ]]; then
        echo "Health check failed for $url: expected $field=$expected but got $actual" >&2
        echo "$body" >&2
        exit 1
    fi
}

check_json_health "$API_BASE_URL/actuator/health" '.status' 'UP'

if [[ "$CHECK_AGENT_HEALTH" == "true" ]]; then
    check_json_health "$CHAT_AGENT_URL/agent/health" '.status' 'ok'
fi

login_response="$(
    curl -fsS \
        -X POST "$API_BASE_URL/api/auth/login" \
        -H 'Content-Type: application/json' \
        -d "{\"email\":\"$CHAT_EMAIL\",\"password\":\"$CHAT_PASSWORD\"}"
)"
token="$(printf '%s' "$login_response" | jq -r '.token')"
if [[ -z "$token" || "$token" == "null" ]]; then
    echo "Login succeeded without JWT token" >&2
    echo "$login_response" >&2
    exit 1
fi

chat_response="$(
    curl -fsS \
        -X POST "$API_BASE_URL/api/chat/messages" \
        -H "Authorization: Bearer $token" \
        -H 'Content-Type: application/json' \
        -H "x-trace-id: $TRACE_ID" \
        -H "x-request-id: $REQUEST_ID" \
        -d "{\"message\":\"$CHAT_MESSAGE\",\"clientContext\":{}}"
)"

session_id="$(printf '%s' "$chat_response" | jq -r '.sessionId')"
intent="$(printf '%s' "$chat_response" | jq -r '.intent')"
response_type="$(printf '%s' "$chat_response" | jq -r '.responseType')"
tool_count="$(printf '%s' "$chat_response" | jq '.toolCalls | length')"
trace_id="$(printf '%s' "$chat_response" | jq -r '.traceId')"

if [[ -z "$session_id" || "$session_id" == "null" ]]; then
    echo "Chat response is missing sessionId" >&2
    echo "$chat_response" >&2
    exit 1
fi
if [[ "$trace_id" != "$TRACE_ID" ]]; then
    echo "Chat response traceId mismatch: expected $TRACE_ID but got $trace_id" >&2
    echo "$chat_response" >&2
    exit 1
fi
if [[ "$intent" == "null" || -z "$intent" ]]; then
    echo "Chat response is missing intent" >&2
    echo "$chat_response" >&2
    exit 1
fi
if [[ "$response_type" == "null" || -z "$response_type" ]]; then
    echo "Chat response is missing responseType" >&2
    echo "$chat_response" >&2
    exit 1
fi
if [[ "$tool_count" -lt 1 ]]; then
    echo "Chat response did not contain any toolCalls" >&2
    echo "$chat_response" >&2
    exit 1
fi

history_response="$(
    curl -fsS \
        "$API_BASE_URL/api/chat/sessions/$session_id/messages?page=0&size=10" \
        -H "Authorization: Bearer $token"
)"

history_count="$(printf '%s' "$history_response" | jq '.messages | length')"
first_role="$(printf '%s' "$history_response" | jq -r '.messages[0].role')"
second_role="$(printf '%s' "$history_response" | jq -r '.messages[1].role')"
second_response_type="$(printf '%s' "$history_response" | jq -r '.messages[1].responseType')"
history_trace_ids="$(printf '%s' "$history_response" | jq -r '.messages[].traceId' | sort -u)"

if [[ "$history_count" -lt 2 ]]; then
    echo "Persisted history did not contain both user and assistant messages" >&2
    echo "$history_response" >&2
    exit 1
fi
if [[ "$first_role" != "USER" || "$second_role" != "ASSISTANT" ]]; then
    echo "Unexpected history message roles: $first_role, $second_role" >&2
    echo "$history_response" >&2
    exit 1
fi
if [[ "$second_response_type" != "$response_type" ]]; then
    echo "Persisted assistant responseType mismatch: expected $response_type but got $second_response_type" >&2
    echo "$history_response" >&2
    exit 1
fi
if [[ "$history_trace_ids" != "$TRACE_ID" ]]; then
    echo "Persisted history traceIds mismatch: expected only $TRACE_ID" >&2
    echo "$history_response" >&2
    exit 1
fi

jq -n \
    --arg apiBaseUrl "$API_BASE_URL" \
    --arg chatAgentUrl "$CHAT_AGENT_URL" \
    --arg sessionId "$session_id" \
    --arg traceId "$trace_id" \
    --arg intent "$intent" \
    --arg responseType "$response_type" \
    --argjson toolCount "$tool_count" \
    --argjson historyCount "$history_count" \
    '{
      ok: true,
      apiBaseUrl: $apiBaseUrl,
      chatAgentUrl: $chatAgentUrl,
      sessionId: $sessionId,
      traceId: $traceId,
      intent: $intent,
      responseType: $responseType,
      toolCount: $toolCount,
      historyCount: $historyCount
    }'
