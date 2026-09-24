import { useEffect } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useLogout } from "@/features/auth/api/auth-hooks";
import { PORTAL_LABELS, PORTAL_URLS, type PortalKind } from "@/features/auth/lib/portal-resolution";

/**
 * Rendered by ProtectedRoute in place of the app when useHomePortal()
 * resolves to somewhere other than this portal — see
 * portal-resolution.ts's resolveHomePortal for why this can happen (any
 * ERPX login works on any of the 4 subdomains, but isn't necessarily *for*
 * this one). Auto-redirects to the account's real portal: the shared
 * `erpx_sso` cookie set at login (modules/authentication/routes.py) means
 * that portal's own use-sso-bootstrap.ts will pick the session up on its
 * own — no login form, no second password entry. The button/message stay
 * as a manual fallback for the rare case the redirect doesn't fire.
 */
export function WrongPortalScreen({ target }: { target: PortalKind | null }) {
  const logout = useLogout();

  useEffect(() => {
    if (!target) return;
    window.location.replace(PORTAL_URLS[target]);
  }, [target]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/30 px-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>{target ? "Redirecting…" : "Wrong portal"}</CardTitle>
          <CardDescription>
            {target
              ? `This account doesn't have access to the Student Portal — taking you to the ${PORTAL_LABELS[target]}.`
              : "This account isn't set up on any ERPX portal yet. Contact your admin."}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {target && (
            <Button
              className="w-full"
              onClick={() => {
                window.location.href = PORTAL_URLS[target];
              }}
            >
              Go to {PORTAL_LABELS[target]} now
            </Button>
          )}
          <Button variant="outline" className="w-full" onClick={() => logout()}>
            Sign out
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
