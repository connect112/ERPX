/**
 * After a deploy the page files get new names. A tab that was opened before the deploy still asks for the old names
 * the next time it loads a page, and fails with "error loading dynamically imported module". When that happens,
 * load the site again once (which fetches the new files). Guarded so a real outage can't cause a reload loop.
 */
const STORAGE_KEY = "erpx-stale-chunk-reload-at";
const GUARD_MS = 30_000;

export function shouldReload(storage: Pick<Storage, "getItem">, now: number): boolean {
  try {
    const at = Number(storage.getItem(STORAGE_KEY));
    return !(Number.isFinite(at) && at > 0 && now - at < GUARD_MS);
  } catch {
    return true;
  }
}

export function reloadOnStaleChunk(): void {
  window.addEventListener("vite:preloadError", (event) => {
    if (!shouldReload(window.sessionStorage, Date.now())) return;
    event.preventDefault();
    try {
      window.sessionStorage.setItem(STORAGE_KEY, String(Date.now()));
    } catch {
      // no storage: reload anyway, once per event
    }
    window.location.reload();
  });
}
