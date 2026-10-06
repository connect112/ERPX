import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useChooseProblem, useProblemStatements } from "@/features/hackathons/api/hackathons-hooks";

function errorText(error: unknown, fallback: string): string {
  return (
    (error as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error?.message ?? fallback
  );
}

/**
 * The challenges the organiser has published. A team that exists can pick one
 * (or change its pick); someone not on a team yet can still read them.
 */
export function ProblemStatementsCard({
  hackathonId,
  hasTeam,
  chosenId,
}: {
  hackathonId: string;
  hasTeam: boolean;
  chosenId: string | null;
}) {
  const { data: statements, isLoading } = useProblemStatements(hackathonId);
  const choose = useChooseProblem(hackathonId);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Problem statements</CardTitle>
        <CardDescription>
          {hasTeam
            ? "Read them all, then choose the one your team will work on. You can change it until the hackathon closes."
            : "Read them now; create or join a team to choose one."}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {isLoading ? (
          <p className="text-sm text-muted-foreground">Loading...</p>
        ) : statements && statements.length > 0 ? (
          statements.map((statement, index) => {
            const isChosen = statement.id === chosenId;
            return (
              <div
                key={statement.id}
                className={`rounded-md border p-4 ${isChosen ? "border-primary bg-primary/5" : ""}`}
              >
                <div className="flex items-start justify-between gap-3">
                  <h3 className="font-medium">
                    {index + 1}. {statement.title}
                  </h3>
                  {hasTeam &&
                    (isChosen ? (
                      <span className="shrink-0 text-sm font-medium text-primary">Your team's choice</span>
                    ) : (
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={choose.isPending}
                        onClick={() => choose.mutate(statement.id)}
                      >
                        Choose this
                      </Button>
                    ))}
                </div>
                <p className="mt-2 whitespace-pre-wrap text-sm text-muted-foreground">{statement.description}</p>
              </div>
            );
          })
        ) : (
          <p className="py-4 text-center text-sm text-muted-foreground">
            No problem statements have been published yet. Check back soon.
          </p>
        )}
        {choose.isError && <p className="text-sm text-destructive">{errorText(choose.error, "Could not save your choice.")}</p>}
      </CardContent>
    </Card>
  );
}
