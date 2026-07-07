import { Mic, MicOff, Phone, PhoneOff } from "lucide-react";

// Shared bluish accent for mic + call (matches active core tint)
const BLUE = "#4aa8ff";

export function MicButton({ active, onToggle }: { active: boolean; onToggle: () => void }) {
  return (
    <button
      onClick={onToggle}
      aria-label={active ? "Stop listening" : "Start listening"}
      className="group relative flex h-20 w-20 items-center justify-center rounded-full transition-all duration-300"
      style={{
        background: active
          ? `radial-gradient(circle at 50% 40%, ${BLUE}99, ${BLUE}26 60%, transparent 70%)`
          : `radial-gradient(circle at 50% 40%, ${BLUE}33, ${BLUE}0d 60%, transparent 70%)`,
        border: `1px solid ${BLUE}8c`,
        color: active ? "#001428" : BLUE,
        boxShadow: active
          ? `0 0 24px ${BLUE}, inset 0 0 20px ${BLUE}59`
          : `0 0 12px ${BLUE}59, inset 0 0 10px ${BLUE}26`,
      }}
    >
      {active && (
        <span
          className="absolute inset-0 rounded-full"
          style={{
            border: `1px solid ${BLUE}`,
            animation: "jv-breathe 1.6s ease-in-out infinite",
          }}
        />
      )}
      {active ? <MicOff size={26} /> : <Mic size={26} />}
    </button>
  );
}

export function CallButton({ active, onToggle }: { active: boolean; onToggle: () => void }) {
  return (
    <button
      onClick={onToggle}
      aria-label={active ? "End call" : "Start call"}
      className="group relative flex h-14 w-14 items-center justify-center rounded-full transition-all duration-300"
      style={{
        background: active
          ? `radial-gradient(circle at 50% 40%, ${BLUE}99, ${BLUE}22 60%, transparent 70%)`
          : `radial-gradient(circle at 50% 40%, ${BLUE}33, ${BLUE}0a 60%, transparent 70%)`,
        border: `1px solid ${BLUE}8c`,
        color: active ? "#001428" : BLUE,
        boxShadow: active
          ? `0 0 26px ${BLUE}, inset 0 0 18px ${BLUE}66`
          : `0 0 10px ${BLUE}4d, inset 0 0 8px ${BLUE}26`,
      }}
    >
      {active && (
        <span
          className="absolute inset-0 rounded-full"
          style={{
            border: `1px solid ${BLUE}`,
            animation: "jv-breathe 2.4s ease-in-out infinite",
          }}
        />
      )}
      {active ? <PhoneOff size={20} /> : <Phone size={20} />}
    </button>
  );
}
