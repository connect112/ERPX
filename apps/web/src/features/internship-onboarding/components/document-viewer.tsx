import { Download, Loader2 } from "lucide-react";
import { type ReactNode, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { errorMessage } from "@/features/institutions/lib/format";
import { onboardingFlowApi } from "@/features/internship-onboarding/api";
import { blobType, viewerKind } from "@/features/internship-onboarding/lib/documents";

export interface ViewerDocument {
  id: string;
  key: string;
  version: number;
  filename: string;
  content_type: string;
  viewable: boolean;
}

interface Props {
  internshipId: string;
  document: ViewerDocument;
  onClose: () => void;
  /** Downloads the file (a short-lived signed link), separately from viewing it. */
  onDownload: (id: string) => void;
  /** The review controls for this document, so a reviewer can verify or send it back without leaving the viewer. */
  children?: ReactNode;
}

/**
 * Shows an uploaded document inside ERPX: a PDF in the browser's own viewer (with its page controls), a JPG or PNG as an image. The
 * file is fetched with the reviewer's own login, shown from a temporary object URL, and that URL is revoked as soon as the viewer
 * closes (or another document replaces it). Other types, and anything that cannot be shown, are offered as a download.
 */
export function DocumentViewer({ internshipId, document: doc, onClose, onDownload, children }: Props) {
  const kind = viewerKind(doc.content_type, doc.viewable);
  const [url, setUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (kind === "download") return;
    let cancelled = false;
    let made: string | null = null;
    setUrl(null);
    setError(null);
    onboardingFlowApi
      .documentFile(internshipId, doc.id)
      .then((data) => {
        if (cancelled) return;
        made = URL.createObjectURL(new Blob([data], { type: blobType(kind, doc.content_type) }));
        setUrl(made);
      })
      .catch((e: unknown) => !cancelled && setError(errorMessage(e, "The document could not be opened. You can still download it.")));
    return () => {
      cancelled = true;
      if (made) URL.revokeObjectURL(made);
    };
  }, [internshipId, doc.id, doc.content_type, kind]);

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-5xl">
        <DialogHeader>
          <DialogTitle>
            {doc.key} · version {doc.version}
          </DialogTitle>
          <DialogDescription>{doc.filename}</DialogDescription>
        </DialogHeader>

        <div className="min-h-[50vh] rounded-md border bg-muted/30">
          {kind === "download" ? (
            <p className="p-6 text-sm text-muted-foreground">This type of file cannot be shown here. Use Download to open it on your computer.</p>
          ) : error ? (
            <p className="p-6 text-sm text-destructive" role="alert">
              {error}
            </p>
          ) : !url ? (
            <p className="flex items-center gap-2 p-6 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" /> Opening the document…
            </p>
          ) : kind === "pdf" ? (
            <iframe title={`${doc.key} version ${doc.version}`} src={`${url}#toolbar=1&navpanes=0`} className="h-[65vh] w-full rounded-md" />
          ) : (
            <div className="flex max-h-[65vh] justify-center overflow-auto p-2">
              <img src={url} alt={`${doc.key} version ${doc.version}`} className="max-h-[62vh] max-w-full object-contain" />
            </div>
          )}
        </div>

        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0 flex-1 space-y-2">{children}</div>
          <Button variant="outline" size="sm" onClick={() => onDownload(doc.id)}>
            <Download className="h-4 w-4" />
            Download
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
