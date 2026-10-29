import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";

import { type CandidateFilters, EMPTY_FILTERS } from "@/features/pentrix-ops/api/candidates-api";

const KEYS = ["q", "assessment", "qualification", "booking", "payment", "marketing", "registered_from", "registered_to", "sort", "order"] as const;

/** The filters live in the address, so a link (from the Overview, or sent to a colleague) opens the list already narrowed. */
export function useUrlFilters(defaults: CandidateFilters = EMPTY_FILTERS) {
  const [params, setParams] = useSearchParams();
  const filters = useMemo<CandidateFilters>(() => {
    const next: CandidateFilters = { ...defaults, page: Math.max(Number(params.get("page")) || 1, 1) };
    for (const key of KEYS) {
      const value = params.get(key);
      if (value) (next as unknown as Record<string, string>)[key] = value;
    }
    return next;
  }, [params, defaults]);

  function update(patch: Partial<CandidateFilters>) {
    const merged: CandidateFilters = { ...filters, ...patch, page: patch.page ?? 1 };
    const next = new URLSearchParams();
    for (const key of KEYS) {
      const value = merged[key];
      if (value && value !== defaults[key]) next.set(key, value);
    }
    if (merged.page > 1) next.set("page", String(merged.page));
    setParams(next, { replace: true });
  }

  return { filters, update, clear: () => setParams(new URLSearchParams(), { replace: true }), active: KEYS.some((k) => params.get(k) && params.get(k) !== defaults[k]) };
}

export const REGISTRATION_SORTS = [["registered", "Registration date"], ["name", "Name"], ["activity", "Latest activity"]];
export const ASSESSMENT_SORTS = [["assessed", "Assessment date"], ["technical", "Technical score"], ["registered", "Registration date"], ["name", "Name"]];
