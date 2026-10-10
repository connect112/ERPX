/**
 * Addresses that come from outside (Instagram, a news feed, a person typing one) become links only if they are plain https
 * addresses. A `javascript:` or `data:` address, or one with a password in it, gives no link at all.
 */
export function safeHref(value: string | null | undefined): string | undefined {
  if (!value || value.length > 1000 || /\s/.test(value)) return undefined;
  try {
    const url = new URL(value);
    if (url.protocol !== "https:" || url.username || url.password || !url.hostname.includes(".")) return undefined;
    return value;
  } catch {
    return undefined;
  }
}
