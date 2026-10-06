import { useAuthStore } from "@/store/auth-store";

/**
 * A hackathon participant: holds the participant marker permission and none
 * of the course permissions a regular student has. Such an account only ever
 * sees Hackathons / Leaderboard / Achievements (see layouts/app-layout.tsx).
 * Driven by the server's permission grant, never a hardcoded role name.
 */
export function useIsParticipantOnly(): boolean {
  const permissions = useAuthStore((s) => s.permissions);
  return permissions.includes("hackathons.participate") && !permissions.includes("courses.view");
}

/** Where a participant may go; everything else sends them back to Hackathons. */
export const PARTICIPANT_PATH_PREFIXES = ["/hackathons", "/hackathon-leaderboard", "/hackathon-achievements"];
