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
CHECK_DRAFT_FLOW="${CHECK_DRAFT_FLOW:-false}"
ADD_TO_CART_MESSAGE="${ADD_TO_CART_MESSAGE:-them cai dau tien vao gio}"
SUPPORT_MESSAGE="${SUPPORT_MESSAGE:-toi muon gap nhan vien ho tro}"

require_bin() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "Missing required command: $1" >&2
        exit 1
    fi
}

require_bin curl
require_bin jq

send_chat() {
    local token="$1"
    local message="$2"
    local session_id="${3:-}"
    local trace_id="$4"
    local request_id="$5"
    local payload

    payload="$(jq -cn \
        --arg message "$message" \
        --arg sessionId "$session_id" \
        '{
          message: $message,
          clientContext: {}
        } + (if $sessionId == "" then {} else {sessionId: $sessionId} end)')"

    curl -fsS \
        -X POST "$API_BASE_URL/api/chat/messages" \
        -H "Authorization: Bearer $token" \
        -H 'Content-Type: application/json' \
        -H "x-trace-id: $trace_id" \
        -H "x-request-id: $request_id" \
        -d "$payload"
}

fetch_history() {
    local token="$1"
    local session_id="$2"

    curl -fsS \
        "$API_BASE_URL/api/chat/sessions/$session_id/messages?page=0&size=20" \
        -H "Authorization: Bearer $token"
}

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

chat_response="$(send_chat "$token" "$CHAT_MESSAGE" "" "$TRACE_ID" "$REQUEST_ID")"

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

history_response="$(fetch_history "$token" "$session_id")"

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

draft_confirm_json='null'
draft_cancel_json='null'
support_confirm_json='null'
support_cancel_json='null'

