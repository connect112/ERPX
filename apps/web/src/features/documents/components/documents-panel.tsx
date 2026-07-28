import { Download, Paperclip, Trash2, Upload } from "lucide-react";
import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  useDeleteDocument,
  useDocumentsList,
  useDownloadDocument,
  useUploadDocument,
} from "@/features/documents/api/documents-hooks";

function formatBytes(bytes: number | null): string {
  if (bytes === null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

interface DocumentsPanelProps {
  entityType: string;
  entityId: string;
}

export function DocumentsPanel({ entityType, entityId }: DocumentsPanelProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);

  const { data: documents, isLoading } = useDocumentsList(entityType, entityId);
  const upload = useUploadDocument(entityType, entityId);
  const remove = useDeleteDocument(entityType, entityId);
  const download = useDownloadDocument();

  const handleFileSelected = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setError(null);
    upload.mutate(file, {
      onError: () => setError("Upload failed. Please try again."),
    });
  };

  const handleDownload = (documentId: string, filename: string) => {
    download.mutate(documentId, {
      onSuccess: (url) => {
        const link = document.createElement("a");
        link.href = url;
        link.download = filename;
        link.click();
      },
    });
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base">Documents</CardTitle>
        <Button size="sm" onClick={() => fileInputRef.current?.click()} disabled={upload.isPending}>
          <Upload className="h-4 w-4" />
          {upload.isPending ? "Uploading..." : "Upload"}
        </Button>
        <input ref={fileInputRef} type="file" className="hidden" onChange={handleFileSelected} />
      </CardHeader>
      <CardContent>
        {error && <p className="pb-3 text-sm text-destructive">{error}</p>}

        {isLoading && <Skeleton className="h-24 w-full" />}

        {!isLoading && (documents?.length ?? 0) === 0 && (
          <p className="flex flex-col items-center gap-2 py-8 text-center text-sm text-muted-foreground">
            <Paperclip className="h-8 w-8 text-muted-foreground/50" />
            No documents attached yet.
          </p>
        )}

        {!isLoading && (documents?.length ?? 0) > 0 && (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>File</TableHead>
                <TableHead>Size</TableHead>
                <TableHead>Uploaded</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {documents?.map((doc) => (
                <TableRow key={doc.id}>
                  <TableCell className="font-medium">{doc.filename}</TableCell>
                  <TableCell className="text-muted-foreground">{formatBytes(doc.size_bytes)}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {new Date(doc.created_at).toLocaleDateString()}
                  </TableCell>
                  <TableCell className="flex justify-end gap-1">
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleDownload(doc.id, doc.filename)}
                      aria-label={`Download ${doc.filename}`}
                    >
                      <Download className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => remove.mutate(doc.id)}
                      aria-label={`Delete ${doc.filename}`}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
