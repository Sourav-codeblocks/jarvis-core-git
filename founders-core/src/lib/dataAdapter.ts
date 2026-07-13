// Single seam for all founder-facing data. fetchJarvisResponse() now talks
// to the real Jarvis Core Gateway over WebSocket (see founder_ws.py) instead
// of faking a delay. The response shape is unchanged, so every consumer
// (Hud.tsx, Overlay.tsx, ReportsBanner.tsx) keeps working untouched.
//
// Reports listed in FOUNDER_REPORTS are the static shortcut tiles in
// ReportsBanner — kept as local fixtures for now. Long-term these should be
// discovered from the same founder tool registry the gateway exposes.

export type OverlayKind = "chart" | "gauge" | "table" | "report" | null;

export interface OverlayPayload {
  kind: OverlayKind;
  title: string;
  chart?: { label: string; value: number }[];
  gauges?: { label: string; value: number; max: number; unit?: string }[];
  table?: {
    columns: string[];
    rows: { status: "pending" | "urgent" | "resolved"; cells: string[] }[];
  };
  report?: string[];
}

export interface JarvisResponse {
  spokenAnswer: string;
  overlay: OverlayPayload | null;
}

export interface FounderReport {
  id: string;
  label: string;
  hint: string;
  spokenAnswer: string;
  overlay: OverlayPayload;
}

/**
 * Curated report catalog a founder would want at a glance.
 * Extend this list (or replace with a remote registry) as new tools ship.
 */
export const FOUNDER_REPORTS: FounderReport[] = [
  {
    id: "revenue",
    label: "Revenue",
    hint: "7-day trend",
    spokenAnswer:
      "Revenue is trending up eighteen percent week over week. Two accounts require your attention.",
    overlay: {
      kind: "chart",
      title: "Revenue · Last 7 Days",
      chart: [
        { label: "MON", value: 42 },
        { label: "TUE", value: 51 },
        { label: "WED", value: 47 },
        { label: "THU", value: 63 },
        { label: "FRI", value: 71 },
        { label: "SAT", value: 68 },
        { label: "SUN", value: 84 },
      ],
    },
  },
  {
    id: "runway",
    label: "Runway",
    hint: "Burn & health",
    spokenAnswer: "Runway is healthy. Burn within tolerance across all subsystems.",
    overlay: {
      kind: "gauge",
      title: "Runway & Burn",
      gauges: [
        { label: "RUNWAY", value: 74, max: 100, unit: "%" },
        { label: "BURN", value: 42, max: 100, unit: "%" },
        { label: "MARGIN", value: 61, max: 100, unit: "%" },
        { label: "CASH", value: 88, max: 100, unit: "%" },
      ],
    },
  },
  {
    id: "pipeline",
    label: "Pipeline",
    hint: "Deals & actions",
    spokenAnswer: "Displaying open pipeline. Two deals flagged urgent.",
    overlay: {
      kind: "table",
      title: "Sales Pipeline",
      table: {
        columns: ["ID", "Account", "Owner", "Status"],
        rows: [
          { status: "urgent", cells: ["DL-412", "Northwind Corp", "Sales", "URGENT"] },
          { status: "urgent", cells: ["DL-408", "Stark Industries", "Sales", "URGENT"] },
          { status: "pending", cells: ["DL-402", "Wayne Ent.", "Sales", "PENDING"] },
          { status: "pending", cells: ["DL-397", "Acme Robotics", "Sales", "PENDING"] },
          { status: "resolved", cells: ["DL-388", "Initech LLC", "Sales", "CLOSED"] },
        ],
      },
    },
  },
  {
    id: "briefing",
    label: "Briefing",
    hint: "Morning digest",
    spokenAnswer: "Compiled briefing ready. Highlights on screen.",
    overlay: {
      kind: "report",
      title: "Morning Briefing",
      report: [
        "// 06:00 — Uplink stable across all regions.",
        "// 06:14 — Overnight batch jobs completed without incident.",
        "// 07:02 — Two new leads inbound from EMEA channel.",
        "// 07:41 — Reminder: board sync at 15:00 local.",
        "// 08:00 — Recommend reviewing DL-412 before standup.",
      ],
    },
  },
];

export function getReportById(id: string): FounderReport | undefined {
  return FOUNDER_REPORTS.find((r) => r.id === id);
}

// --- Real gateway bridge ----------------------------------------------------
// Phase 0: keshri-pipes is the only tenant, so the slug is hardcoded here —
// same seam as tenant_slug in main.py's Telegram webhook. Swap for a runtime
// tenant/session value once the founder login flow exists.

const GATEWAY_URL = import.meta.env.VITE_GATEWAY_URL ?? "http://localhost:8000";
const GATEWAY_WS_URL = `${GATEWAY_URL.replace(/^http/, "ws")}/ws/founder/keshri-pipes`;
const RESPONSE_TIMEOUT_MS = 8000;

/**
 * Ask JARVIS. Opens one WebSocket per query (Phase 0 bridge — simplest
 * thing that proves the wire works end-to-end). A persistent, reused
 * connection is a natural next step once this carries voice audio too.
 */
export function fetchJarvisResponse(query: string): Promise<JarvisResponse> {
  return new Promise((resolve, reject) => {
    let settled = false;
    const ws = new WebSocket(GATEWAY_WS_URL);

    const timeout = setTimeout(() => {
      if (settled) return;
      settled = true;
      ws.close();
      reject(new Error("Gateway did not respond in time."));
    }, RESPONSE_TIMEOUT_MS);

    ws.onopen = () => {
      ws.send(JSON.stringify({ type: "query", text: query }));
    };

    ws.onmessage = (event) => {
      let msg: any;
      try {
        msg = JSON.parse(event.data);
      } catch {
        return;
      }

      // { type: "status", content: "thinking" } will drive a UI indicator
      // later — ignored for now, we just wait for the final response.
      if (msg.type === "response" && !settled) {
        settled = true;
        clearTimeout(timeout);
        ws.close();
        resolve({ spokenAnswer: msg.spokenAnswer, overlay: msg.overlay ?? null });
      }
    };

    ws.onerror = () => {
      if (settled) return;
      settled = true;
      clearTimeout(timeout);
      reject(new Error("Could not reach the Jarvis Core Gateway."));
    };
  });
}
