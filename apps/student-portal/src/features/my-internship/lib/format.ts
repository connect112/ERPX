/** The message the API sent back with an error, or a fallback. */
export function errorMessage(error: unknown, fallback: string): string {
  const data = (error as { response?: { data?: { error?: { message?: string; details?: { msg?: string }[] } } } })?.response
    ?.data?.error;
  const detail = Array.isArray(data?.details) ? data?.details[0]?.msg : undefined;
  return (detail ? detail.replace(/^Value error,\s*/, "") : data?.message) ?? fallback;
}

export function formatDateTime(iso: string | null): string {
  if (!iso) return "-";
  return new Date(iso).toLocaleString("en-GB", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

export function formatBytes(bytes: number): string {
  return bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

/** Files above this are refused by the server; checking here saves the student a failed upload. */
export const MAX_FILE_BYTES = 25 * 1024 * 1024;

/** A problem with the chosen files, or null when they can be sent. */
export function checkFiles(files: File[], maxFiles: number): string | null {
  if (files.length > maxFiles) return `You can attach at most ${maxFiles} file${maxFiles === 1 ? "" : "s"}.`;
  const tooBig = files.find((f) => f.size > MAX_FILE_BYTES);
  if (tooBig) return `${tooBig.name} is larger than ${MAX_FILE_BYTES / 1024 / 1024} MB.`;
  const empty = files.find((f) => f.size === 0);
  if (empty) return `${empty.name} is empty.`;
  return null;
}

/** Time left until `iso`, in words ("2 days 3 hours"), or null once it has passed or when there is no deadline. */
export function timeLeft(iso: string | null, now: Date = new Date()): string | null {
  if (!iso) return null;
  const ms = new Date(iso).getTime() - now.getTime();
  if (ms <= 0) return null;
  const minutes = Math.floor(ms / 60_000);
  const days = Math.floor(minutes / 1440);
  const hours = Math.floor((minutes % 1440) / 60);
  const plural = (n: number, unit: string) => `${n} ${unit}${n === 1 ? "" : "s"}`;
  if (days > 0) return hours > 0 ? `${plural(days, "day")} ${plural(hours, "hour")}` : plural(days, "day");
  if (hours > 0) return `${plural(hours, "hour")} ${plural(minutes % 60, "minute")}`;
  return plural(Math.max(1, minutes), "minute");
}

/** Whether a repository link is a full http(s) web address (the server applies the same rule). */
export function isWebAddress(value: string): boolean {
  const v = value.trim();
  if (!v || /\s/.test(v)) return false;
  try {
    const url = new URL(v);
    return (url.protocol === "http:" || url.protocol === "https:") && !!url.hostname;
  } catch {
    return false;
  }
}
