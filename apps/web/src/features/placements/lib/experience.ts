export const EXPERIENCE_FILTERS = [
  { value: "0-3", label: "0-3 years" },
  { value: "1-5", label: "1-5 years" },
  { value: "3-7", label: "3-7 years" },
  { value: "7+", label: "7+ years" },
  { value: "unknown", label: "Not stated" },
] as const;

/** "3-5 yrs", "5+ yrs", "2 yrs", or "Not stated"; a leading ~ marks a guess made from the title (Senior, Junior...). */
export function experienceLabel(job: {
  experience_min: number | null;
  experience_max: number | null;
  experience_estimated: boolean;
}): string {
  const { experience_min: low, experience_max: high, experience_estimated: guess } = job;
  if (low === null) return "Not stated";
  const text =
    high === null ? (low === 0 ? "Fresher" : `${low}+ yrs`) : low === high ? `${low} yrs` : `${low}-${high} yrs`;
  return guess ? `~${text}` : text;
}
