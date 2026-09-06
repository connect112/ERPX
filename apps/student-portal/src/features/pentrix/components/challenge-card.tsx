import { CheckCircle2, Flag } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { ChallengePublic } from "@/features/pentrix/api/pentrix-api";

const difficultyVariant: Record<ChallengePublic["difficulty"], "success" | "info" | "warning" | "destructive"> = {
  easy: "success",
  medium: "info",
  hard: "warning",
  insane: "destructive",
};

interface ChallengeCardProps {
  challenge: ChallengePublic;
  solved: boolean;
  onSubmit: (flagValue: string) => Promise<{ correct: boolean; already_solved: boolean }>;
}

export function ChallengeCard({ challenge, solved, onSubmit }: ChallengeCardProps) {
  const [open, setOpen] = useState(false);
  const [flagValue, setFlagValue] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async () => {
    if (!flagValue.trim()) return;
    setSubmitting(true);
    setFeedback(null);
    try {
      const result = await onSubmit(flagValue.trim());
      if (result.correct) {
        setFeedback("correct");
        setTimeout(() => setOpen(false), 1200);
      } else {
        setFeedback("incorrect");
      }
    } catch {
      setFeedback("error");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="flex items-center gap-2 text-base">
            {challenge.title}
            {solved && <CheckCircle2 className="h-4 w-4 text-emerald-500" />}
          </CardTitle>
          <Badge variant={difficultyVariant[challenge.difficulty]}>{challenge.difficulty}</Badge>
        </div>
        <CardDescription>{challenge.category}</CardDescription>
      </CardHeader>
      <CardContent className="text-sm text-muted-foreground">{challenge.description}</CardContent>
      <CardFooter className="flex items-center justify-between">
        <span className="text-sm font-medium">{challenge.points} pts</span>
        <Dialog
          open={open}
          onOpenChange={(next) => {
            setOpen(next);
            if (!next) {
              setFlagValue("");
              setFeedback(null);
            }
          }}
        >
          <DialogTrigger asChild>
            <Button size="sm" variant={solved ? "outline" : "default"}>
              <Flag className="h-4 w-4" /> {solved ? "Solved" : "Submit flag"}
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{challenge.title}</DialogTitle>
              <DialogDescription>Enter the flag you found for this challenge.</DialogDescription>
            </DialogHeader>
            <div className="space-y-2">
              <Label htmlFor={`flag-${challenge.id}`}>Flag</Label>
              <Input
                id={`flag-${challenge.id}`}
                placeholder="PENTRIX{...}"
                value={flagValue}
                onChange={(e) => setFlagValue(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
              />
              {feedback === "correct" && (
                <p className="text-sm text-emerald-600 dark:text-emerald-400">Correct — solved!</p>
              )}
              {feedback === "incorrect" && (
                <p className="text-sm text-destructive">Incorrect flag. Try again.</p>
              )}
              {feedback === "error" && (
                <p className="text-sm text-destructive">Something went wrong. Try again.</p>
              )}
            </div>
            <DialogFooter>
              <Button onClick={handleSubmit} disabled={submitting || !flagValue.trim()}>
                {submitting ? "Checking…" : "Submit"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </CardFooter>
    </Card>
  );
}
