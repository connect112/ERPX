import { ArrowLeft, PackagePlus, Send, XCircle } from "lucide-react";
import { type ReactNode, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useVendorsList } from "@/features/accounting/vendors/api/vendors-hooks";
import { useItemsList } from "@/features/inventory/items/api/items-hooks";
import { CreateGoodsReceiptDialog } from "@/features/procurement/goods-receipts/components/create-goods-receipt-dialog";
import { GoodsReceiptsPanel } from "@/features/procurement/goods-receipts/components/goods-receipts-panel";
import {
  useCancelPurchaseOrder,
  usePurchaseOrder,
  useSendPurchaseOrder,
} from "@/features/procurement/purchase-orders/api/purchase-orders-hooks";
import { PurchaseOrderStatusBadge } from "@/features/procurement/purchase-orders/components/purchase-order-status-badge";

function DetailRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b py-3 last:border-0">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="text-sm font-medium">{value}</span>
    </div>
  );
}

export function PurchaseOrderDetailPage() {
  const { poId } = useParams<{ poId: string }>();
  const navigate = useNavigate();
  const { data: po, isLoading } = usePurchaseOrder(poId);
  const { data: vendors } = useVendorsList({ limit: 200 });
  const { data: items } = useItemsList({ limit: 200 });

  const sendPo = useSendPurchaseOrder(poId ?? "");
  const cancelPo = useCancelPurchaseOrder(poId ?? "");
  const [cancelOpen, setCancelOpen] = useState(false);
  const [receiveOpen, setReceiveOpen] = useState(false);

  if (isLoading || !po) {
    return (
      <div className="space-y-4 p-8">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const vendorName = vendors?.items.find((v) => v.id === po.vendor_id)?.name ?? po.vendor_id;
  const itemName = (id: string) => items?.items.find((i) => i.id === id)?.name ?? id;

  return (
    <div className="space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => navigate("/procurement/purchase-orders")}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">{po.po_number}</h1>
            <div className="mt-1 flex items-center gap-2">
              <span className="text-xs text-muted-foreground">{vendorName}</span>
              <PurchaseOrderStatusBadge status={po.status} />
            </div>
          </div>
        </div>
        <div className="flex gap-2">
          {po.status === "draft" && (
            <Button variant="outline" onClick={() => sendPo.mutate()} disabled={sendPo.isPending}>
              <Send className="h-4 w-4" />
              {sendPo.isPending ? "Sending..." : "Send"}
            </Button>
          )}
          {(po.status === "sent" || po.status === "partially_received") && (
            <Button variant="outline" onClick={() => setReceiveOpen(true)}>
              <PackagePlus className="h-4 w-4" />
              Receive goods
            </Button>
          )}
          {po.status !== "received" && po.status !== "cancelled" && (
            <Button variant="outline" onClick={() => setCancelOpen(true)}>
              <XCircle className="h-4 w-4" />
              Cancel
            </Button>
          )}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">Line items</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Item</TableHead>
                  <TableHead>Ordered</TableHead>
                  <TableHead>Received</TableHead>
                  <TableHead>Unit price</TableHead>
                  <TableHead>Total</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {po.lines.map((line) => (
                  <TableRow key={line.id}>
                    <TableCell className="font-medium">{itemName(line.item_id)}</TableCell>
                    <TableCell className="text-muted-foreground">{line.quantity_ordered}</TableCell>
                    <TableCell className="text-muted-foreground">{line.quantity_received}</TableCell>
                    <TableCell className="text-muted-foreground">{line.unit_price.toLocaleString()}</TableCell>
                    <TableCell className="font-medium">{line.line_total.toLocaleString()}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Summary</CardTitle>
          </CardHeader>
          <CardContent>
            <DetailRow label="Order date" value={new Date(po.order_date).toLocaleDateString()} />
            {po.expected_delivery_date && (
              <DetailRow
                label="Expected delivery"
                value={new Date(po.expected_delivery_date).toLocaleDateString()}
              />
            )}
            <DetailRow label="Subtotal" value={po.subtotal_amount.toLocaleString()} />
            <DetailRow label="Tax" value={po.tax_amount.toLocaleString()} />
            <DetailRow label="Total" value={po.total_amount.toLocaleString()} />
            {po.notes && (
              <div className="pt-3">
                <p className="text-sm text-muted-foreground">Notes</p>
                <p className="mt-1 whitespace-pre-wrap text-sm">{po.notes}</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <GoodsReceiptsPanel poId={po.id} />

      <CreateGoodsReceiptDialog open={receiveOpen} onOpenChange={setReceiveOpen} po={po} />

      <Dialog open={cancelOpen} onOpenChange={setCancelOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Cancel purchase order</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Are you sure you want to cancel {po.po_number}? This action cannot be undone.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCancelOpen(false)}>
              Keep order
            </Button>
            <Button
              variant="destructive"
              onClick={() => cancelPo.mutate(undefined, { onSuccess: () => setCancelOpen(false) })}
              disabled={cancelPo.isPending}
            >
              {cancelPo.isPending ? "Cancelling..." : "Cancel order"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
