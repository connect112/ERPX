/** The personal onboarding link ends an hour after onboarding is completed. The server decides; the page only reflects it. */
export const EXPIRED_CODE = "onboarding_link_expired";
export const EXPIRED_TITLE = "This onboarding link has expired";

/** The error code of an API failure (the server's standard error envelope), or null. */
export function errorCode(error: unknown): string | null {
  const code = (error as { response?: { data?: { error?: { code?: string } } } })?.response?.data?.error?.code;
  return typeof code === "string" ? code : null;
}

/** Milliseconds until an ISO time (never negative), or null when the time cannot be read or is too far away for a timer. */
export function msUntil(iso: string | null | undefined, now: number = Date.now()): number | null {
  if (!iso) return null;
  const at = Date.parse(iso);
  if (Number.isNaN(at)) return null;
  const ms = Math.max(0, at - now);
  return ms > 2 ** 31 - 1 ? null : ms;
}
