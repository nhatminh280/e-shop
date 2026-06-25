// Mirrors backend DTO com.eshop.api.chatagent.dto.AgentChatResponse.

export interface AiCitation {
  sourceId: string;
  sourceType: string;
  title: string;
  snippet: string;
  score: number | null;
}

export interface AiProductCard {
  productId: string;
  variantId: string | null;
  name: string;
  slug: string;
  category: string;
  gender: string;
  price: number;
  currency: string;
  imageUrl: string | null;
  colors: string[];
  sizes: string[];
  inStock: boolean;
  stock: number;
  reason: string | null;
  recommendationRank: number | null;
  recommendationScore: number | null;
  recommendationReason: string | null;
}

export interface AiDraftAction {
  draftActionId: string;
  actionType: "cart.add" | "cart.update_quantity" | "cart.remove_item" | "support.handoff";
  payload: Record<string, unknown>;
  status: "pending" | "completed" | "cancelled" | "expired" | "failed";
  expiresAt: string;
  needsConfirmation: boolean;
}

export type AiResponseType =
  | "clarification"
  | "product_results"
  | "recommendations"
  | "order_status"
  | "draft_action"
  | "action_result"
  | "handoff"
  | "fallback"
  | "empty_result"
  | "tool_error"
  | "auth_required"
  | "answer";

export interface AiChatResponse {
  sessionId: string;
  traceId: string;
  intent: string;
  responseType: AiResponseType;
  answer: string;
  productCards: AiProductCard[];
  draftAction: AiDraftAction | null;
  needsConfirmation: boolean;
  citations: AiCitation[];
  intentConfidence: number | null;
  routingConfidence: number | null;
  needsReview: boolean | null;
  latencyMs: number | null;
  fallbackCount: number;
}

export interface AiChatMessage {
  id: string;
  role: "user" | "assistant";
  body: string;
  responseType?: AiResponseType;
  productCards?: AiProductCard[];
  citations?: AiCitation[];
  draftAction?: AiDraftAction | null;
  needsConfirmation?: boolean;
  createdAt: string;
}
