/** A figure Instagram didn't give is shown as this, never as 0. */
export const NOT_AVAILABLE = "Not available";

export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return NOT_AVAILABLE;
  if (Math.abs(value) >= 100) return Math.round(value).toLocaleString("en-IN");
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

/** A rate (0.0123) as a percentage with enough digits to be honest about small numbers. */
export function formatRate(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return NOT_AVAILABLE;
  const percent = value * 100;
  return `${percent >= 10 ? percent.toFixed(0) : percent.toFixed(1)}%`;
}

export function formatChange(value: number | null | undefined): string | null {
  if (value === null || value === undefined || Number.isNaN(value)) return null;
  const percent = Math.round(Math.abs(value) * 100);
  if (percent === 0) return "about the same as before";
  return `${percent}% ${value > 0 ? "higher" : "lower"} than before`;
}

export function signed(value: number | null | undefined): string {
  if (value === null || value === undefined) return NOT_AVAILABLE;
  return `${value > 0 ? "+" : ""}${Math.round(value).toLocaleString("en-IN")}`;
}

export const KIND_LABEL: Record<string, string> = { observed: "Observed", calculated: "Calculated" };

export const GROUP_LABEL: Record<string, string> = {
  kind: "Format",
  pillar: "Topic",
  hook: "Hook style",
  cta: "Call to action",
  time_of_day: "Time of day",
};

export function formatDay(day: string): string {
  return new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short" }).format(new Date(`${day}T00:00:00`));
}
