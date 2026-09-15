import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useLogout } from "@/features/auth/api/auth-hooks";
import { PORTAL_LABELS, PORTAL_URLS, type PortalKind } from "@/features/auth/lib/portal-resolution";

/**
 * Rendered by ProtectedRoute in place of the app when useHomePortal()
 * resolves to somewhere other than this portal — see
 * portal-resolution.ts's resolveHomePortal for why this can happen (any
 * ERPX login works on any of the 4 subdomains, but isn't necessarily
 * *for* this one). No auto-redirect: a login this account doesn't
 * actually belong on will already have gotten this person a valid
 * session token for the wrong portal, so we ask before sending them
 * elsewhere rather than silently bouncing.
 */
export function WrongPortalScreen({ target }: { target: PortalKind | null }) {
  const logout = useLogout();

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/30 px-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Wrong portal</CardTitle>
          <CardDescription>
            {target
              ? `This account doesn't have access to the Admin Panel — your portal is the ${PORTAL_LABELS[target]}.`
              : "This account isn't set up on any ERPX portal yet. Contact your admin."}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {target && (
            <Button
              className="w-full"
              onClick={() => {
                window.location.href = `${PORTAL_URLS[target]}/login`;
              }}
            >
              Go to {PORTAL_LABELS[target]}
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
