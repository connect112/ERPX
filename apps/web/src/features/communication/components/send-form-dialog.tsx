import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { Controller, useForm } from "react-hook-form";

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
import { useSendCommunication } from "@/features/communication/api/communication-hooks";
import {
  type SendFormValues,
  channelLabels,
  channelValues,
  sendFormSchema,
} from "@/features/communication/schemas/communication-schemas";

interface SendFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const emptyValues: SendFormValues = {
  channel: "email",
  recipient: "",
  subject: "",
  body: "",
};

export function SendFormDialog({ open, onOpenChange }: SendFormDialogProps) {
  const sendCommunication = useSendCommunication();

  const {
    register,
    control,
    handleSubmit,
    watch,
    reset,
    formState: { errors },
  } = useForm<SendFormValues>({
    resolver: zodResolver(sendFormSchema),
    defaultValues: emptyValues,
  });

  const channel = watch("channel");

  useEffect(() => {
    if (open) reset(emptyValues);
  }, [open, reset]);

  const onSubmit = (values: SendFormValues) => {
    sendCommunication.mutate(
      {
        channel: values.channel,
        recipient: values.recipient,
        subject: values.subject || undefined,
        body: values.body,
      },
      { onSuccess: () => onOpenChange(false) }
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>Send communication</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="channel">Channel</Label>
              <Controller
                control={control}
                name="channel"
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger id="channel">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {channelValues.map((c) => (
                        <SelectItem key={c} value={c}>
                          {channelLabels[c]}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="recipient">
                {channel === "email" ? "Recipient email" : "Recipient phone"}
              </Label>
              <Input
                id="recipient"
                placeholder={channel === "email" ? "student@example.com" : "+91 98765 43210"}
                {...register("recipient")}
              />
              {errors.recipient && (
                <p className="text-sm text-destructive">{errors.recipient.message}</p>
              )}
            </div>
          </div>

          {channel === "email" && (
            <div className="space-y-2">
              <Label htmlFor="subject">Subject</Label>
              <Input id="subject" {...register("subject")} />
              {errors.subject && <p className="text-sm text-destructive">{errors.subject.message}</p>}
            </div>
          )}

          <div className="space-y-2">
            <Label htmlFor="body">Message</Label>
            <Textarea id="body" rows={4} {...register("body")} />
            {errors.body && <p className="text-sm text-destructive">{errors.body.message}</p>}
          </div>

          {sendCommunication.isError && (
            <p className="text-sm text-destructive">
              {(sendCommunication.error as { response?: { data?: { error?: { message?: string } } } })
                ?.response?.data?.error?.message ?? "Could not send communication."}
            </p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={sendCommunication.isPending}>
              {sendCommunication.isPending ? "Sending..." : "Send"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
