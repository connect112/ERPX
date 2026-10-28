import { useQuery } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useMyRoles } from "@/features/auth/api/authorization-hooks";
import { ourInternshipsApi, ourInternshipsKeys } from "@/features/our-internships/api/our-internships-api";
import { InternshipFormDialog } from "@/features/our-internships/components/internship-form-dialog";
import { statusBadge } from "@/features/our-internships/lib/performance";

export function OurInternshipsListPage() {
  const navigate = useNavigate();
  const [creating, setCreating] = useState(false);
  const roles = useMyRoles();
  // instructors see the programmes they were given, but only people with the manage permission start new ones
  const canCreate = !!roles.data && (roles.data.is_superuser || roles.data.effective_permissions.includes("our_internships.manage"));
  const { data, isLoading, isError } = useQuery({ queryKey: ourInternshipsKeys.list(), queryFn: ourInternshipsApi.list });

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Our Internships</h1>
          <p className="text-sm text-muted-foreground">
            Select students for our internships from the results of the workshops and hackathons held at institutions.
          </p>
        </div>
        {canCreate && (
          <Button onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" />
            Start a new internship
          </Button>
        )}
      </div>

      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="space-y-2 p-6">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : isError ? (
            <p className="p-6 text-sm text-destructive">Could not load internships.</p>
          ) : (data?.length ?? 0) === 0 ? (
            <p className="p-8 text-center text-sm text-muted-foreground">No internships yet. Start one to begin selecting students.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Internship</TableHead>
                  <TableHead>Selecting from</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Selected</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.map((i) => (
                  <TableRow key={i.id} className="cursor-pointer" onClick={() => navigate(`/our-internships/${i.id}`)}>
                    <TableCell className="font-medium">{i.title}</TableCell>
                    <TableCell>
                      {i.scope === "all" ? (
                        "All students"
                      ) : (
                        <>
                          {i.institution_name}
                          <span className="block text-xs text-muted-foreground">{i.event_name ?? "All events"}</span>
                        </>
                      )}
                    </TableCell>
                    <TableCell>
                      <Badge variant={statusBadge[i.status].variant}>{statusBadge[i.status].label}</Badge>
                    </TableCell>
                    <TableCell>{i.selected_count}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {creating && <InternshipFormDialog onClose={() => setCreating(false)} onCreated={(i) => navigate(`/our-internships/${i.id}`)} />}
    </div>
  );
}
