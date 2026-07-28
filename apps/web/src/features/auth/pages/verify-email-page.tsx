import { useEffect } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { useVerifyEmailMutation } from "@/features/auth/api/auth-hooks";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export function VerifyEmailPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");
  const verifyMutation = useVerifyEmailMutation();

  useEffect(() => {
    if (token) {
      verifyMutation.mutate(token);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/30 px-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Email verification</CardTitle>
          <CardDescription>
            {!token && "No verification token was provided."}
            {token && verifyMutation.isPending && "Verifying your email address..."}
            {token && verifyMutation.isSuccess && "Your email has been verified. You can now sign in."}
            {token && verifyMutation.isError &&
              "This verification link is invalid or has expired. Request a new one from the sign-in page."}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Link to="/login">
            <Button className="w-full">Back to sign in</Button>
          </Link>
        </CardContent>
      </Card>
    </div>
  );
}
