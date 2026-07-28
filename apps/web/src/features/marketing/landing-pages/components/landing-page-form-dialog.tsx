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
import { useCampaignsList } from "@/features/marketing/campaigns/api/campaigns-hooks";
import type { LandingPagePublic } from "@/features/marketing/landing-pages/api/landing-pages-api";
import {
  useCreateLandingPage,
  useUpdateLandingPage,
} from "@/features/marketing/landing-pages/api/landing-pages-hooks";
import {
  type LandingPageFormValues,
  landingPageFormSchema,
} from "@/features/marketing/landing-pages/schemas/landing-page-schemas";

interface LandingPageFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  page?: LandingPagePublic;
}

const emptyValues: LandingPageFormValues = {
  slug: "",
  title: "",
  campaignId: "",
  metaDescription: "",
  content: "",
};

export function LandingPageFormDialog({ open, onOpenChange, page }: LandingPageFormDialogProps) {
  const isEditing = !!page;
  const createPage = useCreateLandingPage();
  const updatePage = useUpdateLandingPage(page?.id ?? "");
  const { data: campaigns } = useCampaignsList({ limit: 200 });

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<LandingPageFormValues>({
    resolver: zodResolver(landingPageFormSchema),
    defaultValues: emptyValues,
  });

  useEffect(() => {
    if (open) {
      reset(
        page
          ? {
              slug: page.slug,
              title: page.title,
              campaignId: page.campaign_id ?? "",
              metaDescription: page.meta_description ?? "",
              content: page.content,
            }
          : emptyValues
      );
    }
  }, [open, page, reset]);

  const mutation = isEditing ? updatePage : createPage;

  const onSubmit = (values: LandingPageFormValues) => {
    const shared = {
      title: values.title,
      campaign_id: values.campaignId || undefined,
      meta_description: values.metaDescription || undefined,
      content: values.content,
    };

    if (isEditing) {
      updatePage.mutate(shared, { onSuccess: () => onOpenChange(false) });
    } else {
      createPage.mutate({ ...shared, slug: values.slug }, { onSuccess: () => onOpenChange(false) });
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>{isEditing ? "Edit landing page" : "New landing page"}</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="slug">Slug</Label>
              <Input id="slug" disabled={isEditing} placeholder="e.g. summer-sale" {...register("slug")} />
              {errors.slug && <p className="text-sm text-destructive">{errors.slug.message}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="title">Title</Label>
              <Input id="title" {...register("title")} />
              {errors.title && <p className="text-sm text-destructive">{errors.title.message}</p>}
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="campaignId">Campaign</Label>
            <Controller
              control={control}
              name="campaignId"
              render={({ field }) => (
                <Select value={field.value || undefined} onValueChange={field.onChange}>
                  <SelectTrigger id="campaignId">
                    <SelectValue placeholder="Select campaign" />
                  </SelectTrigger>
                  <SelectContent>
                    {campaigns?.items.map((c) => (
                      <SelectItem key={c.id} value={c.id}>
                        {c.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="metaDescription">Meta description</Label>
            <Textarea id="metaDescription" rows={2} {...register("metaDescription")} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="content">Content</Label>
            <Textarea id="content" rows={6} {...register("content")} />
            {errors.content && <p className="text-sm text-destructive">{errors.content.message}</p>}
          </div>

          {mutation.isError && (
            <p className="text-sm text-destructive">
              {(mutation.error as { response?: { data?: { error?: { message?: string } } } })
                ?.response?.data?.error?.message ?? "Something went wrong. Please try again."}
            </p>
          )}

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? "Saving..." : isEditing ? "Save changes" : "Create landing page"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
