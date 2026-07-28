import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
  useCancelRegistration,
  useCreateRegistration,
  useMarkAttendance,
  useWorkshopRegistrations,
} from "@/features/workshops/api/workshops-hooks";
import {
  type RegistrationFormValues,
  registrationFormSchema,
} from "@/features/workshops/schemas/workshop-schemas";

const statusVariant = {
  registered: "info",
  attended: "success",
  no_show: "warning",
  cancelled: "destructive",
} as const;

function RegisterAttendeeDialog({ workshopId }: { workshopId: string }) {
  const [open, setOpen] = useState(false);
  const createRegistration = useCreateRegistration(workshopId);
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<RegistrationFormValues>({ resolver: zodResolver(registrationFormSchema) });

  const onSubmit = (values: RegistrationFormValues) => {
    createRegistration.mutate(
      {
        contact_name: values.contactName,
        contact_email: values.contactEmail || undefined,
        contact_phone: values.contactPhone || undefined,
      },
      {
        onSuccess: () => {
          setOpen(false);
          reset();
        },
      }
    );
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm">Register attendee</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Register attendee</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="contactName">Name</Label>
            <Input id="contactName" {...register("contactName")} />
            {errors.contactName && (
              <p className="text-sm text-destructive">{errors.contactName.message}</p>
            )}
          </div>
          <div className="space-y-2">
            <Label htmlFor="contactEmail">Email</Label>
            <Input id="contactEmail" type="email" {...register("contactEmail")} />
            {errors.contactEmail && (
              <p className="text-sm text-destructive">{errors.contactEmail.message}</p>
            )}
          </div>
          <div className="space-y-2">
            <Label htmlFor="contactPhone">Phone</Label>
            <Input id="contactPhone" {...register("contactPhone")} />
          </div>
          {createRegistration.isError && (
            <p className="text-sm text-destructive">
              {(createRegistration.error as { response?: { data?: { error?: { message?: string } } } })
                ?.response?.data?.error?.message ?? "Something went wrong."}
            </p>
          )}
          <DialogFooter>
            <Button type="submit" disabled={createRegistration.isPending}>
              Register
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function RegistrationsPanel({ workshopId }: { workshopId: string }) {
  const { data: registrations, isLoading } = useWorkshopRegistrations(workshopId);
  const markAttendance = useMarkAttendance(workshopId);
  const cancelRegistration = useCancelRegistration(workshopId);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {registrations?.length ?? 0} registration{registrations?.length === 1 ? "" : "s"}
        </p>
        <RegisterAttendeeDialog workshopId={workshopId} />
      </div>

      {isLoading ? (
        <Skeleton className="h-32 w-full" />
      ) : registrations && registrations.length > 0 ? (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Contact</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Paid</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {registrations.map((registration) => (
              <TableRow key={registration.id}>
                <TableCell className="font-medium">{registration.contact_name}</TableCell>
                <TableCell className="text-muted-foreground">
                  {registration.contact_email || registration.contact_phone || "—"}
                </TableCell>
                <TableCell>
                  <Badge variant={statusVariant[registration.status]} className="capitalize">
                    {registration.status.replace("_", " ")}
                  </Badge>
                </TableCell>
                <TableCell>{registration.is_paid ? "Yes" : "No"}</TableCell>
                <TableCell className="text-right">
                  {registration.status === "registered" && (
                    <div className="flex justify-end gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() =>
                          markAttendance.mutate({ registrationId: registration.id, attended: true })
                        }
                      >
                        Mark attended
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => cancelRegistration.mutate(registration.id)}
                      >
                        Cancel
                      </Button>
                    </div>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      ) : (
        <p className="py-6 text-center text-sm text-muted-foreground">No registrations yet.</p>
      )}
    </div>
  );
}
