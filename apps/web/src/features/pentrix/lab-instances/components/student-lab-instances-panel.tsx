import { Play, Square } from "lucide-react";
import { useState } from "react";

import { Badge, type BadgeProps } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useLabs } from "@/features/pentrix/labs/api/labs-hooks";
import {
  useLabInstancesForStudent,
  useLaunchLab,
  useStopLabInstance,
} from "@/features/pentrix/lab-instances/api/lab-instances-hooks";
import type { LabInstanceStatus } from "@/features/pentrix/lab-instances/api/lab-instances-api";

const statusVariant: Record<LabInstanceStatus, BadgeProps["variant"]> = {
  provisioning: "info",
  running: "success",
  stopped: "secondary",
  expired: "warning",
  failed: "destructive",
};

export function StudentLabInstancesPanel({ studentId }: { studentId: string }) {
  const { data: instances, isLoading } = useLabInstancesForStudent(studentId);
  const { data: labs } = useLabs();
  const launchLab = useLaunchLab(studentId);
  const stopInstance = useStopLabInstance(studentId);
  const [selectedLab, setSelectedLab] = useState("");

  const labTitle = (id: string) => labs?.find((l) => l.id === id)?.title ?? id;

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base">Lab Instances</CardTitle>
        <div className="flex items-center gap-2">
          <Select value={selectedLab || undefined} onValueChange={setSelectedLab}>
            <SelectTrigger className="h-8 w-48 text-xs">
              <SelectValue placeholder="Select a lab" />
            </SelectTrigger>
            <SelectContent>
              {labs?.filter((l) => l.is_active).map((l) => (
                <SelectItem key={l.id} value={l.id}>
                  {l.title}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button
            size="sm"
            disabled={!selectedLab || launchLab.isPending}
            onClick={() => launchLab.mutate(selectedLab, { onSuccess: () => setSelectedLab("") })}
          >
            <Play className="h-3 w-3" />
            Launch
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-2">
        {isLoading && <Skeleton className="h-16 w-full" />}
        {!isLoading && (instances?.length ?? 0) === 0 && (
          <p className="text-sm text-muted-foreground">No lab instances launched yet.</p>
        )}
        {instances?.map((instance) => (
          <div key={instance.id} className="flex items-center justify-between rounded-md border p-3">
            <div>
              <div className="flex items-center gap-2">
                <p className="text-sm font-medium">{labTitle(instance.lab_id)}</p>
                <Badge variant={statusVariant[instance.status]}>{instance.status}</Badge>
              </div>
              <p className="mt-0.5 text-xs text-muted-foreground">
                Started {new Date(instance.started_at).toLocaleString()} · Expires{" "}
                {new Date(instance.expires_at).toLocaleString()}
              </p>
              {instance.access_endpoint && (
                <a
                  href={instance.access_endpoint}
                  target="_blank"
                  rel="noreferrer"
                  className="text-xs text-primary hover:underline"
                >
                  {instance.access_endpoint}
                </a>
              )}
            </div>
            {(instance.status === "running" || instance.status === "provisioning") && (
              <Button
                variant="ghost"
                size="sm"
                disabled={stopInstance.isPending}
                onClick={() => stopInstance.mutate(instance.id)}
              >
                <Square className="h-3 w-3" />
                Stop
              </Button>
            )}
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
