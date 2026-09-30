import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useLogout } from "@/features/auth/api/auth-hooks";
import { PORTAL_LABELS, PORTAL_URLS, type PortalKind } from "@/features/auth/lib/portal-resolution";

/**
 * Rendered by ProtectedRoute in place of the app when useHomePortal()
 * resolves to somewhere other than this portal — see
 * portal-resolution.ts's resolveHomePortal for why this can happen (any
 * ERPX login works on any of the 4 subdomains, but isn't necessarily *for*
 * this one).
 *
 * Deliberately does NOT auto-redirect (it used to, via
 * `window.location.replace` in a mount effect). That auto-navigation is
 * what caused a real, disruptive bug: an account with valid sessions on
 * two subdomains at once had each one's background token refresh racing
 * the other's, since every refresh (on either origin) rewrites the same
 * shared `erpx_sso` cookie — the loser looked like token reuse/theft to
 * the backend, which revoked every session for the account as a
 * precaution, repeatedly, producing an endless visible bounce between
 * subdomains. The fix is to never auto-navigate between them at all;
 * the button below is a deliberate, one-time, user-initiated hop
 * instead of an automatic one that can race.
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
              ? `This account doesn't have access to the Trainer Portal — head to the ${PORTAL_LABELS[target]} instead.`
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
