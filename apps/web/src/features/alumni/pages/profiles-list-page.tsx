import { useState } from "react";

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
import { useProfilesList, useVerifyProfile } from "@/features/alumni/api/alumni-hooks";

const PAGE_SIZE = 20;

export function ProfilesListPage() {
  const [skip, setSkip] = useState(0);
  const { data, isLoading, isError } = useProfilesList({ skip, limit: PAGE_SIZE });
  const verifyProfile = useVerifyProfile();

  const total = data?.total ?? 0;
  const page = Math.floor(skip / PAGE_SIZE) + 1;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-6 p-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Alumni Profiles</h1>
        <p className="mt-1 text-muted-foreground">
          Graduated students who have opted in to the alumni network.
        </p>
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
              Failed to load alumni profiles. Please try again.
            </p>
          )}

          {!isLoading && !isError && (data?.items.length ?? 0) === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No alumni profiles yet. They appear here once a graduated student creates one.
            </p>
          )}

          {!isLoading && !isError && (data?.items.length ?? 0) > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Graduation year</TableHead>
                  <TableHead>Current company</TableHead>
                  <TableHead>Current designation</TableHead>
                  <TableHead>Verified</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.items.map((profile) => (
                  <TableRow key={profile.id}>
                    <TableCell>{profile.graduation_year ?? "—"}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {profile.current_company || "—"}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {profile.current_designation || "—"}
                    </TableCell>
                    <TableCell>
                      <Badge variant={profile.is_verified ? "success" : "secondary"}>
                        {profile.is_verified ? "Verified" : "Unverified"}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={verifyProfile.isPending}
                        onClick={() =>
                          verifyProfile.mutate({ id: profile.id, isVerified: !profile.is_verified })
                        }
                      >
                        {profile.is_verified ? "Unverify" : "Verify"}
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}

          {!isLoading && total > PAGE_SIZE && (
            <div className="flex items-center justify-between pt-2">
              <p className="text-sm text-muted-foreground">
                Page {page} of {pageCount} ({total} profiles)
              </p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={skip === 0}
                  onClick={() => setSkip(Math.max(0, skip - PAGE_SIZE))}
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={skip + PAGE_SIZE >= total}
                  onClick={() => setSkip(skip + PAGE_SIZE)}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
