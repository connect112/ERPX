// Serves the production build (dist/) the way the production nginx image does, for the browser tests:
//  - nginx 1.27's default MIME table (it has no entry for .mjs, so such a file is application/octet-stream),
//  - X-Content-Type-Options: nosniff (so a wrongly typed script or worker is refused, exactly as in production),
//  - single-page-app fallback to index.html.
// Usage: node e2e/serve-dist.mjs [port]   (run `npm run build` first)
import { createReadStream, existsSync, statSync } from "node:fs";
import { createServer } from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../dist");
const port = Number(process.argv[2] ?? 4173);

const NGINX_MIME = {
  ".html": "text/html",
  ".css": "text/css",
  ".js": "application/javascript",
  ".json": "application/json",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".gif": "image/gif",
  ".ico": "image/x-icon",
  ".webp": "image/webp",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
  ".txt": "text/plain",
  ".pdf": "application/pdf",
  ".wasm": "application/wasm",
  ".map": "application/octet-stream",
};

createServer((req, res) => {
  const url = new URL(req.url ?? "/", "http://localhost");
  let file = path.join(root, decodeURIComponent(url.pathname));
  if (!file.startsWith(root)) return res.writeHead(403).end();
  if (!existsSync(file) || statSync(file).isDirectory()) file = path.join(root, "index.html");
  const type = NGINX_MIME[path.extname(file).toLowerCase()] ?? "application/octet-stream";
  res.writeHead(200, { "Content-Type": type, "X-Content-Type-Options": "nosniff", "Cache-Control": "no-cache" });
  createReadStream(file).pipe(res);
}).listen(port, "127.0.0.1", () => console.log(`serving ${root} on http://127.0.0.1:${port}`));
