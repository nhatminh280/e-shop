-- V17__chat_gateway_persistence.sql
-- Stores production chatbot sessions, messages, traces, and confirmable draft actions.
-- Dialect: PostgreSQL

BEGIN;

CREATE TABLE IF NOT EXISTS chat_sessions (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id               UUID REFERENCES users(id) ON DELETE CASCADE,
  anonymous_session_id  VARCHAR(128),
  status                VARCHAR(24) NOT NULL DEFAULT 'OPEN',
  created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_message_at       TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_updated_at
  ON chat_sessions(user_id, updated_at DESC)
  WHERE user_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_chat_sessions_anonymous
  ON chat_sessions(anonymous_session_id)
  WHERE anonymous_session_id IS NOT NULL;

DROP TRIGGER IF EXISTS trg_chat_sessions_updated_at ON chat_sessions;
CREATE TRIGGER trg_chat_sessions_updated_at
  BEFORE UPDATE ON chat_sessions
  FOR EACH ROW
  EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS chat_messages (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id      UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
  user_id         UUID REFERENCES users(id) ON DELETE SET NULL,
  role            VARCHAR(24) NOT NULL,
  body            TEXT NOT NULL,
  intent          VARCHAR(80),
  response_type   VARCHAR(80),
  trace_id        VARCHAR(128),
  latency_ms      NUMERIC,
  fallback_count  INTEGER NOT NULL DEFAULT 0,
  payload_json    JSONB,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_session_created_at
  ON chat_messages(session_id, created_at);

CREATE INDEX IF NOT EXISTS idx_chat_messages_trace_id
  ON chat_messages(trace_id)
  WHERE trace_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_chat_messages_intent
  ON chat_messages(intent)
  WHERE intent IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_chat_messages_response_type
  ON chat_messages(response_type)
  WHERE response_type IS NOT NULL;

CREATE TABLE IF NOT EXISTS chat_tool_calls (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id        UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
  message_id        UUID NOT NULL REFERENCES chat_messages(id) ON DELETE CASCADE,
  trace_id          VARCHAR(128),
  tool_name         VARCHAR(120) NOT NULL,
  status            VARCHAR(40) NOT NULL,
  latency_ms        NUMERIC,
  request_summary   TEXT,
  response_summary  TEXT,
  input_json        JSONB,
  error_message     TEXT,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_tool_calls_message
  ON chat_tool_calls(message_id);

CREATE INDEX IF NOT EXISTS idx_chat_tool_calls_trace_id
  ON chat_tool_calls(trace_id)
  WHERE trace_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_chat_tool_calls_tool_status
  ON chat_tool_calls(tool_name, status);

CREATE TABLE IF NOT EXISTS chat_node_traces (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id          UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
  message_id          UUID NOT NULL REFERENCES chat_messages(id) ON DELETE CASCADE,
  trace_id            VARCHAR(128),
  node_name           VARCHAR(120) NOT NULL,
  intent              VARCHAR(80),
  status              VARCHAR(40) NOT NULL,
  latency_ms          NUMERIC,
  intent_confidence   NUMERIC,
  routing_confidence  NUMERIC,
  input_summary       TEXT,
  output_summary      TEXT,
  error_message       TEXT,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_node_traces_message
  ON chat_node_traces(message_id);

CREATE INDEX IF NOT EXISTS idx_chat_node_traces_trace_id
  ON chat_node_traces(trace_id)
  WHERE trace_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS chat_draft_actions (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id    UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
  user_id       UUID REFERENCES users(id) ON DELETE SET NULL,
  message_id    UUID NOT NULL REFERENCES chat_messages(id) ON DELETE CASCADE,
  action_type   VARCHAR(80) NOT NULL,
  status        VARCHAR(24) NOT NULL,
  payload_json  JSONB NOT NULL,
  result_json   JSONB,
  expires_at    TIMESTAMPTZ NOT NULL,
  confirmed_at  TIMESTAMPTZ,
  completed_at  TIMESTAMPTZ,
  cancelled_at  TIMESTAMPTZ,
  error_message TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_draft_actions_session_status
  ON chat_draft_actions(session_id, status);

CREATE INDEX IF NOT EXISTS idx_chat_draft_actions_user_status
  ON chat_draft_actions(user_id, status)
  WHERE user_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_chat_draft_actions_expires_at
  ON chat_draft_actions(expires_at);

DROP TRIGGER IF EXISTS trg_chat_draft_actions_updated_at ON chat_draft_actions;
CREATE TRIGGER trg_chat_draft_actions_updated_at
  BEFORE UPDATE ON chat_draft_actions
  FOR EACH ROW
  EXECUTE FUNCTION set_updated_at();

COMMIT;
