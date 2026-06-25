import { useCallback, useEffect, useRef, useState } from "react";
import { sendChatMessage } from "../services/aiChatService";
import type { AiChatMessage } from "../types/aiChat";

const SESSION_STORAGE_KEY = "aiChatSessionId";

function readToken(): string | null {
  return localStorage.getItem("accessToken");
}

function readStoredSessionId(): string | null {
  return sessionStorage.getItem(SESSION_STORAGE_KEY);
}

function storeSessionId(id: string): void {
  sessionStorage.setItem(SESSION_STORAGE_KEY, id);
}

function clearStoredSessionId(): void {
  sessionStorage.removeItem(SESSION_STORAGE_KEY);
}

function nowIso(): string {
  return new Date().toISOString();
}

export interface UseAiChatResult {
  messages: AiChatMessage[];
  sending: boolean;
  error: string | null;
  sessionId: string | null;
  send: (text: string) => Promise<void>;
  reset: () => void;
}

export function useAiChat(): UseAiChatResult {
  const sessionRef = useRef<string | null>(readStoredSessionId());
  const [messages, setMessages] = useState<AiChatMessage[]>([]);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Best-effort welcome line; replaced when first response arrives.
    setMessages([
      {
        id: `welcome-${Date.now()}`,
        role: "assistant",
        body: "Hi! I can help with returns, shipping, payment, sizing, and product care. What would you like to know?",
        createdAt: nowIso(),
      },
    ]);
  }, []);

  const send = useCallback(async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || sending) {
      return;
    }
    setError(null);
    const userMessage: AiChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      body: trimmed,
      createdAt: nowIso(),
    };
    setMessages((prev) => [...prev, userMessage]);
    setSending(true);
    try {
      const response = await sendChatMessage({
        sessionId: sessionRef.current,
        message: trimmed,
        token: readToken(),
        clientContext: {
          page: window.location.pathname,
          locale: navigator.language,
        },
      });
      if (response.sessionId && response.sessionId !== sessionRef.current) {
        sessionRef.current = response.sessionId;
        storeSessionId(response.sessionId);
      }
      const assistantMessage: AiChatMessage = {
        id: `assistant-${response.traceId ?? Date.now()}`,
        role: "assistant",
        body: response.answer || "I do not have an answer right now.",
        responseType: response.responseType,
        productCards: response.productCards ?? [],
        citations: response.citations ?? [],
        draftAction: response.draftAction ?? null,
        needsConfirmation: response.needsConfirmation,
        createdAt: nowIso(),
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Chat is temporarily unavailable.";
      setError(message);
      setMessages((prev) => [
        ...prev,
        {
          id: `error-${Date.now()}`,
          role: "assistant",
          body: "Sorry, I could not send that message. Please try again.",
          responseType: "tool_error",
          createdAt: nowIso(),
        },
      ]);
    } finally {
      setSending(false);
    }
  }, [sending]);

  const reset = useCallback(() => {
    clearStoredSessionId();
    sessionRef.current = null;
    setMessages([]);
    setError(null);
  }, []);

  return {
    messages,
    sending,
    error,
    sessionId: sessionRef.current,
    send,
    reset,
  };
}
