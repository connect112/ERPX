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
import { CreateUserDialog } from "@/features/users/components/create-user-dialog";
import { UserStatusBadge } from "@/features/users/components/user-status-badge";
import { useCurrentUserProfile, useUsersList } from "@/features/users/api/users-hooks";

const PAGE_SIZE = 20;

export function UsersListPage() {
  const navigate = useNavigate();
  const { data: currentProfile, isLoading: profileLoading, isError: profileError } = useCurrentUserProfile();
  const [skip, setSkip] = useState(0);
  const [formOpen, setFormOpen] = useState(false);

  const organizationId = currentProfile?.organization_id;
  const { data, isLoading, isError } = useUsersList({
    organization_id: organizationId ?? "",
    skip,
    limit: PAGE_SIZE,
  });

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Users</h1>
          <p className="mt-1 text-muted-foreground">
            Manage user accounts and their organizational profiles.
          </p>
        </div>
        <Button onClick={() => setFormOpen(true)} disabled={!organizationId}>
          <Plus className="h-4 w-4" />
          New User
        </Button>
      </div>

      <Card>
        <CardContent className="space-y-4 p-6">
          {profileLoading && (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          )}

          {!profileLoading && profileError && (
            <p className="py-8 text-center text-sm text-destructive">
              Your account is not yet associated with an organization. Contact your administrator.
            </p>
          )}

          {!profileLoading && !profileError && isLoading && (
            <div className="space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          )}

          {!profileLoading && !profileError && isError && (
            <p className="py-8 text-center text-sm text-destructive">
              Failed to load users. Please try again.
            </p>
          )}

          {!profileLoading && !profileError && !isLoading && !isError && (data?.length ?? 0) === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No users found. Add your first user to get started.
            </p>
          )}

          {!profileLoading && !profileError && !isLoading && !isError && (data?.length ?? 0) > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Designation</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.map((user) => (
                  <TableRow
                    key={user.id}
                    className="cursor-pointer"
                    onClick={() => navigate(`/administration/users/${user.id}`)}
                  >
                    <TableCell className="font-medium">{user.full_name}</TableCell>
                    <TableCell className="text-muted-foreground">{user.email}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {user.profile?.designation || "—"}
                    </TableCell>
                    <TableCell>
                      <UserStatusBadge status={user.status} />
                      {!user.is_email_verified && (
                        <Badge variant="secondary" className="ml-2">
                          Unverified
                        </Badge>
                      )}
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

      {organizationId && (
        <CreateUserDialog open={formOpen} onOpenChange={setFormOpen} organizationId={organizationId} />
      )}
    </div>
  );
}
