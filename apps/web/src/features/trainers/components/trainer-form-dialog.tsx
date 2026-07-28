import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useEmployeesList } from "@/features/employees/api/employees-hooks";
import { useCreateTrainer } from "@/features/trainers/api/trainers-hooks";

interface TrainerFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function TrainerFormDialog({ open, onOpenChange }: TrainerFormDialogProps) {
  const [employeeId, setEmployeeId] = useState("");
  const [specializations, setSpecializations] = useState("");
  const [bio, setBio] = useState("");
  const [maxWeeklyHours, setMaxWeeklyHours] = useState("");

  const { data: employees } = useEmployeesList({ limit: 200 });
  const createTrainer = useCreateTrainer();

  const reset = () => {
    setEmployeeId("");
    setSpecializations("");
    setBio("");
    setMaxWeeklyHours("");
  };

  const handleSubmit = () => {
    createTrainer.mutate(
      {
        employee_id: employeeId,
        specializations: specializations || undefined,
        bio: bio || undefined,
        max_weekly_hours: maxWeeklyHours ? Number(maxWeeklyHours) : undefined,
      },
      {
        onSuccess: () => {
          reset();
          onOpenChange(false);
        },
      }
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New trainer profile</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="employeeId">Employee</Label>
            <Select value={employeeId} onValueChange={setEmployeeId}>
              <SelectTrigger id="employeeId">
                <SelectValue placeholder="Select an employee" />
              </SelectTrigger>
              <SelectContent>
                {employees?.items.map((e) => (
                  <SelectItem key={e.id} value={e.id}>
                    {e.full_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="specializations">Specializations</Label>
            <Input
              id="specializations"
              placeholder="e.g. Python, Web Security, Data Science"
              value={specializations}
              onChange={(e) => setSpecializations(e.target.value)}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="bio">Bio</Label>
            <Textarea id="bio" rows={3} value={bio} onChange={(e) => setBio(e.target.value)} />
          </div>

          <div className="space-y-2">
            <Label htmlFor="maxWeeklyHours">Max weekly hours</Label>
            <Input
              id="maxWeeklyHours"
              type="number"
              min={1}
              max={168}
              value={maxWeeklyHours}
              onChange={(e) => setMaxWeeklyHours(e.target.value)}
            />
          </div>

          {createTrainer.isError && (
            <p className="text-sm text-destructive">
              {(createTrainer.error as { response?: { data?: { error?: { message?: string } } } })
                ?.response?.data?.error?.message ?? "Could not create trainer profile."}
            </p>
          )}
        </div>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button type="button" disabled={!employeeId || createTrainer.isPending} onClick={handleSubmit}>
            {createTrainer.isPending ? "Creating..." : "Create trainer"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
