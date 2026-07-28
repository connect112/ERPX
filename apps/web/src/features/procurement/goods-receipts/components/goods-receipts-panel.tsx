import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useGoodsReceiptsByPurchaseOrder } from "@/features/procurement/goods-receipts/api/goods-receipts-hooks";

export function GoodsReceiptsPanel({ poId }: { poId: string }) {
  const { data: receipts, isLoading } = useGoodsReceiptsByPurchaseOrder(poId);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Goods receipts</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading && <Skeleton className="h-24 w-full" />}
        {!isLoading && (receipts?.length ?? 0) === 0 && (
          <p className="py-4 text-center text-sm text-muted-foreground">No goods received yet.</p>
        )}
        {!isLoading && (receipts?.length ?? 0) > 0 && (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Receipt number</TableHead>
                <TableHead>Date</TableHead>
                <TableHead>Lines</TableHead>
                <TableHead>Notes</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {receipts?.map((receipt) => (
                <TableRow key={receipt.id}>
                  <TableCell className="font-mono text-xs text-muted-foreground">
                    {receipt.receipt_number}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {new Date(receipt.receipt_date).toLocaleDateString()}
                  </TableCell>
                  <TableCell className="text-muted-foreground">{receipt.lines.length}</TableCell>
                  <TableCell className="max-w-xs truncate text-muted-foreground">
                    {receipt.notes || "—"}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
