import { zodResolver } from "@hookform/resolvers/zod";
import { Controller, useForm } from "react-hook-form";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { useCompleteRegistrationMutation } from "@/features/auth/api/auth-hooks";
import {
  type CompleteRegistrationFormValues,
  completeRegistrationSchema,
  genderLabels,
  genderValues,
} from "@/features/auth/schemas/auth-schemas";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

/**
 * Landing page for an invited employee's link (see
 * EmployeeService.invite_employee / complete_registration) — the one-time
 * combined step where they set their own password AND fill in the
 * personal-detail fields the admin's "New employee" form deliberately
 * never collects (see modules/employees/schemas.py's
 * EmployeeCreateRequest docstring). Modeled directly on
 * ResetPasswordPage, which shares the same underlying token machinery
 * but only asks for a password — this asks for the rest of the profile
 * too, in one submit, since the alternative (set password, then get
 * dropped into a mostly-empty portal to fill it in some other time)
 * is worse UX and worse data-completeness than doing it all up front
 * while they're already on this page.
 */
export function CompleteRegistrationPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");
  const navigate = useNavigate();
  const completeMutation = useCompleteRegistrationMutation();

  const {
    register,
    control,
    handleSubmit,
    formState: { errors },
  } = useForm<CompleteRegistrationFormValues>({ resolver: zodResolver(completeRegistrationSchema) });

  const onSubmit = (values: CompleteRegistrationFormValues) => {
    if (!token) return;
    completeMutation.mutate(
      {
        token,
        new_password: values.newPassword,
        phone: values.phone,
        gender: values.gender,
        date_of_birth: values.dateOfBirth,
        address_line1: values.addressLine1,
        city: values.city,
        state: values.state,
        country: values.country,
        postal_code: values.postalCode,
        emergency_contact_name: values.emergencyContactName,
        emergency_contact_phone: values.emergencyContactPhone,
      },
      { onSuccess: () => navigate("/login", { replace: true }) }
    );
  };

  if (!token) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-muted/30 px-4">
        <Card className="w-full max-w-sm">
          <CardHeader>
            <CardTitle>Invalid link</CardTitle>
            <CardDescription>
              This registration link is missing its token. Please use the link from your invite
              email again, or ask your admin to resend it.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Link to="/login" className="text-sm text-primary underline-offset-4 hover:underline">
              Back to sign in
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/30 px-4 py-8">
      <Card className="w-full max-w-xl">
        <CardHeader>
          <CardTitle>Complete your registration</CardTitle>
          <CardDescription>
            Set your password and fill in your details to activate your ERPX account.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {completeMutation.isSuccess ? (
            <p className="text-sm text-muted-foreground">
              You're all set. Redirecting to sign in…
            </p>
          ) : (
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
              <div className="space-y-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Password
                </p>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="newPassword">New password</Label>
                    <Input id="newPassword" type="password" {...register("newPassword")} />
                    {errors.newPassword && (
                      <p className="text-sm text-destructive">{errors.newPassword.message}</p>
                    )}
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="confirmPassword">Confirm password</Label>
                    <Input id="confirmPassword" type="password" {...register("confirmPassword")} />
                    {errors.confirmPassword && (
                      <p className="text-sm text-destructive">{errors.confirmPassword.message}</p>
                    )}
                  </div>
                </div>
              </div>

              <div className="space-y-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Personal details
                </p>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="phone">Phone</Label>
                    <Input id="phone" {...register("phone")} />
                    {errors.phone && <p className="text-sm text-destructive">{errors.phone.message}</p>}
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="gender">Gender</Label>
                    <Controller
                      control={control}
                      name="gender"
                      render={({ field }) => (
                        <Select value={field.value || undefined} onValueChange={field.onChange}>
                          <SelectTrigger id="gender">
                            <SelectValue placeholder="Select gender" />
                          </SelectTrigger>
                          <SelectContent>
                            {genderValues.map((g) => (
                              <SelectItem key={g} value={g}>
                                {genderLabels[g]}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      )}
                    />
                    {errors.gender && (
                      <p className="text-sm text-destructive">{errors.gender.message}</p>
                    )}
                  </div>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="dateOfBirth">Date of birth</Label>
                  <Input id="dateOfBirth" type="date" {...register("dateOfBirth")} />
                  {errors.dateOfBirth && (
                    <p className="text-sm text-destructive">{errors.dateOfBirth.message}</p>
                  )}
                </div>
              </div>

              <div className="space-y-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Address
                </p>
                <div className="space-y-2">
                  <Label htmlFor="addressLine1">Address line 1</Label>
                  <Input id="addressLine1" {...register("addressLine1")} />
                  {errors.addressLine1 && (
                    <p className="text-sm text-destructive">{errors.addressLine1.message}</p>
                  )}
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="city">City</Label>
                    <Input id="city" {...register("city")} />
                    {errors.city && <p className="text-sm text-destructive">{errors.city.message}</p>}
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="state">State</Label>
                    <Input id="state" {...register("state")} />
                    {errors.state && <p className="text-sm text-destructive">{errors.state.message}</p>}
                  </div>
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="country">Country</Label>
                    <Input id="country" {...register("country")} />
                    {errors.country && (
                      <p className="text-sm text-destructive">{errors.country.message}</p>
                    )}
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="postalCode">Postal code</Label>
                    <Input id="postalCode" {...register("postalCode")} />
                    {errors.postalCode && (
                      <p className="text-sm text-destructive">{errors.postalCode.message}</p>
                    )}
                  </div>
                </div>
              </div>

              <div className="space-y-3">
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Emergency contact
                </p>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="emergencyContactName">Contact name</Label>
                    <Input id="emergencyContactName" {...register("emergencyContactName")} />
                    {errors.emergencyContactName && (
                      <p className="text-sm text-destructive">
                        {errors.emergencyContactName.message}
                      </p>
                    )}
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="emergencyContactPhone">Contact phone</Label>
                    <Input id="emergencyContactPhone" {...register("emergencyContactPhone")} />
                    {errors.emergencyContactPhone && (
                      <p className="text-sm text-destructive">
                        {errors.emergencyContactPhone.message}
                      </p>
                    )}
                  </div>
                </div>
              </div>

              {completeMutation.isError && (
                <p className="text-sm text-destructive">
                  {(completeMutation.error as { response?: { data?: { error?: { message?: string } } } })
                    ?.response?.data?.error?.message ??
                    "This link may have expired. Please ask your admin to resend it."}
                </p>
              )}

              <Button type="submit" className="w-full" disabled={completeMutation.isPending}>
                {completeMutation.isPending ? "Setting up your account..." : "Complete registration"}
              </Button>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
