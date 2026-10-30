import type { FileFilters, FileItem } from "@/features/storage-manager/api/storage-api";

/**
 * The rules the screens follow. The server enforces every one of them again; these only decide what the page offers.
 */

/** Only a platform superuser may delete, and only a file nothing uses that is not protected. */
export function isDeletable(item: FileItem, canDelete: boolean): boolean {
  return canDelete && item.status === "orphan" && !item.protected && item.backend === "object_storage";
}

export interface DeleteForm {
  blockedCount: number;
  reason: string;
  typed: string;
  confirmText: string;
}

/** The delete button is live only when nothing is blocked, a reason is written, and the confirmation is exact. */
export function isDeleteReady({ blockedCount, reason, typed, confirmText }: DeleteForm): boolean {
  return blockedCount === 0 && reason.trim().length >= 3 && typed.trim() === confirmText;
}

export function purgeConfirmText(count: number): string {
  return `PURGE ${count}`;
}

export function nextSort(filters: Pick<FileFilters, "sort" | "order">, key: string): Pick<FileFilters, "sort" | "order"> {
  if (filters.sort === key) return { sort: key, order: filters.order === "asc" ? "desc" : "asc" };
  return { sort: key, order: "asc" };
}

export function hasActiveFilters(filters: FileFilters): boolean {
  return Boolean(filters.q || filters.status || filters.type_group || filters.large || filters.min_size || filters.owner);
}

export function totalBytes(items: Iterable<FileItem>): number {
  let sum = 0;
  for (const item of items) sum += item.size_bytes;
  return sum;
}
