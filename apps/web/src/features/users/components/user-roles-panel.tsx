import { Plus, X } from "lucide-react";
import { useState } from "react";

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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useAssignRole, useRevokeRole, useRolesList, useUserRoles } from "@/features/authorization/api/authorization-hooks";

export function UserRolesPanel({ userId }: { userId: string }) {
  const { data: userRoles, isLoading } = useUserRoles(userId);
  const { data: allRoles } = useRolesList();
  const assignRole = useAssignRole();
  const revokeRole = useRevokeRole();

  const [assignOpen, setAssignOpen] = useState(false);
  const [selectedRoleId, setSelectedRoleId] = useState("");

  const assignedRoleIds = new Set(userRoles?.roles.map((r) => r.id));
  const availableRoles = allRoles?.filter((r) => !assignedRoleIds.has(r.id));

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base">Roles</CardTitle>
        <Button size="sm" onClick={() => setAssignOpen(true)}>
          <Plus className="h-4 w-4" />
          Assign role
        </Button>
      </CardHeader>
      <CardContent className="space-y-4">
        {isLoading && <Skeleton className="h-16 w-full" />}
        {!isLoading && (userRoles?.roles.length ?? 0) === 0 && (
          <p className="text-sm text-muted-foreground">No roles assigned.</p>
        )}
        {!isLoading && (userRoles?.roles.length ?? 0) > 0 && (
          <div className="flex flex-wrap gap-2">
            {userRoles?.roles.map((role) => (
              <Badge key={role.id} variant="secondary" className="flex items-center gap-1 pr-1">
                {role.name}
                <button
                  type="button"
                  className="ml-1 rounded-full hover:bg-muted-foreground/20"
                  onClick={() => revokeRole.mutate({ userId, roleId: role.id })}
                  disabled={revokeRole.isPending}
                >
                  <X className="h-3 w-3" />
                </button>
              </Badge>
            ))}
          </div>
        )}
        {userRoles && userRoles.effective_permissions.length > 0 && (
          <div>
            <p className="mb-1 text-xs text-muted-foreground">
              {userRoles.effective_permissions.length} effective permission(s)
            </p>
          </div>
        )}
      </CardContent>

      <Dialog open={assignOpen} onOpenChange={setAssignOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Assign role</DialogTitle>
          </DialogHeader>
          <Select value={selectedRoleId || undefined} onValueChange={setSelectedRoleId}>
            <SelectTrigger>
              <SelectValue placeholder="Select role" />
            </SelectTrigger>
            <SelectContent>
              {availableRoles?.map((r) => (
                <SelectItem key={r.id} value={r.id}>
                  {r.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {assignRole.isError && (
            <p className="text-sm text-destructive">
              {(assignRole.error as { response?: { data?: { error?: { message?: string } } } })
                ?.response?.data?.error?.message ?? "Something went wrong. Please try again."}
            </p>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => setAssignOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={() =>
                assignRole.mutate(
                  { userId, roleId: selectedRoleId },
                  {
                    onSuccess: () => {
                      setAssignOpen(false);
                      setSelectedRoleId("");
                    },
                  }
                )
              }
              disabled={!selectedRoleId || assignRole.isPending}
            >
              {assignRole.isPending ? "Assigning..." : "Assign"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
