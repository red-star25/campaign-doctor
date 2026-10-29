import { cn } from "@/lib/cn";
import type { ScenarioSummary } from "@/lib/types";

export function IncidentPicker({
  scenarios,
  selectedId,
  onSelect,
}: {
  scenarios: ScenarioSummary[];
  selectedId: string | null;
  onSelect: (scenarioId: string) => void;
}) {
  if (scenarios.length === 0) {
    return <p className="text-sm text-ink">No incidents are registered.</p>;
  }

  return (
    <div aria-label="Incidents" className="mb-4 flex flex-wrap gap-2">
      {scenarios.map((scenario) => {
        const selected = scenario.scenario_id === selectedId;
        return (
          <button
            key={scenario.scenario_id}
            type="button"
            aria-pressed={selected}
            onClick={() => onSelect(scenario.scenario_id)}
            className={cn(
              "rounded-full border px-3 py-1 text-sm",
              selected ? "border-pine bg-pine-soft text-ink" : "border-line bg-raised text-ink hover:border-line-strong",
            )}
          >
            {scenario.name}
          </button>
        );
      })}
    </div>
  );
}
