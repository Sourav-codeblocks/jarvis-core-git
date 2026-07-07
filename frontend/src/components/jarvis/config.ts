// ============================================================
// JARVIS CONFIG — edit these two lines to rebrand for a business
// ============================================================
export const assistantName = "JARVIS";
export const tagline = "FOUNDER COMMAND INTERFACE";
// ============================================================

export type ThemePreset = {
  id: string;
  label: string;
  // primary accent hex (drives --jv-cyan)
  accent: string;
  // secondary hex, used for gradient tails / --jv-cyan-dim
  accentDim: string;
  // gradient partner (particle tails, nucleus glow)
  accentAlt: string;
  // third blended color for nebula / supernova richness
  accent3: string;
  // hot core color for supernova center
  hot: string;
  // contrast color for call-active state (always visibly different from theme)
  contrast: string;
};

export const THEME_PRESETS: ThemePreset[] = [
  // Cassiopeia — matches supernova remnant reference (pink/teal/lime/violet)
  {
    id: "cassiopeia",
    label: "Cassiopeia",
    accent: "#d15a8f",     // hot pink / magenta filaments
    accentDim: "#4a2a6e",  // deep violet shadow
    accentAlt: "#4fb8d4",  // teal / cyan-blue outer wisps
    accent3: "#a8c94a",    // lime-green pockets
    hot: "#f7d0e0",        // soft pink-white (restrained, not blazing)
    contrast: "#4aa8ff",   // bluish active-state (mic/call)
  },
  // Cygnus Veil — image 1 (violet/pink nebula)
  {
    id: "cygnus",
    label: "Cygnus Veil",
    accent: "#a06fff",     // violet-blue
    accentDim: "#3a1a6e",
    accentAlt: "#ff5faa",  // magenta-pink
    accent3: "#5a8ad4",    // deep blue
    hot: "#ffe8f4",
    contrast: "#ffb347",   // warm gold/amber contrast
  },
  // Crimson Deep — image 2 (maroon/rose)
  {
    id: "crimson",
    label: "Crimson Deep",
    accent: "#c14a5a",     // crimson
    accentDim: "#2a0810",
    accentAlt: "#e88a9a",  // dusty rose
    accent3: "#7a2838",    // deep maroon
    hot: "#ffd8dc",
    contrast: "#5fd4d4",   // cool cyan/teal contrast
  },
];

export const DEFAULT_THEME_ID = "cassiopeia";

export function getPreset(id: string): ThemePreset {
  return THEME_PRESETS.find((t) => t.id === id) ?? THEME_PRESETS[0];
}
