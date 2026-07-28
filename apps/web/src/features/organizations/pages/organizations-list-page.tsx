import { Plus } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useOrganizationsList } from "@/features/organizations/api/organizations-hooks";
import { OrganizationFormDialog } from "@/features/organizations/components/organization-form-dialog";
import { subscriptionPlanLabels } from "@/features/organizations/schemas/organization-schemas";

const PAGE_SIZE = 20;

export function OrganizationsListPage() {
  const navigate = useNavigate();
  const [skip, setSkip] = useState(0);
  const [formOpen, setFormOpen] = useState(false);

  const { data, isLoading, isError } = useOrganizationsList({ skip, limit: PAGE_SIZE });

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Organizations</h1>
          <p className="mt-1 text-muted-foreground">
            Manage tenant organizations, their branches, and settings.
          </p>
        </div>
        <Button onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          New Organization
        </Button>
      </div>

      <Card>
        <CardContent className="space-y-4 p-6">
          {isLoading && (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          )}

          {isError && (
            <p className="py-8 text-center text-sm text-destructive">
              Failed to load organizations. Please try again.
            </p>
          )}

          {!isLoading && !isError && (data?.length ?? 0) === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No organizations found. Create your first one to get started.
            </p>
          )}

          {!isLoading && !isError && (data?.length ?? 0) > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Slug</TableHead>
                  <TableHead>Plan</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.map((org) => (
                  <TableRow
                    key={org.id}
                    className="cursor-pointer"
                    onClick={() => navigate(`/organizations/${org.id}`)}
                  >
                    <TableCell className="font-medium">{org.name}</TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">{org.slug}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {subscriptionPlanLabels[org.subscription_plan]}
                    </TableCell>
                    <TableCell>
                      <Badge variant={org.is_active ? "success" : "secondary"}>
                        {org.is_active ? "Active" : "Inactive"}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}

          {!isLoading && (data?.length ?? 0) === PAGE_SIZE && (
            <div className="flex items-center justify-between pt-2">
              <p className="text-sm text-muted-foreground">Page {Math.floor(skip / PAGE_SIZE) + 1}</p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={skip === 0}
                  onClick={() => setSkip(Math.max(0, skip - PAGE_SIZE))}
                >
                  Previous
                </Button>
                <Button variant="outline" size="sm" onClick={() => setSkip(skip + PAGE_SIZE)}>
                  Next
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <OrganizationFormDialog open={formOpen} onOpenChange={setFormOpen} />
    </div>
  );
}
