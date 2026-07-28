import { ArrowLeft, Pencil, Trash2 } from "lucide-react";
import { type ReactNode, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useDeleteVendor,
  useUpdateVendor,
  useVendor,
} from "@/features/accounting/vendors/api/vendors-hooks";
import { VendorFormDialog } from "@/features/accounting/vendors/pages/vendor-form-dialog";
import { VendorTDSDeductionsPanel } from "@/features/accounting/tds/components/vendor-tds-deductions-panel";

function DetailRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b py-3 last:border-0">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm font-medium">{value}</span>
    </div>
  );
}

export function VendorDetailPage() {
  const { vendorId } = useParams<{ vendorId: string }>();
  const navigate = useNavigate();
  const { data: vendor, isLoading } = useVendor(vendorId);
  const updateVendor = useUpdateVendor(vendorId ?? "");
  const deleteVendor = useDeleteVendor();

  const [editOpen, setEditOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);

  if (isLoading || !vendor) {
    return (
      <div className="space-y-4 p-8">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const handleDelete = () => {
    deleteVendor.mutate(vendor.id, { onSuccess: () => navigate("/accounting/vendors") });
  };

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => navigate("/accounting/vendors")}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">{vendor.name}</h1>
            <div className="mt-1 flex items-center gap-2">
              <span className="font-mono text-xs text-muted-foreground">{vendor.vendor_code}</span>
              <Badge variant={vendor.is_active ? "success" : "secondary"}>
                {vendor.is_active ? "Active" : "Inactive"}
              </Badge>
            </div>
          </div>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => updateVendor.mutate({ is_active: !vendor.is_active })}
            disabled={updateVendor.isPending}
          >
            {vendor.is_active ? "Deactivate" : "Activate"}
          </Button>
          <Button variant="outline" onClick={() => setEditOpen(true)}>
            <Pencil className="h-4 w-4" />
            Edit
          </Button>
          <Button variant="outline" onClick={() => setDeleteOpen(true)}>
            <Trash2 className="h-4 w-4" />
            Delete
          </Button>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Contact details</CardTitle>
          </CardHeader>
          <CardContent>
            <DetailRow label="Email" value={vendor.email || "—"} />
            <DetailRow label="Phone" value={vendor.phone || "—"} />
            <DetailRow label="GSTIN" value={vendor.gstin || "—"} />
            <DetailRow label="PAN" value={vendor.pan_number || "—"} />
            <DetailRow
              label="Address"
              value={
                [vendor.address_line1, vendor.address_line2, vendor.city, vendor.state, vendor.country, vendor.postal_code]
                  .filter(Boolean)
                  .join(", ") || "—"
              }
            />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Bank details</CardTitle>
          </CardHeader>
          <CardContent>
            <DetailRow label="Bank name" value={vendor.bank_name || "—"} />
            <DetailRow label="Account number" value={vendor.bank_account_number || "—"} />
            <DetailRow label="IFSC code" value={vendor.bank_ifsc_code || "—"} />
            {vendor.notes && (
              <div className="pt-3">
                <p className="text-sm text-muted-foreground">Notes</p>
                <p className="mt-1 whitespace-pre-wrap text-sm">{vendor.notes}</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <VendorTDSDeductionsPanel vendorId={vendor.id} />

      <VendorFormDialog open={editOpen} onOpenChange={setEditOpen} vendor={vendor} />

      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete vendor</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Are you sure you want to delete <span className="font-medium">{vendor.name}</span>? This
            action cannot be undone.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteOpen(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDelete} disabled={deleteVendor.isPending}>
              {deleteVendor.isPending ? "Deleting..." : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
