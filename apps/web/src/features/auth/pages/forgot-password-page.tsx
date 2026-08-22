import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";

import { useForgotPasswordMutation } from "@/features/auth/api/auth-hooks";
import {
  type ForgotPasswordFormValues,
  forgotPasswordSchema,
} from "@/features/auth/schemas/auth-schemas";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export function ForgotPasswordPage() {
  const mutation = useForgotPasswordMutation();
  const [submitted, setSubmitted] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ForgotPasswordFormValues>({ resolver: zodResolver(forgotPasswordSchema) });

  const onSubmit = (values: ForgotPasswordFormValues) => {
    mutation.mutate(values.email, { onSuccess: () => setSubmitted(true) });
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/30 px-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Reset your password</CardTitle>
          <CardDescription>
            {submitted
              ? "If an account with that email exists, we've sent a reset link."
              : "Enter your email and we'll send you a reset link."}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {submitted ? (
            <Link to="/login">
              <Button className="w-full">Back to sign in</Button>
            </Link>
          ) : (
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="email" required>Email</Label>
                <Input id="email" type="email" {...register("email")} />
                {errors.email && (
                  <p className="text-sm text-destructive">{errors.email.message}</p>
                )}
              </div>
              <Button type="submit" className="w-full" disabled={mutation.isPending}>
                {mutation.isPending ? "Sending..." : "Send reset link"}
              </Button>
              <p className="text-center text-sm">
                <Link to="/login" className="text-primary hover:underline">
                  Back to sign in
                </Link>
              </p>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
