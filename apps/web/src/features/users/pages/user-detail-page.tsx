import { ArrowLeft, Pencil } from "lucide-react";
import { type ReactNode, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useBranches } from "@/features/branches/api/branches-hooks";
import { UserProfileFormDialog } from "@/features/users/components/user-profile-form-dialog";
import { UserRolesPanel } from "@/features/users/components/user-roles-panel";
import { UserStatusBadge } from "@/features/users/components/user-status-badge";
import { useCurrentUserProfile, useUserProfile, useUsersList } from "@/features/users/api/users-hooks";
import { genderLabels } from "@/features/users/schemas/user-schemas";

function DetailRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b py-3 last:border-0">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm font-medium">{value}</span>
    </div>
  );
}

export function UserDetailPage() {
  const { userId } = useParams<{ userId: string }>();
  const navigate = useNavigate();
  const { data: currentProfile } = useCurrentUserProfile();
  const organizationId = currentProfile?.organization_id;
  const { data: users, isLoading: usersLoading } = useUsersList({
    organization_id: organizationId ?? "",
    limit: 200,
  });
  const { data: profile, isLoading: profileLoading } = useUserProfile(userId);
  const { data: branches } = useBranches(organizationId);

  const [editOpen, setEditOpen] = useState(false);

  const account = users?.find((u) => u.id === userId);

  if (usersLoading || profileLoading || !profile) {
    return (
      <div className="space-y-4 p-8">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const branchName = branches?.find((b) => b.id === profile.branch_id)?.name;

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => navigate("/administration/users")}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">{account?.full_name || "User"}</h1>
            <div className="mt-1 flex items-center gap-2">
              <span className="text-xs text-muted-foreground">{account?.email}</span>
              {account && <UserStatusBadge status={account.status} />}
            </div>
          </div>
        </div>
        <Button variant="outline" onClick={() => setEditOpen(true)}>
          <Pencil className="h-4 w-4" />
          Edit profile
        </Button>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Profile details</CardTitle>
            </CardHeader>
            <CardContent>
              <DetailRow label="Branch" value={branchName || "—"} />
              <DetailRow label="Employee code" value={profile.employee_code || "—"} />
              <DetailRow label="Designation" value={profile.designation || "—"} />
              <DetailRow label="Department" value={profile.department || "—"} />
              <DetailRow label="Gender" value={profile.gender ? genderLabels[profile.gender] : "—"} />
              <DetailRow
                label="Date of birth"
                value={profile.date_of_birth ? new Date(profile.date_of_birth).toLocaleDateString() : "—"}
              />
              <DetailRow
                label="Date of joining"
                value={
                  profile.date_of_joining ? new Date(profile.date_of_joining).toLocaleDateString() : "—"
                }
              />
              <DetailRow
                label="Address"
                value={
                  [profile.address_line1, profile.city, profile.state, profile.country, profile.postal_code]
                    .filter(Boolean)
                    .join(", ") || "—"
                }
              />
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6">
          <UserRolesPanel userId={profile.user_id} />
        </div>
      </div>

      <UserProfileFormDialog open={editOpen} onOpenChange={setEditOpen} profile={profile} />
    </div>
  );
}
