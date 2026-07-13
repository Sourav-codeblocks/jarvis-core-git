import { createFileRoute } from "@tanstack/react-router";
import { Hud } from "@/components/hud/Hud";

export const Route = createFileRoute("/")({
  component: Index,
});

function Index() {
  return <Hud />;
}
