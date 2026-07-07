import type { OverlayPayload } from "./DataOverlay";
import {
  DEMO_FULFILLMENT_GAUGE,
  DEMO_LOW_STOCK,
  DEMO_ORDERS_WEEK,
  DEMO_PENDING_ORDERS,
} from "./demoPayloads";

/**
 * ============================================================================
 * OWNER QUERY PIPELINE — stub for real backend
 * ============================================================================
 *
 * PRODUCTION FLOW (to be wired later — do not touch the UI to do this):
 *
 *   1. Voice stream → STT → transcript string
 *   2. handleOwnerQuery(transcript) receives the transcript
 *   3. Intent classifier picks one of:
 *        - inventory_status     → structured DB query, return `chart` overlay
 *        - pending_orders       → structured DB query, return `table` overlay
 *        - customer_waiting     → structured DB query, return `table` overlay
 *        - order_detail         → structured DB query, return `table` overlay
 *        - catalog_lookup       → RAG over product docs, `null` overlay
 *        - conversational       → LLM, `null` overlay
 *   4. Backend responds with { spokenAnswer, overlay } — this exact shape
 *   5. Frontend types the caption + (optionally) opens the visual readout
 *
 * The stub below simulates that round-trip with mock latency + keyword
 * matching so the UI is fully exercisable today. Swap the body of
 * `handleOwnerQuery` for a fetch() call when the backend lands. The
 * component tree does not need to change.
 * ============================================================================
 */

export interface OwnerQueryResponse {
  spokenAnswer: string;
  overlay: OverlayPayload | null;
}

const SUGGESTED_QUERIES = [
  "What's running low in stock?",
  "Which orders are waiting on approval?",
  "How is our fulfillment rate this week?",
  "Show me orders over the last week.",
];

export function getSuggestedQueries() {
  return SUGGESTED_QUERIES;
}

export async function handleOwnerQuery(transcript: string): Promise<OwnerQueryResponse> {
  // Simulate backend latency
  await new Promise((r) => setTimeout(r, 1400));

  const t = transcript.toLowerCase();

  if (/(low|stock|inventory|running out)/.test(t)) {
    return {
      spokenAnswer:
        "You have six products under threshold. KP-001 and KP-014 are critical — three and seven units left respectively. I would recommend reordering those tonight.",
      overlay: DEMO_LOW_STOCK,
    };
  }

  if (/(pending|approval|awaiting|waiting.*order)/.test(t)) {
    return {
      spokenAnswer:
        "Five orders are awaiting your approval. Two have aged past 48 hours, totalling five thousand one hundred dollars. Order 8842 for M. Okafor is the oldest.",
      overlay: DEMO_PENDING_ORDERS,
    };
  }

  if (/(fulfill|ship|on time|performance)/.test(t)) {
    return {
      spokenAnswer:
        "Fulfillment sits at eighty-seven percent for the last seven days, up two points from the previous week. Comfortably above your ninety-day baseline.",
      overlay: DEMO_FULFILLMENT_GAUGE,
    };
  }

  if (/(order|volume|week|trend|last 7|last seven)/.test(t)) {
    return {
      spokenAnswer:
        "Order volume peaked Friday at fifty-five orders. Weekly total is two hundred sixty-five, a twelve percent lift over last week.",
      overlay: DEMO_ORDERS_WEEK,
    };
  }

  if (/(customer|reply|response|waiting)/.test(t)) {
    return {
      spokenAnswer:
        "Three customers are still waiting on a reply. I've queued draft responses in your inbox — say the word and I'll send them.",
      overlay: null,
    };
  }

  return {
    spokenAnswer:
      "I heard you, but I'm not certain which record set to pull. Try asking about inventory, pending orders, or fulfillment rate.",
    overlay: null,
  };
}
