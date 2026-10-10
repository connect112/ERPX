import type { SeriesPoint } from "@/features/social-media/api/social-media-api";
import { NOT_AVAILABLE, formatDay, formatNumber } from "@/features/social-media/lib/numbers";

/**
 * One bar per day. A day with no figure is drawn as a short dashed mark (and says so on hover), never as an empty bar that
 * would read as zero.
 */
export function DayBars({ series, label }: { series: SeriesPoint[]; label: string }) {
  const present = series.filter((p) => p.value !== null) as { day: string; value: number }[];
  const max = Math.max(1, ...present.map((p) => p.value));
  const width = 100 / Math.max(series.length, 1);
  const summary = present.length
    ? `${label}: ${present.length} of ${series.length} days have a figure, from ${formatNumber(Math.min(...present.map((p) => p.value)))} to ${formatNumber(max)}.`
    : `${label}: no figures for these days.`;
  return (
    <svg role="img" aria-label={summary} viewBox="0 0 100 40" preserveAspectRatio="none" className="h-24 w-full">
      <title>{summary}</title>
      <line x1="0" y1="38" x2="100" y2="38" stroke="currentColor" strokeOpacity="0.2" strokeWidth="0.3" />
      {series.map((p, i) =>
        p.value === null ? (
          <g key={p.day}>
            <title>{`${formatDay(p.day)}: ${NOT_AVAILABLE}`}</title>
            <line x1={i * width + width / 2} y1="36" x2={i * width + width / 2} y2="38" stroke="currentColor" strokeOpacity="0.4" strokeWidth="0.6" strokeDasharray="0.6 0.6" />
          </g>
        ) : (
          <rect key={p.day} x={i * width + width * 0.15} y={38 - (p.value / max) * 36} width={width * 0.7} height={Math.max((p.value / max) * 36, 0.4)} className="fill-primary">
            <title>{`${formatDay(p.day)}: ${formatNumber(p.value)}`}</title>
          </rect>
        ),
      )}
    </svg>
  );
}
