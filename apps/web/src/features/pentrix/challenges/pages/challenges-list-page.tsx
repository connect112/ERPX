import { Plus } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useChallenges } from "@/features/pentrix/challenges/api/challenges-hooks";
import { ChallengeFormDialog } from "@/features/pentrix/challenges/pages/challenge-form-dialog";
import { labDifficultyLabels } from "@/features/pentrix/labs/schemas/lab-schemas";

export function ChallengesListPage() {
  const navigate = useNavigate();
  const [category, setCategory] = useState("");
  const { data: challenges, isLoading, isError } = useChallenges(category || undefined);
  const [formOpen, setFormOpen] = useState(false);

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Challenges</h1>
          <p className="mt-1 text-muted-foreground">
            CTF-style challenges students solve for points, standalone or tied to a lab.
          </p>
        </div>
        <Button onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          New Challenge
        </Button>
      </div>

      <Card>
        <CardContent className="space-y-4 p-6">
          <Input
            placeholder="Filter by category..."
            className="sm:w-64"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
          />

          {isLoading && <Skeleton className="h-32 w-full" />}
          {isError && (
            <p className="py-8 text-center text-sm text-destructive">Failed to load challenges.</p>
          )}
          {!isLoading && !isError && (challenges?.length ?? 0) === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No challenges yet. Create one to get started.
            </p>
          )}
          {!isLoading && !isError && (challenges?.length ?? 0) > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Title</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead>Difficulty</TableHead>
                  <TableHead>Points</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {challenges?.map((challenge) => (
                  <TableRow
                    key={challenge.id}
                    className="cursor-pointer"
                    onClick={() => navigate(`/pentrix/challenges/${challenge.id}`)}
                  >
                    <TableCell className="font-medium">{challenge.title}</TableCell>
                    <TableCell className="text-muted-foreground">{challenge.category}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {labDifficultyLabels[challenge.difficulty]}
                    </TableCell>
                    <TableCell className="text-muted-foreground">{challenge.points}</TableCell>
                    <TableCell>
                      <Badge variant={challenge.is_active ? "success" : "secondary"}>
                        {challenge.is_active ? "Active" : "Inactive"}
                      </Badge>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <ChallengeFormDialog open={formOpen} onOpenChange={setFormOpen} />
    </div>
  );
}
