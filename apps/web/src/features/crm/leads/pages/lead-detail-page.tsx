import { ArrowLeft, Pencil, Trash2 } from "lucide-react";
import { type ReactNode, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { AdmissionTab } from "@/features/crm/admissions/components/admission-tab";
import { CounsellingTab } from "@/features/crm/counselling/components/counselling-tab";
import { EnquiriesTab } from "@/features/crm/enquiries/components/enquiries-tab";
import { FollowUpsTab } from "@/features/crm/followups/components/followups-tab";
import { useChangeLeadStatus, useDeleteLead, useLead } from "@/features/crm/leads/api/leads-hooks";
import { LeadFormDialog } from "@/features/crm/leads/components/lead-form-dialog";
import { LeadStatusBadge } from "@/features/crm/leads/components/lead-status-badge";
import {
  type LeadStatus,
  leadSourceLabels,
  leadStatusLabels,
  leadStatusTransitions,
} from "@/features/crm/leads/schemas/lead-schemas";

function DetailRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b py-3 last:border-0">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm font-medium">{value}</span>
    </div>
  );
}

export function LeadDetailPage() {
  const { leadId } = useParams<{ leadId: string }>();
  const navigate = useNavigate();
  const { data: lead, isLoading } = useLead(leadId);
  const changeStatus = useChangeLeadStatus(leadId ?? "");
  const deleteLead = useDeleteLead();

  const [editOpen, setEditOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [statusTarget, setStatusTarget] = useState<LeadStatus | null>(null);
  const [lostReason, setLostReason] = useState("");

  if (isLoading || !lead) {
    return (
      <div className="space-y-4 p-8">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const availableTransitions = leadStatusTransitions[lead.status];

  const handleConfirmStatus = () => {
    if (!statusTarget) return;
    changeStatus.mutate(
      { status: statusTarget, lost_reason: statusTarget === "lost" ? lostReason : undefined },
      {
        onSuccess: () => {
          setStatusTarget(null);
          setLostReason("");
        },
      }
    );
  };

  const handleDelete = () => {
    deleteLead.mutate(lead.id, {
      onSuccess: () => navigate("/crm/leads"),
    });
  };

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => navigate("/crm/leads")}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">{lead.full_name}</h1>
            <div className="mt-1">
              <LeadStatusBadge status={lead.status} />
            </div>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setEditOpen(true)}>
            <Pencil className="h-4 w-4" />
            Edit
          </Button>
          <Button variant="outline" onClick={() => setDeleteOpen(true)}>
            <Trash2 className="h-4 w-4" />
            Delete
          </Button>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">Lead details</CardTitle>
          </CardHeader>
          <CardContent>
            <DetailRow label="Email" value={lead.email || "—"} />
            <DetailRow label="Phone" value={lead.phone || "—"} />
            <DetailRow label="Source" value={leadSourceLabels[lead.source]} />
            <DetailRow
              label="Created"
              value={new Date(lead.created_at).toLocaleString()}
            />
            {lead.status === "lost" && lead.lost_reason && (
              <DetailRow label="Lost reason" value={lead.lost_reason} />
            )}
            {lead.notes && (
              <div className="pt-3">
                <p className="text-sm text-muted-foreground">Notes</p>
                <p className="mt-1 whitespace-pre-wrap text-sm">{lead.notes}</p>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Change status</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {availableTransitions.length === 0 && (
              <p className="text-sm text-muted-foreground">
                No further transitions available from this status.
              </p>
            )}
            {availableTransitions.map((next) => (
              <Button
                key={next}
                variant="outline"
                className="w-full justify-start"
                onClick={() => setStatusTarget(next)}
              >
                Mark as {leadStatusLabels[next]}
              </Button>
            ))}
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="enquiries">
        <TabsList>
          <TabsTrigger value="enquiries">Enquiries</TabsTrigger>
          <TabsTrigger value="followups">Follow-ups</TabsTrigger>
          <TabsTrigger value="counselling">Counselling</TabsTrigger>
          <TabsTrigger value="admission">Admission</TabsTrigger>
        </TabsList>
        <TabsContent value="enquiries">
          <EnquiriesTab leadId={lead.id} />
        </TabsContent>
        <TabsContent value="followups">
          <FollowUpsTab leadId={lead.id} />
        </TabsContent>
        <TabsContent value="counselling">
          <CounsellingTab leadId={lead.id} />
        </TabsContent>
        <TabsContent value="admission">
          <AdmissionTab leadId={lead.id} />
        </TabsContent>
      </Tabs>

      <LeadFormDialog open={editOpen} onOpenChange={setEditOpen} lead={lead} />

      <Dialog open={!!statusTarget} onOpenChange={(open) => !open && setStatusTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              Mark lead as {statusTarget ? leadStatusLabels[statusTarget] : ""}
            </DialogTitle>
          </DialogHeader>

          {statusTarget === "lost" && (
            <div className="space-y-2">
              <Label htmlFor="lostReason">Reason</Label>
              <Textarea
                id="lostReason"
                rows={3}
                value={lostReason}
                onChange={(e) => setLostReason(e.target.value)}
                placeholder="Why was this lead lost?"
              />
              {changeStatus.isError && !lostReason.trim() && (
                <p className="text-sm text-destructive">A reason is required.</p>
              )}
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => setStatusTarget(null)}>
              Cancel
            </Button>
            <Button
              onClick={handleConfirmStatus}
              disabled={
                changeStatus.isPending || (statusTarget === "lost" && !lostReason.trim())
              }
            >
              {changeStatus.isPending ? "Updating..." : "Confirm"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete lead</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Are you sure you want to delete <span className="font-medium">{lead.full_name}</span>?
            This action cannot be undone.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteOpen(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDelete} disabled={deleteLead.isPending}>
              {deleteLead.isPending ? "Deleting..." : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
