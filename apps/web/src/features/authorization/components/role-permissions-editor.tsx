import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { usePermissions, useSetRolePermissions } from "@/features/authorization/api/authorization-hooks";
import type { PermissionPublic, RoleWithPermissions } from "@/features/authorization/api/authorization-api";

export function RolePermissionsEditor({ role }: { role: RoleWithPermissions }) {
  const { data: permissions, isLoading } = usePermissions();
  const setRolePermissions = useSetRolePermissions(role.id);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  useEffect(() => {
    setSelected(new Set(role.permissions.map((p) => p.code)));
  }, [role]);

  const grouped = new Map<string, PermissionPublic[]>();
  permissions?.forEach((p) => {
    const list = grouped.get(p.module) ?? [];
    list.push(p);
    grouped.set(p.module, list);
  });

  const toggle = (code: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(code)) next.delete(code);
      else next.add(code);
      return next;
    });
  };

  const hasChanges =
    selected.size !== role.permissions.length ||
    role.permissions.some((p) => !selected.has(p.code));

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base">Permissions</CardTitle>
        <Button
          size="sm"
          onClick={() => setRolePermissions.mutate(Array.from(selected))}
          disabled={!hasChanges || selected.size === 0 || setRolePermissions.isPending}
        >
          {setRolePermissions.isPending ? "Saving..." : "Save permissions"}
        </Button>
      </CardHeader>
      <CardContent className="space-y-4">
        {isLoading && <Skeleton className="h-48 w-full" />}
        {!isLoading &&
          Array.from(grouped.entries())
            .sort(([a], [b]) => a.localeCompare(b))
            .map(([module, modulePermissions]) => (
              <div key={module} className="space-y-2">
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  {module}
                </p>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                  {modulePermissions?.map((permission) => (
                    <label key={permission.id} className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        className="h-4 w-4 rounded border-input"
                        checked={selected.has(permission.code)}
                        onChange={() => toggle(permission.code)}
                      />
                      <span title={permission.description ?? undefined}>{permission.code}</span>
                    </label>
                  ))}
                </div>
              </div>
            ))}

        {setRolePermissions.isError && (
          <p className="text-sm text-destructive">
            {(setRolePermissions.error as { response?: { data?: { error?: { message?: string } } } })
              ?.response?.data?.error?.message ?? "Something went wrong. Please try again."}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
