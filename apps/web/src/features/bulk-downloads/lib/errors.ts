/** The server's own message (ERPX errors are `{ error: { message } }`), or a fallback. */
export function errorText(error: unknown, fallback: string): string {
  const message = (error as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error?.message;
  return message ?? fallback;
}
