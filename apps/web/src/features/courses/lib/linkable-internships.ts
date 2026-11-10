import { useQuery } from "@tanstack/react-query";

import { type OurInternship, ourInternshipsApi, ourInternshipsKeys } from "@/features/our-internships/api/our-internships-api";

/** The internships a course can be linked to: this organization's, except closed ones. */
export function useLinkableInternships() {
  const query = useQuery({ queryKey: ourInternshipsKeys.list(), queryFn: () => ourInternshipsApi.list() });
  return { ...query, internships: (query.data ?? []).filter((i) => i.status !== "closed") };
}

/** An internship as the picker lists it, saying which course it uses now. */
export function internshipLabel(i: OurInternship): string {
  return i.lms_course_title ? `${i.title} (uses "${i.lms_course_title}")` : i.title;
}
