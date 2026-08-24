import { ExternalLink, Loader2, Square } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import type { LabInstancePublic, LabPublic } from "@/features/pentrix/api/pentrix-api";

const difficultyVariant: Record<LabPublic["difficulty"], "success" | "info" | "warning" | "destructive"> = {
  easy: "success",
  medium: "info",
  hard: "warning",
  insane: "destructive",
};

interface LabCardProps {
  lab: LabPublic;
  activeInstance: LabInstancePublic | undefined;
  onLaunch: () => void;
  onStop: (instanceId: string) => void;
  isLaunching: boolean;
  isStopping: boolean;
}

export function LabCard({ lab, activeInstance, onLaunch, onStop, isLaunching, isStopping }: LabCardProps) {
  const isRunning = activeInstance?.status === "running";
  const isProvisioning = activeInstance?.status === "provisioning";

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-base">{lab.title}</CardTitle>
          <Badge variant={difficultyVariant[lab.difficulty]}>{lab.difficulty}</Badge>
        </div>
        <CardDescription>{lab.description ?? lab.category}</CardDescription>
      </CardHeader>
      <CardContent className="text-sm text-muted-foreground">
        {lab.points} pts · {lab.default_duration_minutes} min session
      </CardContent>
      <CardFooter className="flex flex-col items-stretch gap-2">
        {isProvisioning ? (
          <Button disabled className="w-full">
            <Loader2 className="h-4 w-4 animate-spin" /> Provisioning…
          </Button>
        ) : isRunning ? (
          <>
            {activeInstance?.access_endpoint && (
              <Button asChild className="w-full">
                <a href={activeInstance.access_endpoint} target="_blank" rel="noreferrer">
                  <ExternalLink className="h-4 w-4" /> Open environment
                </a>
              </Button>
            )}
            <Button
              variant="outline"
              className="w-full"
              disabled={isStopping}
              onClick={() => activeInstance && onStop(activeInstance.id)}
            >
              <Square className="h-4 w-4" /> {isStopping ? "Stopping…" : "Stop instance"}
            </Button>
          </>
        ) : (
          <Button className="w-full" onClick={onLaunch} disabled={isLaunching || !lab.is_active}>
            {isLaunching ? "Launching…" : lab.is_active ? "Launch lab" : "Unavailable"}
          </Button>
        )}
      </CardFooter>
    </Card>
  );
}
