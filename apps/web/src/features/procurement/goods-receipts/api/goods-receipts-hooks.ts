import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type GoodsReceiptCreatePayload,
  goodsReceiptsApi,
} from "@/features/procurement/goods-receipts/api/goods-receipts-api";

const goodsReceiptsKeys = {
  all: ["procurement", "goods-receipts"] as const,
  byPurchaseOrder: (poId: string) => [...goodsReceiptsKeys.all, "po", poId] as const,
};

export function useGoodsReceiptsByPurchaseOrder(poId: string | undefined) {
  return useQuery({
    queryKey: goodsReceiptsKeys.byPurchaseOrder(poId ?? ""),
    queryFn: () => goodsReceiptsApi.listByPurchaseOrder(poId as string),
    enabled: !!poId,
  });
}

export function useCreateGoodsReceipt() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: GoodsReceiptCreatePayload) => goodsReceiptsApi.create(payload),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: goodsReceiptsKeys.byPurchaseOrder(variables.purchase_order_id),
      });
      queryClient.invalidateQueries({ queryKey: ["procurement", "purchase-orders"] });
      queryClient.invalidateQueries({ queryKey: ["inventory", "items"] });
      queryClient.invalidateQueries({ queryKey: ["inventory", "stock"] });
    },
  });
}
