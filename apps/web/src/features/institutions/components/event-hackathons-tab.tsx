import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link2, Plus, Unlink } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { HackathonFormDialog } from "@/features/hackathons/components/hackathon-form-dialog";
import { type InstitutionEvent, institutionsApi, institutionsKeys } from "@/features/institutions/api/institutions-api";
import { errorMessage, formatDateRange } from "@/features/institutions/lib/format";

/**
 * The hackathons of an event. Like exams, a hackathon is one record: link an existing one or create it here, and it stays
 * reachable from Hackathons too. Removing it from the event never deletes it.
 */
export function EventHackathonsTab({ event }: { event: InstitutionEvent }) {
  const queryClient = useQueryClient();
  const [linking, setLinking] = useState(false);
  const [creating, setCreating] = useState(false);
  const list = useQuery({ queryKey: institutionsKeys.eventHackathons(event.id), queryFn: () => institutionsApi.eventHackathons(event.id) });
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: institutionsKeys.all });
    void queryClient.invalidateQueries({ queryKey: ["hackathons"] });
  };
  const unlink = useMutation({ mutationFn: (id: string) => institutionsApi.unlinkHackathon(event.id, id), onSuccess: refresh });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted-foreground">Hackathons held as part of this event. Open one to manage its teams, scores and leaderboard.</p>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setLinking(true)}>
            <Link2 className="h-4 w-4" />
            Link existing hackathon
          </Button>
          <Button onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" />
            New hackathon
          </Button>
        </div>
      </div>
      <Card>
        <CardContent className="p-0">
          {list.isLoading ? (
            <div className="p-6">
              <Skeleton className="h-10 w-full" />
            </div>
          ) : (list.data?.length ?? 0) === 0 ? (
            <p className="p-8 text-center text-sm text-muted-foreground">No hackathons on this event yet.</p>
          ) : (
            <ul className="divide-y">
              {list.data?.map((h) => (
                <li key={h.id} className="flex items-center justify-between gap-3 p-4">
                  <div>
                    <Link to={`/hackathons/${h.id}`} className="font-medium hover:underline">
                      {h.title}
                    </Link>
                    <p className="text-xs text-muted-foreground">
                      {h.code} · {formatDateRange(h.start_date, h.end_date)}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant="outline" className="capitalize">{h.status.replace(/_/g, " ")}</Badge>
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label={`Remove ${h.title} from this event`}
                      onClick={() => {
                        if (window.confirm(`Remove "${h.title}" from this event? The hackathon itself is kept in Hackathons.`)) unlink.mutate(h.id);
                      }}
                    >
                      <Unlink className="h-4 w-4" />
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
      {unlink.isError && <p className="text-sm text-destructive">{errorMessage(unlink.error, "Could not remove the hackathon.")}</p>}
      {linking && <LinkHackathonDialog event={event} onClose={() => setLinking(false)} onDone={refresh} />}
      <HackathonFormDialog
        open={creating}
        onOpenChange={(open) => {
          setCreating(open);
          if (!open) refresh();
        }}
        eventId={event.id}
      />
    </div>
  );
}

function LinkHackathonDialog({ event, onClose, onDone }: { event: InstitutionEvent; onClose: () => void; onDone: () => void }) {
  const candidates = useQuery({ queryKey: ["institutions", "hackathon-candidates", event.id], queryFn: () => institutionsApi.hackathonCandidates(event.id) });
  const link = useMutation({
    mutationFn: (id: string) => institutionsApi.linkHackathon(event.id, id),
    onSuccess: () => {
      onDone();
      onClose();
    },
  });
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-h-[90vh] max-w-lg overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Link an existing hackathon</DialogTitle>
          <DialogDescription>Hackathons that are not part of any event yet. Linking does not copy the hackathon; it is the same one in both places.</DialogDescription>
        </DialogHeader>
        {candidates.isLoading ? (
          <Skeleton className="h-10 w-full" />
        ) : (candidates.data?.length ?? 0) === 0 ? (
          <p className="text-sm text-muted-foreground">Every hackathon already belongs to an event. Create a new one instead.</p>
        ) : (
          <ul className="divide-y rounded-md border">
            {candidates.data?.map((h) => (
              <li key={h.id} className="flex items-center justify-between gap-3 p-3">
                <div>
                  <p className="text-sm font-medium">{h.title}</p>
                  <p className="text-xs text-muted-foreground">
                    {h.code} · {formatDateRange(h.start_date, h.end_date)}
                  </p>
                </div>
                <Button size="sm" disabled={link.isPending} onClick={() => link.mutate(h.id)}>
                  Link
                </Button>
              </li>
            ))}
          </ul>
        )}
        {link.isError && <p className="text-sm text-destructive">{errorMessage(link.error, "Could not link the hackathon.")}</p>}
      </DialogContent>
    </Dialog>
  );
}
