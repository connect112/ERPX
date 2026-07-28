import { Plug, Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  useDeleteIntegration,
  useIntegrationsList,
  useTestIntegration,
} from "@/features/integrations/api/integrations-hooks";
import { IntegrationFormDialog } from "@/features/integrations/components/integration-form-dialog";

export function IntegrationsPage() {
  const [formOpen, setFormOpen] = useState(false);
  const { data, isLoading, isError } = useIntegrationsList({ limit: 100 });
  const testIntegration = useTestIntegration();
  const deleteIntegration = useDeleteIntegration();

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Integrations</h1>
          <p className="mt-1 text-muted-foreground">
            Third-party service connections. Testing performs a real HTTP request to the
            configured base URL. Administrator-only.
          </p>
        </div>
        <Button onClick={() => setFormOpen(true)}>
          <Plus className="h-4 w-4" />
          New Integration
        </Button>
      </div>

      <Card>
        <CardContent className="space-y-4 p-6">
          {isLoading && (
            <div className="space-y-2">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          )}

          {isError && (
            <p className="py-8 text-center text-sm text-destructive">
              Failed to load integrations. Please try again.
            </p>
          )}

          {!isLoading && !isError && (data?.items.length ?? 0) === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No integrations configured yet.
            </p>
          )}

          {!isLoading && !isError && (data?.items.length ?? 0) > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead>Provider</TableHead>
                  <TableHead>API key</TableHead>
                  <TableHead>Last test</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {data?.items.map((integration) => (
                  <TableRow key={integration.id}>
                    <TableCell className="font-medium">{integration.name}</TableCell>
                    <TableCell className="text-muted-foreground">{integration.provider}</TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      {integration.masked_api_key || "—"}
                    </TableCell>
                    <TableCell>
                      {integration.last_test_status ? (
                        <div>
                          <Badge
                            variant={integration.last_test_status === "success" ? "success" : "destructive"}
                          >
                            {integration.last_test_status === "success" ? "Reachable" : "Unreachable"}
                          </Badge>
                          <p className="mt-1 max-w-xs truncate text-xs text-muted-foreground">
                            {integration.last_test_message}
                          </p>
                        </div>
                      ) : (
                        <span className="text-sm text-muted-foreground">Not tested</span>
                      )}
                    </TableCell>
                    <TableCell className="flex justify-end gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => testIntegration.mutate(integration.id)}
                        disabled={testIntegration.isPending}
                        aria-label={`Test ${integration.name}`}
                      >
                        <Plug className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => deleteIntegration.mutate(integration.id)}
                        aria-label={`Delete ${integration.name}`}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <IntegrationFormDialog open={formOpen} onOpenChange={setFormOpen} />
    </div>
  );
}
