import type { FileStatus } from "@/features/storage-manager/api/storage-api";

export function formatBytes(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined) return "—";
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let value = bytes / 1024;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value >= 100 ? value.toFixed(0) : value.toFixed(1)} ${units[unit]}`;
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export const STATUS_LABELS: Record<FileStatus, string> = {
  in_use: "In use",
  pending: "Upload pending",
  orphan: "Unused",
  missing_object: "File missing",
  protected: "Protected",
};

export type Tone = "default" | "success" | "warning" | "danger" | "muted";

export const STATUS_TONES: Record<FileStatus, Tone> = {
  in_use: "success",
  pending: "muted",
  orphan: "warning",
  missing_object: "danger",
  protected: "default",
};

export const VERDICT_LABELS: Record<string, string> = {
  eligible: "Safe to move to Trash",
  in_use: "Still needed",
  protected: "Protected",
  missing: "Nothing to delete",
  not_deletable: "Cannot be deleted",
};

/** Folder paths travel as one string; this is the inverse of joining segments with "/". */
export function pathLabel(path: string[]): string {
  return path.length === 0 ? "All storage" : path.join(" / ");
}

export function percent(part: number, whole: number): number {
  return whole > 0 ? Math.min(100, Math.round((part / whole) * 100)) : 0;
}
