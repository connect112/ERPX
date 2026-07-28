import { Pencil, Plus, Trash2 } from "lucide-react";
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
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { BranchPublic } from "@/features/branches/api/branches-api";
import { useBranches, useDeleteBranch } from "@/features/branches/api/branches-hooks";
import { BranchFormDialog } from "@/features/branches/components/branch-form-dialog";

export function BranchesPanel({ organizationId }: { organizationId: string }) {
  const { data: branches, isLoading, isError } = useBranches(organizationId);
  const deleteBranch = useDeleteBranch(organizationId);
  const [formOpen, setFormOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<BranchPublic | undefined>(undefined);
  const [deleteTarget, setDeleteTarget] = useState<BranchPublic | null>(null);

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base">Branches</CardTitle>
        <Button
          size="sm"
          onClick={() => {
            setEditTarget(undefined);
            setFormOpen(true);
          }}
        >
          <Plus className="h-4 w-4" />
          New branch
        </Button>
      </CardHeader>
      <CardContent>
        {isLoading && <Skeleton className="h-32 w-full" />}
        {isError && <p className="text-sm text-destructive">Failed to load branches.</p>}
        {!isLoading && !isError && (branches?.length ?? 0) === 0 && (
          <p className="py-4 text-center text-sm text-muted-foreground">No branches yet.</p>
        )}
        {!isLoading && !isError && (branches?.length ?? 0) > 0 && (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Code</TableHead>
                <TableHead>Name</TableHead>
                <TableHead>Location</TableHead>
                <TableHead>Head office</TableHead>
                <TableHead>Status</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {branches?.map((branch) => (
                <TableRow key={branch.id}>
                  <TableCell className="font-mono text-xs text-muted-foreground">{branch.code}</TableCell>
                  <TableCell className="font-medium">{branch.name}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {[branch.city, branch.state, branch.country].filter(Boolean).join(", ") || "—"}
                  </TableCell>
                  <TableCell>
                    {branch.is_head_office && <Badge variant="info">Head office</Badge>}
                  </TableCell>
                  <TableCell>
                    <Badge variant={branch.is_active ? "success" : "secondary"}>
                      {branch.is_active ? "Active" : "Inactive"}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right">
                    <div className="flex justify-end gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => {
                          setEditTarget(branch);
                          setFormOpen(true);
                        }}
                      >
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button variant="ghost" size="icon" onClick={() => setDeleteTarget(branch)}>
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>

      <BranchFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        organizationId={organizationId}
        branch={editTarget}
      />

      <Dialog open={!!deleteTarget} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete branch</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Are you sure you want to delete{" "}
            <span className="font-medium">{deleteTarget?.name}</span>? This action cannot be undone.
          </p>
          {deleteBranch.isError && (
            <p className="text-sm text-destructive">
              {(deleteBranch.error as { response?: { data?: { error?: { message?: string } } } })
                ?.response?.data?.error?.message ?? "Something went wrong. Please try again."}
            </p>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                if (!deleteTarget) return;
                deleteBranch.mutate(deleteTarget.id, { onSuccess: () => setDeleteTarget(null) });
              }}
              disabled={deleteBranch.isPending}
            >
              {deleteBranch.isPending ? "Deleting..." : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
