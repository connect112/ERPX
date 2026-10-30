import { Badge } from "@/components/ui/badge";
import type { FileStatus } from "@/features/storage-manager/api/storage-api";
import { STATUS_LABELS, STATUS_TONES, type Tone } from "@/features/storage-manager/lib/format";

const VARIANT: Record<Tone, "default" | "success" | "warning" | "destructive" | "secondary"> = {
  default: "default",
  success: "success",
  warning: "warning",
  danger: "destructive",
  muted: "secondary",
};

export function StatusBadge({ status }: { status: FileStatus }) {
  return <Badge variant={VARIANT[STATUS_TONES[status]]}>{STATUS_LABELS[status]}</Badge>;
}
