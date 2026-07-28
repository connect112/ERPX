import { ArrowLeft, Pencil } from "lucide-react";
import { type ReactNode, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useChangeWorkshopStatus, useWorkshop } from "@/features/workshops/api/workshops-hooks";
import { RegistrationsPanel } from "@/features/workshops/components/registrations-panel";
import { WorkshopFormDialog } from "@/features/workshops/components/workshop-form-dialog";
import { WorkshopStatusBadge } from "@/features/workshops/components/workshop-status-badge";
import {
  type WorkshopStatus,
  workshopStatusLabels,
  workshopStatusValues,
} from "@/features/workshops/schemas/workshop-schemas";

function DetailRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b py-3 last:border-0">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm font-medium">{value}</span>
    </div>
  );
}

export function WorkshopDetailPage() {
  const { workshopId } = useParams<{ workshopId: string }>();
  const navigate = useNavigate();
  const { data: workshop, isLoading } = useWorkshop(workshopId);
  const changeStatus = useChangeWorkshopStatus(workshopId ?? "");
  const [editOpen, setEditOpen] = useState(false);

  if (isLoading || !workshop) {
    return (
      <div className="space-y-4 p-8">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => navigate("/workshops")}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">{workshop.title}</h1>
            <div className="mt-1 flex items-center gap-2">
              <span className="font-mono text-xs text-muted-foreground">{workshop.code}</span>
              <WorkshopStatusBadge status={workshop.status} />
            </div>
          </div>
        </div>
        <Button variant="outline" onClick={() => setEditOpen(true)}>
          <Pencil className="h-4 w-4" />
          Edit
        </Button>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Workshop details</CardTitle>
            </CardHeader>
            <CardContent>
              <DetailRow label="Date" value={new Date(workshop.workshop_date).toLocaleDateString()} />
              <DetailRow label="Time" value={`${workshop.start_time} – ${workshop.end_time}`} />
              <DetailRow label="Mode" value={<span className="capitalize">{workshop.mode}</span>} />
              <DetailRow label="Venue" value={workshop.venue || "—"} />
              <DetailRow label="Meeting link" value={workshop.meeting_link || "—"} />
              <DetailRow label="Capacity" value={workshop.capacity ?? "Unlimited"} />
              <DetailRow label="Fee" value={workshop.fee > 0 ? workshop.fee.toLocaleString() : "Free"} />
              {workshop.description && (
                <div className="pt-3">
                  <p className="text-sm text-muted-foreground">Description</p>
                  <p className="mt-1 whitespace-pre-wrap text-sm">{workshop.description}</p>
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Registrations</CardTitle>
            </CardHeader>
            <CardContent>
              <RegistrationsPanel workshopId={workshop.id} />
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Change status</CardTitle>
            </CardHeader>
            <CardContent>
              <Select
                value={workshop.status}
                onValueChange={(value) => changeStatus.mutate(value as WorkshopStatus)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {workshopStatusValues.map((s) => (
                    <SelectItem key={s} value={s}>
                      {workshopStatusLabels[s]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </CardContent>
          </Card>
        </div>
      </div>

      <WorkshopFormDialog open={editOpen} onOpenChange={setEditOpen} workshop={workshop} />
    </div>
  );
}
