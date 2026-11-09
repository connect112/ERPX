/**
 * Draws a PDF's pages onto canvases inside a host element, with pdf.js (loaded only when a PDF is first shown).
 *
 * Why not an <iframe>: an embedded PDF viewer takes keyboard focus when it loads, and the browser scrolls the whole page to bring it into
 * view; on every preview refresh that moved the page under the person who was editing. Android Chrome cannot show a PDF in an iframe at
 * all. Canvases take no focus, never scroll the page, and behave the same on every device.
 *
 * The new pages replace the old ones in a single step (the old picture stays until the new one is ready), and the host's own scroll
 * position is kept, so a refresh does not flicker or lose your place in the preview.
 */
export interface RenderedPdf {
  pages: number;
  destroy: () => void;
}

type PdfJs = typeof import("pdfjs-dist");
interface Engine {
  lib: PdfJs;
  worker: InstanceType<PdfJs["PDFWorker"]>;
}
let loading: Promise<Engine> | null = null;

/**
 * pdf.js and ONE background worker, created the first time a PDF is shown and kept for the life of the page.
 *
 * The worker is bundled by Vite as an ordinary script (`?worker`), so it is served as `assets/*.js` with a JavaScript type. It must not be
 * loaded by URL as a `.mjs` file: the production nginx serves `.mjs` as application/octet-stream, which a browser refuses for a module
 * worker (and for the fallback that pdf.js tries when the worker fails), so every preview ended in an error.
 */
function engine(): Promise<Engine> {
  loading ??= (async () => {
    const [lib, { default: PdfWorker }] = await Promise.all([import("pdfjs-dist"), import("pdfjs-dist/build/pdf.worker.min.mjs?worker")]);
    return { lib, worker: new lib.PDFWorker({ port: new PdfWorker() as never }) }; // (pdf.js's bundled typings wrongly declare `port` as null only)
  })();
  loading.catch(() => (loading = null)); // a failed start is tried again on the next preview, not remembered
  return loading;
}

export interface RenderOptions {
  /** 100 draws each page as wide as the host; 150 one and a half times that. */
  zoom: number;
  signal?: AbortSignal;
}

export async function renderPdf(blob: Blob, host: HTMLElement, { zoom, signal }: RenderOptions): Promise<RenderedPdf> {
  const { lib, worker } = await engine();
  // the shared worker is passed in, so destroying one document never stops the worker the next preview needs
  const doc = await lib.getDocument({ data: new Uint8Array(await blob.arrayBuffer()), worker }).promise;
  const stop = () => {
    void doc.destroy();
    throw new DOMException("The preview was replaced.", "AbortError");
  };
  try {
    if (signal?.aborted) stop();
    const width = Math.max(200, host.clientWidth - 24) * (zoom / 100);
    const ratio = Math.min(2, globalThis.devicePixelRatio || 1);
    const pages: HTMLCanvasElement[] = [];
    for (let n = 1; n <= doc.numPages; n++) {
      const page = await doc.getPage(n);
      if (signal?.aborted) stop();
      const fit = width / page.getViewport({ scale: 1 }).width;
      const viewport = page.getViewport({ scale: fit * ratio });
      const canvas = document.createElement("canvas");
      canvas.width = Math.floor(viewport.width);
      canvas.height = Math.floor(viewport.height);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${(viewport.height / ratio).toFixed(1)}px`;
      canvas.className = "mx-auto mb-3 block bg-white shadow";
      canvas.setAttribute("role", "img");
      canvas.setAttribute("aria-label", `Page ${n} of ${doc.numPages}`);
      const context = canvas.getContext("2d");
      if (context) await page.render({ canvasContext: context, viewport }).promise;
      if (signal?.aborted) stop();
      pages.push(canvas);
    }
    const [top, left] = [host.scrollTop, host.scrollLeft];
    host.replaceChildren(...pages);
    host.scrollTop = top;
    host.scrollLeft = left;
    return { pages: doc.numPages, destroy: () => void doc.destroy() };
  } catch (error) {
    void doc.destroy();
    throw error;
  }
}