if [[ "$CHECK_DRAFT_FLOW" == "true" ]]; then
    add_trace_id="${TRACE_ID}-add"
    add_request_id="${REQUEST_ID}-add"
    add_response="$(send_chat "$token" "$ADD_TO_CART_MESSAGE" "$session_id" "$add_trace_id" "$add_request_id")"
    add_response_type="$(printf '%s' "$add_response" | jq -r '.responseType')"
    add_needs_confirmation="$(printf '%s' "$add_response" | jq -r '.needsConfirmation')"
    add_action_type="$(printf '%s' "$add_response" | jq -r '.draftAction.actionType')"
    add_draft_action_id="$(printf '%s' "$add_response" | jq -r '.draftAction.draftActionId')"

    if [[ "$add_response_type" != "draft_action" ]]; then
        echo "Expected add-to-cart follow-up to produce draft_action but got $add_response_type" >&2
        echo "$add_response" >&2
        exit 1
    fi
    if [[ "$add_needs_confirmation" != "true" ]]; then
        echo "Expected add-to-cart follow-up to require confirmation" >&2
        echo "$add_response" >&2
        exit 1
    fi
    if [[ "$add_action_type" != "cart.add" ]]; then
        echo "Expected add-to-cart draft action type cart.add but got $add_action_type" >&2
        echo "$add_response" >&2
        exit 1
    fi
    if [[ -z "$add_draft_action_id" || "$add_draft_action_id" == "null" ]]; then
        echo "Draft add response is missing draftActionId" >&2
        echo "$add_response" >&2
        exit 1
    fi

    confirm_response="$(
        curl -fsS \
            -X POST "$API_BASE_URL/api/chat/actions/$add_draft_action_id/confirm" \
            -H "Authorization: Bearer $token"
    )"
    confirm_status="$(printf '%s' "$confirm_response" | jq -r '.status')"
    confirm_action_type="$(printf '%s' "$confirm_response" | jq -r '.actionType')"
    if [[ "$confirm_status" != "completed" || "$confirm_action_type" != "cart.add" ]]; then
        echo "Draft confirm did not complete successfully" >&2
        echo "$confirm_response" >&2
        exit 1
    fi

    confirm_history="$(fetch_history "$token" "$session_id")"
    confirm_history_count="$(printf '%s' "$confirm_history" | jq '.messages | length')"
    confirm_last_response_type="$(printf '%s' "$confirm_history" | jq -r '.messages[-1].responseType')"
    if [[ "$confirm_history_count" -lt 5 ]]; then
        echo "Confirm flow history did not record the expected action_result message" >&2
        echo "$confirm_history" >&2
        exit 1
    fi
    if [[ "$confirm_last_response_type" != "action_result" ]]; then
        echo "Confirm flow last responseType should be action_result but got $confirm_last_response_type" >&2
        echo "$confirm_history" >&2
        exit 1
    fi
    draft_confirm_json="$(jq -cn \
        --arg draftActionId "$add_draft_action_id" \
        --arg status "$confirm_status" \
        --arg actionType "$confirm_action_type" \
        --argjson historyCount "$confirm_history_count" \
        '{draftActionId: $draftActionId, status: $status, actionType: $actionType, historyCount: $historyCount}')"

    cancel_search_trace_id="${TRACE_ID}-cancel-search"
    cancel_search_request_id="${REQUEST_ID}-cancel-search"
    cancel_search_response="$(send_chat "$token" "$CHAT_MESSAGE" "" "$cancel_search_trace_id" "$cancel_search_request_id")"
    cancel_session_id="$(printf '%s' "$cancel_search_response" | jq -r '.sessionId')"
    if [[ -z "$cancel_session_id" || "$cancel_session_id" == "null" ]]; then
        echo "Cancel flow search response is missing sessionId" >&2
        echo "$cancel_search_response" >&2
        exit 1
    fi

    cancel_add_trace_id="${TRACE_ID}-cancel-add"
    cancel_add_request_id="${REQUEST_ID}-cancel-add"
    cancel_add_response="$(send_chat "$token" "$ADD_TO_CART_MESSAGE" "$cancel_session_id" "$cancel_add_trace_id" "$cancel_add_request_id")"
    cancel_add_response_type="$(printf '%s' "$cancel_add_response" | jq -r '.responseType')"
    cancel_action_type="$(printf '%s' "$cancel_add_response" | jq -r '.draftAction.actionType')"
    cancel_draft_action_id="$(printf '%s' "$cancel_add_response" | jq -r '.draftAction.draftActionId')"
    if [[ "$cancel_add_response_type" != "draft_action" || "$cancel_action_type" != "cart.add" ]]; then
        echo "Cancel flow add-to-cart step did not produce expected draft_action" >&2
        echo "$cancel_add_response" >&2
        exit 1
    fi
    if [[ -z "$cancel_draft_action_id" || "$cancel_draft_action_id" == "null" ]]; then
        echo "Cancel flow add response is missing draftActionId" >&2
        echo "$cancel_add_response" >&2
        exit 1
    fi

    cancel_response="$(
        curl -fsS \
            -X POST "$API_BASE_URL/api/chat/actions/$cancel_draft_action_id/cancel" \
            -H "Authorization: Bearer $token"
    )"
    cancel_status="$(printf '%s' "$cancel_response" | jq -r '.status')"
    cancel_result_action_type="$(printf '%s' "$cancel_response" | jq -r '.actionType')"
    if [[ "$cancel_status" != "cancelled" || "$cancel_result_action_type" != "cart.add" ]]; then
        echo "Draft cancel did not return cancelled cart.add" >&2
        echo "$cancel_response" >&2
        exit 1
    fi

    cancel_history="$(fetch_history "$token" "$cancel_session_id")"
    cancel_history_count="$(printf '%s' "$cancel_history" | jq '.messages | length')"
    cancel_last_response_type="$(printf '%s' "$cancel_history" | jq -r '.messages[-1].responseType')"
    if [[ "$cancel_history_count" -lt 5 ]]; then
        echo "Cancel flow history did not record the expected action_result message" >&2
        echo "$cancel_history" >&2
        exit 1
    fi
    if [[ "$cancel_last_response_type" != "action_result" ]]; then
        echo "Cancel flow last responseType should be action_result but got $cancel_last_response_type" >&2
        echo "$cancel_history" >&2
        exit 1
    fi
    draft_cancel_json="$(jq -cn \
        --arg draftActionId "$cancel_draft_action_id" \
        --arg status "$cancel_status" \
        --arg actionType "$cancel_result_action_type" \
        --arg sessionId "$cancel_session_id" \
        --argjson historyCount "$cancel_history_count" \
        '{draftActionId: $draftActionId, status: $status, actionType: $actionType, sessionId: $sessionId, historyCount: $historyCount}')"

    support_trace_id="${TRACE_ID}-support"
    support_request_id="${REQUEST_ID}-support"
    support_response="$(send_chat "$token" "$SUPPORT_MESSAGE" "" "$support_trace_id" "$support_request_id")"
    support_session_id="$(printf '%s' "$support_response" | jq -r '.sessionId')"
    support_response_type="$(printf '%s' "$support_response" | jq -r '.responseType')"
    support_action_type="$(printf '%s' "$support_response" | jq -r '.draftAction.actionType')"
    support_needs_confirmation="$(printf '%s' "$support_response" | jq -r '.needsConfirmation')"
    support_draft_action_id="$(printf '%s' "$support_response" | jq -r '.draftAction.draftActionId')"
    if [[ "$support_response_type" != "handoff" ]]; then
        echo "Expected support flow to produce handoff but got $support_response_type" >&2
        echo "$support_response" >&2
        exit 1
    fi
    if [[ "$support_action_type" != "support.handoff" || "$support_needs_confirmation" != "true" ]]; then
        echo "Expected support flow to require confirmation for support.handoff" >&2
        echo "$support_response" >&2
        exit 1
    fi
    if [[ -z "$support_draft_action_id" || "$support_draft_action_id" == "null" ]]; then
        echo "Support handoff response is missing draftActionId" >&2
        echo "$support_response" >&2
        exit 1
    fi

    support_confirm_response="$(
        curl -fsS \
            -X POST "$API_BASE_URL/api/chat/actions/$support_draft_action_id/confirm" \
            -H "Authorization: Bearer $token"
    )"
    support_confirm_status="$(printf '%s' "$support_confirm_response" | jq -r '.status')"
    support_confirm_action_type="$(printf '%s' "$support_confirm_response" | jq -r '.actionType')"
    if [[ "$support_confirm_status" != "completed" || "$support_confirm_action_type" != "support.handoff" ]]; then
        echo "Support draft confirm did not complete successfully" >&2
        echo "$support_confirm_response" >&2
        exit 1
    fi

    support_confirm_history="$(fetch_history "$token" "$support_session_id")"
    support_confirm_history_count="$(printf '%s' "$support_confirm_history" | jq '.messages | length')"
    support_confirm_last_response_type="$(printf '%s' "$support_confirm_history" | jq -r '.messages[-1].responseType')"
    if [[ "$support_confirm_history_count" -lt 3 ]]; then
        echo "Support confirm history did not record the expected action_result message" >&2
        echo "$support_confirm_history" >&2
        exit 1
    fi
    if [[ "$support_confirm_last_response_type" != "action_result" ]]; then
        echo "Support confirm last responseType should be action_result but got $support_confirm_last_response_type" >&2
        echo "$support_confirm_history" >&2
        exit 1
    fi
    support_confirm_json="$(jq -cn \
        --arg draftActionId "$support_draft_action_id" \
        --arg status "$support_confirm_status" \
        --arg actionType "$support_confirm_action_type" \
        --arg sessionId "$support_session_id" \
        --argjson historyCount "$support_confirm_history_count" \
        '{draftActionId: $draftActionId, status: $status, actionType: $actionType, sessionId: $sessionId, historyCount: $historyCount}')"

    support_cancel_trace_id="${TRACE_ID}-support-cancel"
    support_cancel_request_id="${REQUEST_ID}-support-cancel"
    support_cancel_response="$(send_chat "$token" "$SUPPORT_MESSAGE" "" "$support_cancel_trace_id" "$support_cancel_request_id")"
    support_cancel_session_id="$(printf '%s' "$support_cancel_response" | jq -r '.sessionId')"
    support_cancel_draft_action_id="$(printf '%s' "$support_cancel_response" | jq -r '.draftAction.draftActionId')"
    support_cancel_action_type="$(printf '%s' "$support_cancel_response" | jq -r '.draftAction.actionType')"
    if [[ "$support_cancel_action_type" != "support.handoff" ]]; then
        echo "Support cancel flow did not produce support.handoff draft" >&2
        echo "$support_cancel_response" >&2
        exit 1
    fi
    if [[ -z "$support_cancel_draft_action_id" || "$support_cancel_draft_action_id" == "null" ]]; then
        echo "Support cancel response is missing draftActionId" >&2
        echo "$support_cancel_response" >&2
        exit 1
    fi

    support_cancel_result="$(
        curl -fsS \
            -X POST "$API_BASE_URL/api/chat/actions/$support_cancel_draft_action_id/cancel" \
            -H "Authorization: Bearer $token"
    )"
    support_cancel_status="$(printf '%s' "$support_cancel_result" | jq -r '.status')"
    support_cancel_result_action_type="$(printf '%s' "$support_cancel_result" | jq -r '.actionType')"
    if [[ "$support_cancel_status" != "cancelled" || "$support_cancel_result_action_type" != "support.handoff" ]]; then
        echo "Support draft cancel did not return cancelled support.handoff" >&2
        echo "$support_cancel_result" >&2
        exit 1
    fi

    support_cancel_history="$(fetch_history "$token" "$support_cancel_session_id")"
    support_cancel_history_count="$(printf '%s' "$support_cancel_history" | jq '.messages | length')"
    support_cancel_last_response_type="$(printf '%s' "$support_cancel_history" | jq -r '.messages[-1].responseType')"
    if [[ "$support_cancel_history_count" -lt 3 ]]; then
        echo "Support cancel history did not record the expected action_result message" >&2
        echo "$support_cancel_history" >&2
        exit 1
    fi
    if [[ "$support_cancel_last_response_type" != "action_result" ]]; then
        echo "Support cancel last responseType should be action_result but got $support_cancel_last_response_type" >&2
        echo "$support_cancel_history" >&2
        exit 1
    fi
    support_cancel_json="$(jq -cn \
        --arg draftActionId "$support_cancel_draft_action_id" \
        --arg status "$support_cancel_status" \
        --arg actionType "$support_cancel_result_action_type" \
        --arg sessionId "$support_cancel_session_id" \
        --argjson historyCount "$support_cancel_history_count" \
        '{draftActionId: $draftActionId, status: $status, actionType: $actionType, sessionId: $sessionId, historyCount: $historyCount}')"
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
    --argjson draftConfirm "$draft_confirm_json" \
    --argjson draftCancel "$draft_cancel_json" \
    --argjson supportConfirm "$support_confirm_json" \
    --argjson supportCancel "$support_cancel_json" \
    '{
      ok: true,
      apiBaseUrl: $apiBaseUrl,
      chatAgentUrl: $chatAgentUrl,
      sessionId: $sessionId,
      traceId: $traceId,
      intent: $intent,
      responseType: $responseType,
      toolCount: $toolCount,
      historyCount: $historyCount,
      draftConfirm: $draftConfirm,
      draftCancel: $draftCancel,
      supportConfirm: $supportConfirm,
      supportCancel: $supportCancel
    }'
