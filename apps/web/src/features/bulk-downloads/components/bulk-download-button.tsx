import { FolderDown } from "lucide-react";
import { useState } from "react";

import { Button, type ButtonProps } from "@/components/ui/button";
import type { BulkSource } from "@/features/bulk-downloads/api/bulk-downloads-api";
import { BulkDownloadDialog } from "@/features/bulk-downloads/components/bulk-download-dialog";

interface Props {
  source: BulkSource;
  scopeId: string | null;
  label?: string;
  size?: ButtonProps["size"];
  variant?: ButtonProps["variant"];
}

/** Drop-in "Bulk download" button for any page that shows documents a module produces. */
export function BulkDownloadButton({ source, scopeId, label = "Bulk download", size, variant = "outline" }: Props) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button size={size} variant={variant} onClick={() => setOpen(true)}>
        <FolderDown className="h-4 w-4" />
        {label}
      </Button>
      {open && <BulkDownloadDialog open={open} onOpenChange={setOpen} source={source} scopeId={scopeId} />}
    </>
  );
}
