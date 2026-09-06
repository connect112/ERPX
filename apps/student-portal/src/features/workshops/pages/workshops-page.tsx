import { format, parseISO } from "date-fns";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useBrowseWorkshops,
  useMyWorkshopRegistrations,
  useRegisterForWorkshop,
} from "@/features/workshops/api/workshops-hooks";

export function WorkshopsPage() {
  const { data: workshops, isLoading } = useBrowseWorkshops();
  const { data: registrations } = useMyWorkshopRegistrations();
  const registerMutation = useRegisterForWorkshop();

  const registeredWorkshopIds = new Set((registrations ?? []).map((r) => r.workshop_id));

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold">Workshops</h1>
        <p className="text-sm text-muted-foreground">Upcoming workshops open for registration.</p>
      </div>

      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-40 w-full" />
        </div>
      ) : workshops && workshops.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {workshops.map((workshop) => {
            const isRegistered = registeredWorkshopIds.has(workshop.id);
            return (
              <Card key={workshop.id}>
                <CardHeader>
                  <div className="flex items-start justify-between gap-2">
                    <CardTitle className="text-base">{workshop.title}</CardTitle>
                    <Badge variant={workshop.mode === "virtual" ? "info" : "secondary"}>
                      {workshop.mode}
                    </Badge>
                  </div>
                  <CardDescription>
                    {format(parseISO(workshop.workshop_date), "PP")} · {workshop.start_time.slice(0, 5)}
                    –{workshop.end_time.slice(0, 5)}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  {workshop.description && (
                    <p className="text-sm text-muted-foreground">{workshop.description}</p>
                  )}
                  <p className="text-sm text-muted-foreground">
                    {workshop.venue ?? (workshop.mode === "virtual" ? "Online" : "TBA")}
                    {workshop.fee > 0 && ` · ₹${workshop.fee}`}
                  </p>
                  <Button
                    className="w-full"
                    variant={isRegistered ? "outline" : "default"}
                    disabled={isRegistered || registerMutation.isPending}
                    onClick={() => registerMutation.mutate(workshop.id)}
                  >
                    {isRegistered ? "Registered" : "Register"}
                  </Button>
                </CardContent>
              </Card>
            );
          })}
        </div>
      ) : (
        <p className="py-6 text-center text-sm text-muted-foreground">
          No upcoming workshops right now — check back soon.
        </p>
      )}
    </div>
  );
}
