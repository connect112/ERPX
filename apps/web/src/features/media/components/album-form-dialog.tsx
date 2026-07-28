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
import { Textarea } from "@/components/ui/textarea";
import { useCreateAlbum } from "@/features/media/api/media-hooks";

interface AlbumFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function AlbumFormDialog({ open, onOpenChange }: AlbumFormDialogProps) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const createAlbum = useCreateAlbum();

  const reset = () => {
    setTitle("");
    setDescription("");
  };

  const handleSubmit = () => {
    createAlbum.mutate(
      { title, description: description || undefined },
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
          <DialogTitle>New album</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="title">Title</Label>
            <Input id="title" value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="description">Description</Label>
            <Textarea
              id="description"
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>

          {createAlbum.isError && (
            <p className="text-sm text-destructive">
              {(createAlbum.error as { response?: { data?: { error?: { message?: string } } } })
                ?.response?.data?.error?.message ?? "Could not create album."}
            </p>
          )}
        </div>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            type="button"
            disabled={!title || createAlbum.isPending}
            onClick={handleSubmit}
          >
            {createAlbum.isPending ? "Creating..." : "Create album"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
