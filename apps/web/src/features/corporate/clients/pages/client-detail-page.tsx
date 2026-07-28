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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  useChangeClientStatus,
  useClient,
  useDeleteClient,
} from "@/features/corporate/clients/api/clients-hooks";
import { ClientFormDialog } from "@/features/corporate/clients/components/client-form-dialog";
import { ClientStatusBadge } from "@/features/corporate/clients/components/client-status-badge";
import {
  type ClientStatus,
  clientStatusLabels,
  clientStatusValues,
} from "@/features/corporate/clients/schemas/client-schemas";
import { AMCPanel } from "@/features/corporate/amc/components/amc-panel";
import { DocumentsPanel } from "@/features/documents/components/documents-panel";
import { ContractsPanel } from "@/features/corporate/contracts/components/contracts-panel";
import { ProjectsPanel } from "@/features/corporate/projects/components/projects-panel";
import { QuotationsPanel } from "@/features/corporate/quotations/components/quotations-panel";
import { SOCPanel } from "@/features/corporate/soc/components/soc-panel";
import { TicketsPanel } from "@/features/corporate/tickets/components/tickets-panel";

function DetailRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b py-3 last:border-0">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm font-medium">{value}</span>
    </div>
  );
}

export function ClientDetailPage() {
  const { clientId } = useParams<{ clientId: string }>();
  const navigate = useNavigate();
  const { data: client, isLoading } = useClient(clientId);
  const changeStatus = useChangeClientStatus(clientId ?? "");
  const deleteClient = useDeleteClient();

  const [editOpen, setEditOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [statusTarget, setStatusTarget] = useState<ClientStatus | null>(null);

  if (isLoading || !client) {
    return (
      <div className="space-y-4 p-8">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const handleDelete = () => {
    deleteClient.mutate(client.id, { onSuccess: () => navigate("/corporate/clients") });
  };

  const handleConfirmStatus = () => {
    if (!statusTarget) return;
    changeStatus.mutate(statusTarget, { onSuccess: () => setStatusTarget(null) });
  };

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => navigate("/corporate/clients")}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">{client.name}</h1>
            <div className="mt-1 flex items-center gap-2">
              <span className="font-mono text-xs text-muted-foreground">{client.client_code}</span>
              <ClientStatusBadge status={client.status} />
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
        <div className="space-y-6 lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Client details</CardTitle>
            </CardHeader>
            <CardContent>
              <DetailRow label="Industry" value={client.industry || "—"} />
              <DetailRow label="Website" value={client.website || "—"} />
              <DetailRow label="GSTIN" value={client.gstin || "—"} />
              <DetailRow label="Contact person" value={client.contact_person_name || "—"} />
              <DetailRow label="Contact email" value={client.contact_email || "—"} />
              <DetailRow label="Contact phone" value={client.contact_phone || "—"} />
              <DetailRow
                label="Address"
                value={
                  [client.address_line1, client.city, client.state, client.country, client.postal_code]
                    .filter(Boolean)
                    .join(", ") || "—"
                }
              />
              {client.notes && (
                <div className="pt-3">
                  <p className="text-sm text-muted-foreground">Notes</p>
                  <p className="mt-1 whitespace-pre-wrap text-sm">{client.notes}</p>
                </div>
              )}
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
                value={client.status}
                onValueChange={(value) => setStatusTarget(value as ClientStatus)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {clientStatusValues.map((s) => (
                    <SelectItem key={s} value={s}>
                      {clientStatusLabels[s]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </CardContent>
          </Card>
        </div>
      </div>

      <Tabs defaultValue="projects">
        <TabsList>
          <TabsTrigger value="projects">Projects</TabsTrigger>
          <TabsTrigger value="quotations">Quotations</TabsTrigger>
          <TabsTrigger value="contracts">Contracts</TabsTrigger>
          <TabsTrigger value="tickets">Tickets</TabsTrigger>
          <TabsTrigger value="amc">AMC</TabsTrigger>
          <TabsTrigger value="soc">SOC</TabsTrigger>
          <TabsTrigger value="documents">Documents</TabsTrigger>
        </TabsList>
        <TabsContent value="projects">
          <ProjectsPanel clientId={client.id} />
        </TabsContent>
        <TabsContent value="quotations">
          <QuotationsPanel clientId={client.id} />
        </TabsContent>
        <TabsContent value="contracts">
          <ContractsPanel clientId={client.id} />
        </TabsContent>
        <TabsContent value="tickets">
          <TicketsPanel clientId={client.id} />
        </TabsContent>
        <TabsContent value="amc">
          <AMCPanel clientId={client.id} />
        </TabsContent>
        <TabsContent value="soc">
          <SOCPanel clientId={client.id} />
        </TabsContent>
        <TabsContent value="documents">
          <DocumentsPanel entityType="corporate_clients" entityId={client.id} />
        </TabsContent>
      </Tabs>

      <ClientFormDialog open={editOpen} onOpenChange={setEditOpen} client={client} />

      <Dialog
        open={!!statusTarget}
        onOpenChange={(open) => !open && setStatusTarget(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              Mark client as {statusTarget ? clientStatusLabels[statusTarget] : ""}
            </DialogTitle>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setStatusTarget(null)}>
              Cancel
            </Button>
            <Button onClick={handleConfirmStatus} disabled={changeStatus.isPending}>
              {changeStatus.isPending ? "Updating..." : "Confirm"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete client</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Are you sure you want to delete <span className="font-medium">{client.name}</span>? This
            action cannot be undone.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteOpen(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDelete} disabled={deleteClient.isPending}>
              {deleteClient.isPending ? "Deleting..." : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
