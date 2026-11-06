/** How the staff viewer shows an uploaded document. Only these types are rendered in the page; anything else is a download. */
export type ViewerKind = "pdf" | "image" | "download";

export function viewerKind(contentType: string | null | undefined, viewable = true): ViewerKind {
  if (!viewable) return "download";
  const type = (contentType ?? "").toLowerCase().split(";")[0].trim();
  if (type === "application/pdf") return "pdf";
  if (type === "image/jpeg" || type === "image/png") return "image";
  return "download";
}

/** The type the temporary object URL is created with: the document's own, limited to what the viewer renders. */
export function blobType(kind: ViewerKind, contentType: string): string {
  if (kind === "pdf") return "application/pdf";
  if (kind === "image") return contentType.toLowerCase().includes("png") ? "image/png" : "image/jpeg";
  return "application/octet-stream";
}
