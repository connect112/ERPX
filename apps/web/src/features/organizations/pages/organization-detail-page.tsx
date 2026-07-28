import { ArrowLeft, Pencil, Trash2 } from "lucide-react";
import { type ReactNode, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useDeleteOrganization, useOrganization } from "@/features/organizations/api/organizations-hooks";
import { OrganizationFormDialog } from "@/features/organizations/components/organization-form-dialog";
import { subscriptionPlanLabels } from "@/features/organizations/schemas/organization-schemas";
import { BranchesPanel } from "@/features/branches/components/branches-panel";
import { OrgSettingsPanel } from "@/features/settings/components/org-settings-panel";

function DetailRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b py-3 last:border-0">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm font-medium">{value}</span>
    </div>
  );
}

export function OrganizationDetailPage() {
  const { orgId } = useParams<{ orgId: string }>();
  const navigate = useNavigate();
  const { data: org, isLoading } = useOrganization(orgId);
  const deleteOrganization = useDeleteOrganization();

  const [editOpen, setEditOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);

  if (isLoading || !org) {
    return (
      <div className="space-y-4 p-8">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const handleDelete = () => {
    deleteOrganization.mutate(org.id, { onSuccess: () => navigate("/organizations") });
  };

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => navigate("/organizations")}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">{org.name}</h1>
            <div className="mt-1 flex items-center gap-2">
              <span className="font-mono text-xs text-muted-foreground">{org.slug}</span>
              <Badge variant={org.is_active ? "success" : "secondary"}>
                {org.is_active ? "Active" : "Inactive"}
              </Badge>
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

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Organization details</CardTitle>
        </CardHeader>
        <CardContent>
          <DetailRow label="Legal name" value={org.legal_name || "—"} />
          <DetailRow label="Industry" value={org.industry || "—"} />
          <DetailRow label="Email" value={org.email || "—"} />
          <DetailRow label="Phone" value={org.phone || "—"} />
          <DetailRow label="Website" value={org.website || "—"} />
          <DetailRow label="Subscription plan" value={subscriptionPlanLabels[org.subscription_plan]} />
          <DetailRow
            label="Address"
            value={
              [org.address_line1, org.city, org.state, org.country, org.postal_code]
                .filter(Boolean)
                .join(", ") || "—"
            }
          />
        </CardContent>
      </Card>

      <Tabs defaultValue="branches">
        <TabsList>
          <TabsTrigger value="branches">Branches</TabsTrigger>
          <TabsTrigger value="settings">Settings</TabsTrigger>
        </TabsList>
        <TabsContent value="branches">
          <BranchesPanel organizationId={org.id} />
        </TabsContent>
        <TabsContent value="settings">
          <OrgSettingsPanel organizationId={org.id} />
        </TabsContent>
      </Tabs>

      <OrganizationFormDialog open={editOpen} onOpenChange={setEditOpen} organization={org} />

      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete organization</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Are you sure you want to delete <span className="font-medium">{org.name}</span>? This action
            cannot be undone.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteOpen(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDelete} disabled={deleteOrganization.isPending}>
              {deleteOrganization.isPending ? "Deleting..." : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
