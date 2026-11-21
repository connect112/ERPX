import { createContext, useContext } from "react";

/**
 * Whether the signed-in person may edit the curriculum shown. Editing needs the course permission; an internship instructor can read the
 * linked course's curriculum but never edits it merely because they manage the internship's activities. The server enforces this on every
 * request; the panels use it only to hide controls that would be refused.
 */
export const CurriculumAccessContext = createContext<{ canManage: boolean }>({ canManage: true });

export function useCurriculumAccess() {
  return useContext(CurriculumAccessContext);
}
