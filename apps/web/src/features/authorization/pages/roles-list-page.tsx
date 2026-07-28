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
import { useRolesList } from "@/features/authorization/api/authorization-hooks";
import { RoleFormDialog } from "@/features/authorization/components/role-form-dialog";

export function RolesListPage() {
  const navigate = useNavigate();
  const { data: roles, isLoading, isError } = useRolesList();
  const [formOpen, setFormOpen] = useState(false);

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Roles</h1>
          <p className="mt-1 text-muted-foreground">
            Define roles and the permissions each one grants.
          </p>
        </div>
        <Button onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          New Role
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
              Failed to load roles. Please try again.
            </p>
          )}

          {!isLoading && !isError && (roles?.length ?? 0) === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No roles found. Create your first role to get started.
            </p>
          )}

          {!isLoading && !isError && (roles?.length ?? 0) > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Slug</TableHead>
                  <TableHead>Description</TableHead>
                  <TableHead>Type</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {roles?.map((role) => (
                  <TableRow
                    key={role.id}
                    className="cursor-pointer"
                    onClick={() => navigate(`/administration/roles/${role.id}`)}
                  >
                    <TableCell className="font-medium">{role.name}</TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">{role.slug}</TableCell>
                    <TableCell className="text-muted-foreground">{role.description || "—"}</TableCell>
                    <TableCell>
                      <Badge variant={role.is_system ? "secondary" : "info"}>
                        {role.is_system ? "System" : "Custom"}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <RoleFormDialog open={formOpen} onOpenChange={setFormOpen} />
    </div>
  );
}
