// Single source of truth for all user-facing text/branding.
// A tenant can rebrand the entire HUD by editing this one file.

export const config = {
  assistantName: "JARVIS",
  tagline: "Founder's Command Interface",
  status: {
    standby: "STANDBY",
    listening: "LISTENING",
    call: "CALL ACTIVE",
    thinking: "PROCESSING",
    typing: "TEXT INPUT",
  },
  hints: {
    micIdle: "Tap ring to speak",
    micActive: "Listening…",
    callIdle: "Initiate secure call",
    callActive: "Call in progress",
    typeMode: "Type your directive",
    esc: "ESC to close",
  },
  labels: {
    telemetry: "TELEMETRY",
    uplink: "UPLINK",
    coreTemp: "CORE",
    signal: "SIGNAL",
    latency: "LATENCY",
    devSimulate: "DEV: simulate voice-trigger",
  },
  greeting: "Good evening. All systems nominal.",
} as const;

export type Config = typeof config;
