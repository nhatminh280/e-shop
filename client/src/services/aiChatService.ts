import api from "../config/axios";
import type { AiChatResponse } from "../types/aiChat";

interface SendMessageArgs {
  sessionId: string | null;
  message: string;
  token?: string | null;
  clientContext?: Record<string, unknown>;
}

interface ConfirmCancelArgs {
  draftActionId: string;
  token?: string | null;
}

function authHeaders(token: string | null | undefined): Record<string, string> {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function sendChatMessage({
  sessionId,
  message,
  token,
  clientContext,
}: SendMessageArgs): Promise<AiChatResponse> {
  const { data } = await api.post<AiChatResponse>(
    "/api/chat/messages",
    {
      sessionId,
      message,
      clientContext: clientContext ?? {},
    },
    { headers: authHeaders(token) }
  );
  return data;
}

export async function confirmDraftAction({
  draftActionId,
  token,
}: ConfirmCancelArgs): Promise<unknown> {
  const { data } = await api.post(
    `/api/chat/actions/${encodeURIComponent(draftActionId)}/confirm`,
    {},
    { headers: authHeaders(token) }
  );
  return data;
}

export async function cancelDraftAction({
  draftActionId,
  token,
}: ConfirmCancelArgs): Promise<unknown> {
  const { data } = await api.post(
    `/api/chat/actions/${encodeURIComponent(draftActionId)}/cancel`,
    {},
    { headers: authHeaders(token) }
  );
  return data;
}
