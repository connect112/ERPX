import { ArrowLeft, Trash2 } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useRolesList } from "@/features/authorization/api/authorization-hooks";
import {
  useDeleteWorkflow,
  useUpdateWorkflow,
  useWorkflow,
} from "@/features/workflow/api/workflow-hooks";

export function WorkflowDetailPage() {
  const { workflowId } = useParams<{ workflowId: string }>();
  const navigate = useNavigate();
  const { data: workflow, isLoading } = useWorkflow(workflowId);
  const { data: roles } = useRolesList();
  const updateWorkflow = useUpdateWorkflow(workflowId ?? "");
  const deleteWorkflow = useDeleteWorkflow();

  const handleDelete = () => {
    if (!workflowId) return;
    deleteWorkflow.mutate(workflowId, { onSuccess: () => navigate("/workflow/workflows") });
  };

  if (isLoading || !workflow) {
    return (
      <div className="space-y-4 p-8">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const roleName = (roleId: string) => roles?.find((r) => r.id === roleId)?.name ?? roleId;

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => navigate("/workflow/workflows")}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">{workflow.name}</h1>
            <div className="mt-1 flex items-center gap-2">
              <span className="font-mono text-xs text-muted-foreground">{workflow.entity_type}</span>
              <Badge variant={workflow.is_active ? "success" : "secondary"}>
                {workflow.is_active ? "Active" : "Inactive"}
              </Badge>
            </div>
          </div>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => updateWorkflow.mutate({ is_active: !workflow.is_active })}
            disabled={updateWorkflow.isPending}
          >
            {workflow.is_active ? "Deactivate" : "Activate"}
          </Button>
          <Button variant="outline" onClick={handleDelete} disabled={deleteWorkflow.isPending}>
            <Trash2 className="h-4 w-4" />
            Delete
          </Button>
        </div>
      </div>

      {workflow.description && <p className="text-muted-foreground">{workflow.description}</p>}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Approval steps</CardTitle>
        </CardHeader>
        <CardContent>
          <ol className="space-y-3">
            {workflow.steps.map((step) => (
              <li key={step.id} className="flex items-center gap-3 border-b pb-3 last:border-0">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-muted text-sm font-medium">
                  {step.step_order}
                </span>
                <div>
                  <p className="text-sm font-medium">{step.name || `Step ${step.step_order}`}</p>
                  <p className="text-sm text-muted-foreground">Approver: {roleName(step.approver_role_id)}</p>
                </div>
              </li>
            ))}
          </ol>
        </CardContent>
      </Card>
    </div>
  );
}
