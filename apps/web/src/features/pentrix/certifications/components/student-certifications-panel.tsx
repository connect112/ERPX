import { Award, Plus } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useCertificationsForStudent,
  useIssueCertification,
} from "@/features/pentrix/certifications/api/certifications-hooks";

export function StudentCertificationsPanel({ studentId }: { studentId: string }) {
  const { data: certifications, isLoading } = useCertificationsForStudent(studentId);
  const issueCertification = useIssueCertification(studentId);

  const [formOpen, setFormOpen] = useState(false);
  const [trackName, setTrackName] = useState("");
  const [minimumPoints, setMinimumPoints] = useState("0");
  const [force, setForce] = useState(false);

  const onIssue = () => {
    if (!trackName) return;
    issueCertification.mutate(
      { trackName, minimumPoints: Number(minimumPoints), force },
      {
        onSuccess: () => {
          setFormOpen(false);
          setTrackName("");
          setMinimumPoints("0");
          setForce(false);
        },
      }
    );
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base">Pentrix Certifications</CardTitle>
        <Button size="sm" onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          Issue certification
        </Button>
      </CardHeader>
      <CardContent className="space-y-2">
        {isLoading && <Skeleton className="h-12 w-full" />}
        {!isLoading && (certifications?.length ?? 0) === 0 && (
          <p className="text-sm text-muted-foreground">No certifications issued yet.</p>
        )}
        {certifications?.map((cert) => (
          <div key={cert.id} className="flex items-center justify-between rounded-md border p-3">
            <div className="flex items-center gap-2">
              <Award className="h-4 w-4 text-primary" />
              <div>
                <p className="text-sm font-medium">{cert.track_name}</p>
                <p className="text-xs text-muted-foreground">{cert.certificate_number}</p>
              </div>
            </div>
            <div className="text-right">
              <p className="text-xs text-muted-foreground">{cert.points_at_issuance} pts</p>
              <p className="text-xs text-muted-foreground">
                {new Date(cert.issued_at).toLocaleDateString()}
              </p>
            </div>
          </div>
        ))}
      </CardContent>

      <Dialog open={formOpen} onOpenChange={setFormOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Issue certification</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="trackName">Track name</Label>
              <Input
                id="trackName"
                placeholder="e.g. Web Exploitation Specialist"
                value={trackName}
                onChange={(e) => setTrackName(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="minimumPoints">Minimum points required</Label>
              <Input
                id="minimumPoints"
                type="number"
                value={minimumPoints}
                onChange={(e) => setMinimumPoints(e.target.value)}
              />
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-input"
                checked={force}
                onChange={(e) => setForce(e.target.checked)}
              />
              Force issue (bypass minimum points requirement)
            </label>
            {issueCertification.isError && (
              <p className="text-sm text-destructive">
                {(issueCertification.error as { response?: { data?: { error?: { message?: string } } } })
                  ?.response?.data?.error?.message ?? "Something went wrong. Please try again."}
              </p>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setFormOpen(false)}>
              Cancel
            </Button>
            <Button onClick={onIssue} disabled={!trackName || issueCertification.isPending}>
              {issueCertification.isPending ? "Issuing..." : "Issue certification"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
