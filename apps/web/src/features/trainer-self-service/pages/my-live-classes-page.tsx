import { useState } from "react";
import { ExternalLink, Video } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { LiveClassStatusBadge } from "@/features/live-classes/components/live-class-status-badge";
import type { LiveClassPublic, LiveClassStatus } from "@/features/live-classes/api/live-classes-api";
import { useMyBatches } from "@/features/trainer-self-service/api/batches-hooks";
import type { LiveClassJoinToken } from "@/features/trainer-self-service/api/live-classes-api";
import {
  useChangeMyLiveClassStatus,
  useJoinMyLiveClass,
  useMyLiveClasses,
} from "@/features/trainer-self-service/api/live-classes-hooks";
import { VideoCallOverlay } from "@/features/trainer-self-service/components/video-call-overlay";

// What a trainer can do to one of their own live classes from here,
// keyed by its current status — mirrors the admin LiveClassesPanel's
// same status machine, enforced again server-side by
// modules/live_classes/service.py's _ALLOWED_TRANSITIONS.
const NEXT_STATUS: Record<LiveClassStatus, { label: string; status: LiveClassStatus }[]> = {
  scheduled: [
    { label: "Start", status: "live" },
    { label: "Cancel", status: "cancelled" },
  ],
  live: [{ label: "Complete", status: "completed" }],
  completed: [],
  cancelled: [],
};

interface ActiveCall extends LiveClassJoinToken {
  title: string;
  liveClassId: string;
}

export function MyLiveClassesPage() {
  const { data: liveClasses, isLoading } = useMyLiveClasses();
  const { data: batches } = useMyBatches();
  const changeStatus = useChangeMyLiveClassStatus();
  const joinLiveClass = useJoinMyLiveClass();
  const [activeCall, setActiveCall] = useState<ActiveCall | null>(null);

  const batchNames = new Map((batches ?? []).map((b) => [b.id, b.name]));

  const sorted = [...(liveClasses ?? [])].sort(
    (a, b) => new Date(b.scheduled_at).getTime() - new Date(a.scheduled_at).getTime()
  );

  const handleJoin = (liveClass: LiveClassPublic) => {
    joinLiveClass.mutate(liveClass.id, {
      onSuccess: (token) =>
        setActiveCall({ ...token, title: liveClass.title, liveClassId: liveClass.id }),
    });
  };

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold">My Live Classes</h1>
        <p className="text-sm text-muted-foreground">
          Sessions scheduled for the batches you teach. Join, start, and mark them complete here.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">All sessions</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-2">
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-10 w-full" />
            </div>
          ) : sorted.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Batch</TableHead>
                  <TableHead>Title</TableHead>
                  <TableHead>Scheduled</TableHead>
                  <TableHead>Duration</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sorted.map((liveClass) => (
                  <LiveClassRow
                    key={liveClass.id}
                    liveClass={liveClass}
                    batchName={batchNames.get(liveClass.batch_id) ?? "Unknown batch"}
                    onChangeStatus={(status) => changeStatus.mutate({ id: liveClass.id, status })}
                    onJoin={() => handleJoin(liveClass)}
                    isJoining={joinLiveClass.isPending}
                    isPending={changeStatus.isPending}
                  />
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="py-6 text-center text-sm text-muted-foreground">
              No live classes scheduled yet.
            </p>
          )}
        </CardContent>
      </Card>

      {activeCall && (
        <VideoCallOverlay
          domain={activeCall.domain}
          room={activeCall.room}
          jwt={activeCall.jwt}
          title={activeCall.title}
          liveClassId={activeCall.liveClassId}
          onClose={() => setActiveCall(null)}
        />
      )}
    </div>
  );
}

function LiveClassRow({
  liveClass,
  batchName,
  onChangeStatus,
  onJoin,
  isJoining,
  isPending,
}: {
  liveClass: LiveClassPublic;
  batchName: string;
  onChangeStatus: (status: LiveClassStatus) => void;
  onJoin: () => void;
  isJoining: boolean;
  isPending: boolean;
}) {
  const canJoin = liveClass.status === "scheduled" || liveClass.status === "live";

  return (
    <TableRow>
      <TableCell>{batchName}</TableCell>
      <TableCell className="font-medium">{liveClass.title}</TableCell>
      <TableCell>{new Date(liveClass.scheduled_at).toLocaleString()}</TableCell>
      <TableCell>{liveClass.duration_minutes} min</TableCell>
      <TableCell>
        <LiveClassStatusBadge status={liveClass.status} />
      </TableCell>
      <TableCell>
        <div className="flex flex-wrap items-center gap-2">
          {canJoin && (
            <Button size="sm" variant="outline" disabled={isJoining} onClick={onJoin}>
              <Video className="h-4 w-4" />
              Join
            </Button>
          )}
          {NEXT_STATUS[liveClass.status].map((next) => (
            <Button
              key={next.status}
              size="sm"
              variant={next.status === "cancelled" ? "outline" : "default"}
              disabled={isPending}
              onClick={() => onChangeStatus(next.status)}
            >
              {next.label}
            </Button>
          ))}
          {liveClass.status === "completed" && liveClass.recording_url && (
            <Button size="sm" variant="ghost" asChild>
              <a href={liveClass.recording_url} target="_blank" rel="noreferrer">
                <ExternalLink className="h-4 w-4" />
                Recording
              </a>
            </Button>
          )}
        </div>
      </TableCell>
    </TableRow>
  );
}
