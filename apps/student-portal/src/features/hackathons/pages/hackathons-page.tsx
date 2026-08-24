import { format, parseISO } from "date-fns";
import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useBrowseHackathons } from "@/features/hackathons/api/hackathons-hooks";

export function HackathonsPage() {
  const { data: hackathons, isLoading } = useBrowseHackathons();

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold">Hackathons</h1>
        <p className="text-sm text-muted-foreground">Open for registration, or currently ongoing.</p>
      </div>

      {isLoading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-40 w-full" />
        </div>
      ) : hackathons && hackathons.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {hackathons.map((hackathon) => (
            <Card key={hackathon.id}>
              <CardHeader>
                <div className="flex items-start justify-between gap-2">
                  <CardTitle className="text-base">{hackathon.title}</CardTitle>
                  <Badge variant={hackathon.status === "ongoing" ? "success" : "info"}>
                    {hackathon.status === "ongoing" ? "Ongoing" : "Open"}
                  </Badge>
                </div>
                {hackathon.theme && <CardDescription>{hackathon.theme}</CardDescription>}
              </CardHeader>
              <CardContent className="space-y-3">
                <p className="text-sm text-muted-foreground">
                  {format(parseISO(hackathon.start_date), "PP")} – {format(parseISO(hackathon.end_date), "PP")}
                </p>
                <p className="text-sm text-muted-foreground">
                  Teams up to {hackathon.max_team_size} · Register by{" "}
                  {format(parseISO(hackathon.registration_deadline), "PP")}
                </p>
                <Button asChild className="w-full">
                  <Link to={`/hackathons/${hackathon.id}`}>View & join a team</Link>
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <p className="py-6 text-center text-sm text-muted-foreground">
          No hackathons open right now — check back soon.
        </p>
      )}
    </div>
  );
}
