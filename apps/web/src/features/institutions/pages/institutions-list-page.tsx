import { useQuery } from "@tanstack/react-query";
import { FileText, Plus } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { institutionsApi, institutionsKeys } from "@/features/institutions/api/institutions-api";
import { InstitutionFormDialog } from "@/features/institutions/components/institution-form-dialog";
import { useDebounced } from "@/features/institutions/lib/use-debounced";

export function InstitutionsListPage() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  const q = useDebounced(search.trim());

  const { data, isLoading, isError } = useQuery({
    queryKey: institutionsKeys.list(q),
    queryFn: () => institutionsApi.list(q),
  });

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Institutions</h1>
          <p className="text-sm text-muted-foreground">
            The colleges we partner with: their MOU and faculty contact, the events held there, and the students who
            registered for them.
          </p>
        </div>
        <Button onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          New institution
        </Button>
      </div>

      <Input
        aria-label="Search institutions"
        placeholder="Search by institution, city or faculty name"
        className="max-w-md"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />

      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="space-y-2 p-6">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : isError ? (
            <p className="p-6 text-sm text-destructive">Could not load institutions.</p>
          ) : (data?.items.length ?? 0) === 0 ? (
            <p className="p-8 text-center text-sm text-muted-foreground">
              {q ? "No institution matches that search." : "No institutions yet. Add the first one to get started."}
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Institution</TableHead>
                  <TableHead>Location</TableHead>
                  <TableHead>Faculty contact</TableHead>
                  <TableHead>Events</TableHead>
                  <TableHead>Students</TableHead>
                  <TableHead>MOU</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.items.map((i) => (
                  <TableRow key={i.id} className="cursor-pointer" onClick={() => navigate(`/institutions/${i.id}`)}>
                    <TableCell className="font-medium">{i.name}</TableCell>
                    <TableCell>{i.location}</TableCell>
                    <TableCell>
                      {i.faculty_name}
                      {i.faculty_designation && <span className="block text-xs text-muted-foreground">{i.faculty_designation}</span>}
                    </TableCell>
                    <TableCell>{i.event_count}</TableCell>
                    <TableCell>{i.student_count}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {i.mou_filename ? (
                        <span className="inline-flex items-center gap-1">
                          <FileText className="h-4 w-4" aria-hidden="true" />
                          Uploaded
                        </span>
                      ) : i.mou_details ? (
                        "Noted"
                      ) : (
                        "—"
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {formOpen && <InstitutionFormDialog onClose={() => setFormOpen(false)} onSaved={(i) => navigate(`/institutions/${i.id}`)} />}
    </div>
  );
}
