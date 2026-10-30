import type { SelectionPayload } from "@/features/bulk-downloads/api/bulk-downloads-api";

/**
 * What the administrator has ticked, across every page of the list.
 *
 * "some": exactly these ids. "all": everything matching the current search and status, except the ones unticked
 * afterwards -- so "select all 2,000" never has to load or send 2,000 ids. Changing the search or status while in
 * "all" mode starts over, because "all" always means "all matching what is on screen".
 */
export type Selection = { mode: "some"; ids: ReadonlySet<string> } | { mode: "all"; excluded: ReadonlySet<string> };

export const emptySelection = (): Selection => ({ mode: "some", ids: new Set() });

export function isSelected(selection: Selection, id: string): boolean {
  return selection.mode === "some" ? selection.ids.has(id) : !selection.excluded.has(id);
}

export function toggle(selection: Selection, id: string): Selection {
  if (selection.mode === "some") {
    const ids = new Set(selection.ids);
    if (ids.has(id)) ids.delete(id);
    else ids.add(id);
    return { mode: "some", ids };
  }
  const excluded = new Set(selection.excluded);
  if (excluded.has(id)) excluded.delete(id);
  else excluded.add(id);
  return { mode: "all", excluded };
}

/** Tick or untick every id on the current page, keeping what was chosen on other pages. */
export function setPage(selection: Selection, pageIds: string[], on: boolean): Selection {
  if (selection.mode === "some") {
    const ids = new Set(selection.ids);
    pageIds.forEach((id) => (on ? ids.add(id) : ids.delete(id)));
    return { mode: "some", ids };
  }
  const excluded = new Set(selection.excluded);
  pageIds.forEach((id) => (on ? excluded.delete(id) : excluded.add(id)));
  return { mode: "all", excluded };
}

export const selectAllMatching = (): Selection => ({ mode: "all", excluded: new Set() });

export function count(selection: Selection, total: number): number {
  return selection.mode === "some" ? selection.ids.size : Math.max(0, total - selection.excluded.size);
}

export function pageState(selection: Selection, pageIds: string[]): "all" | "some" | "none" {
  const on = pageIds.filter((id) => isSelected(selection, id)).length;
  if (on === 0) return "none";
  return on === pageIds.length ? "all" : "some";
}

export function toPayload(selection: Selection, filters: { search?: string; status?: string }): SelectionPayload {
  if (selection.mode === "some") return { mode: "selected", ids: [...selection.ids] };
  return {
    mode: "filtered",
    search: filters.search || undefined,
    status: filters.status || undefined,
    exclude_ids: [...selection.excluded],
  };
}
