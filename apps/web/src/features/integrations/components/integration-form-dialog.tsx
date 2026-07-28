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
import { useCreateIntegration } from "@/features/integrations/api/integrations-hooks";

interface IntegrationFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function IntegrationFormDialog({ open, onOpenChange }: IntegrationFormDialogProps) {
  const [provider, setProvider] = useState("");
  const [name, setName] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const createIntegration = useCreateIntegration();

  const reset = () => {
    setProvider("");
    setName("");
    setBaseUrl("");
    setApiKey("");
  };

  const handleSubmit = () => {
    createIntegration.mutate(
      { provider, name, base_url: baseUrl, api_key: apiKey || undefined, is_enabled: true },
      { onSuccess: () => { reset(); onOpenChange(false); } }
    );
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New integration</DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="provider">Provider</Label>
              <Input
                id="provider"
                placeholder="e.g. zoom, slack, custom"
                value={provider}
                onChange={(e) => setProvider(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="name">Name</Label>
              <Input id="name" value={name} onChange={(e) => setName(e.target.value)} />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="baseUrl">Base URL</Label>
            <Input
              id="baseUrl"
              placeholder="https://api.example.com"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="apiKey">API key (optional)</Label>
            <Input
              id="apiKey"
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
            />
          </div>

          {createIntegration.isError && (
            <p className="text-sm text-destructive">
              {(createIntegration.error as { response?: { data?: { error?: { message?: string } } } })
                ?.response?.data?.error?.message ?? "Could not create integration."}
            </p>
          )}
        </div>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            type="button"
            disabled={!provider || !name || !baseUrl || createIntegration.isPending}
            onClick={handleSubmit}
          >
            {createIntegration.isPending ? "Creating..." : "Create integration"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
