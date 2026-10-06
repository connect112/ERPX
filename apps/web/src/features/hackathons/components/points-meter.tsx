/**
 * "allocated / total" with a bar: how much of a task's marks has been given out.
 * Green when every mark is accounted for, blue while there is still room, red if over.
 */
export function PointsMeter({
  label,
  value,
  total,
  hint,
}: {
  label: string;
  value: number;
  total: number;
  hint?: string;
}) {
  const over = value > total;
  const complete = total > 0 && value === total;
  const percent = total > 0 ? Math.min(100, Math.round((value / total) * 100)) : 0;
  const color = over ? "bg-destructive" : complete ? "bg-emerald-500" : "bg-primary";
  return (
    <div className="space-y-1">
      <div className="flex items-baseline justify-between gap-2 text-sm">
        <span className="font-medium">{label}</span>
        <span className={`tabular-nums font-semibold ${over ? "text-destructive" : ""}`}>
          {value} / {total}
        </span>
      </div>
      <div
        className="h-2 overflow-hidden rounded-full bg-muted"
        role="progressbar"
        aria-label={label}
        aria-valuenow={value}
        aria-valuemin={0}
        aria-valuemax={total}
      >
        <div className={`h-full rounded-full transition-all ${color}`} style={{ width: `${percent}%` }} />
      </div>
      <p className={`text-xs ${over ? "text-destructive" : "text-muted-foreground"}`}>
        {hint ??
          (over
            ? `${value - total} over the task's marks`
            : complete
              ? "All marks accounted for"
              : total === 0
                ? "Set the task's marks first"
                : `${total - value} still to allocate`)}
      </p>
    </div>
  );
}
