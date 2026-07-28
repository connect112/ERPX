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
import { type ClassroomType } from "@/features/classrooms/api/classrooms-api";
import { useCreateClassroom } from "@/features/classrooms/api/classrooms-hooks";

interface ClassroomFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function ClassroomFormDialog({ open, onOpenChange }: ClassroomFormDialogProps) {
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [classroomType, setClassroomType] = useState<ClassroomType>("physical");
  const [capacity, setCapacity] = useState("");
  const [locationOrLink, setLocationOrLink] = useState("");

  const createClassroom = useCreateClassroom();

  const reset = () => {
    setName("");
    setCode("");
    setClassroomType("physical");
    setCapacity("");
    setLocationOrLink("");
  };

  const handleSubmit = () => {
    createClassroom.mutate(
      {
        name,
        code,
        classroom_type: classroomType,
        capacity: capacity ? Number(capacity) : undefined,
        location: classroomType === "physical" ? locationOrLink || undefined : undefined,
        meeting_link: classroomType === "virtual" ? locationOrLink || undefined : undefined,
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
          <DialogTitle>New classroom</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="name">Name</Label>
              <Input id="name" value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="code">Code</Label>
              <Input id="code" value={code} onChange={(e) => setCode(e.target.value)} />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="classroomType">Type</Label>
            <Select value={classroomType} onValueChange={(v) => setClassroomType(v as ClassroomType)}>
              <SelectTrigger id="classroomType">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="physical">Physical</SelectItem>
                <SelectItem value="virtual">Virtual</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="capacity">Capacity</Label>
            <Input
              id="capacity"
              type="number"
              min={1}
              value={capacity}
              onChange={(e) => setCapacity(e.target.value)}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="locationOrLink">
              {classroomType === "physical" ? "Location" : "Meeting link"}
            </Label>
            <Input
              id="locationOrLink"
              value={locationOrLink}
              onChange={(e) => setLocationOrLink(e.target.value)}
              placeholder={classroomType === "physical" ? "Building A, Floor 2" : "https://meet..."}
            />
          </div>

          {createClassroom.isError && (
            <p className="text-sm text-destructive">
              {(createClassroom.error as { response?: { data?: { error?: { message?: string } } } })
                ?.response?.data?.error?.message ?? "Could not create classroom."}
            </p>
          )}
        </div>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            type="button"
            disabled={!name || !code || createClassroom.isPending}
            onClick={handleSubmit}
          >
            {createClassroom.isPending ? "Creating..." : "Create classroom"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
