import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useCheckIn, useCheckOut } from "@/features/attendance/api/attendance-hooks";
import { useEmployeesList } from "@/features/employees/api/employees-hooks";

interface CheckInOutDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  mode: "check-in" | "check-out";
}

export function CheckInOutDialog({ open, onOpenChange, mode }: CheckInOutDialogProps) {
  const { data: employees } = useEmployeesList({ limit: 200 });
  const checkIn = useCheckIn();
  const checkOut = useCheckOut();
  const [employeeId, setEmployeeId] = useState("");

  useEffect(() => {
    if (open) setEmployeeId("");
  }, [open]);

  const mutation = mode === "check-in" ? checkIn : checkOut;

  const handleSubmit = () => {
    if (!employeeId) return;
    if (mode === "check-in") {
      checkIn.mutate({ employee_id: employeeId }, { onSuccess: () => onOpenChange(false) });
    } else {
      checkOut.mutate({ employee_id: employeeId }, { onSuccess: () => onOpenChange(false) });
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{mode === "check-in" ? "Check in" : "Check out"}</DialogTitle>
        </DialogHeader>
        <div className="space-y-2">
          <Label htmlFor="employeeId">Employee</Label>
          <Select value={employeeId || undefined} onValueChange={setEmployeeId}>
            <SelectTrigger id="employeeId">
              <SelectValue placeholder="Select employee" />
            </SelectTrigger>
            <SelectContent>
              {employees?.items.map((e) => (
                <SelectItem key={e.id} value={e.id}>
                  {e.full_name} ({e.employee_code})
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {mutation.isError && (
          <p className="text-sm text-destructive">
            {(mutation.error as { response?: { data?: { error?: { message?: string } } } })
              ?.response?.data?.error?.message ?? "Something went wrong. Please try again."}
          </p>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={!employeeId || mutation.isPending}>
            {mutation.isPending ? "Saving..." : mode === "check-in" ? "Check in" : "Check out"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
