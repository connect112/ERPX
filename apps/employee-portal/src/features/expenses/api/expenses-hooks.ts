import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { expensesApi } from "@/features/expenses/api/expenses-api";

const claimsKey = ["expense-claims", "me"] as const;

export function useMyExpenseClaims() {
  return useQuery({
    queryKey: claimsKey,
    queryFn: () => expensesApi.myClaims(),
  });
}

export function useSubmitExpenseClaim() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { description: string; amount: number; receipt?: File }) => {
      let receiptDocumentId: string | undefined;
      if (input.receipt) {
        const { document_id, upload_url } = await expensesApi.requestReceiptUpload(
          input.receipt.name,
          input.receipt.type || "application/octet-stream"
        );
        const uploadResponse = await expensesApi.uploadToPresignedUrl(upload_url, input.receipt);
        if (!uploadResponse.ok) {
          throw new Error("Receipt upload failed.");
        }
        await expensesApi.confirmReceiptUpload(document_id);
        receiptDocumentId = document_id;
      }
      return expensesApi.submitClaim({
        description: input.description,
        amount: input.amount,
        receipt_document_id: receiptDocumentId,
      });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: claimsKey }),
  });
}
