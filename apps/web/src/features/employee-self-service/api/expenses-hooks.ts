import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { myExpensesApi } from "@/features/employee-self-service/api/expenses-api";

const claimsKey = ["expense-claims", "me"] as const;

export function useMyExpenseClaims() {
  return useQuery({
    queryKey: claimsKey,
    queryFn: () => myExpensesApi.myClaims(),
  });
}

export function useSubmitExpenseClaim() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { description: string; amount: number; receipt?: File }) => {
      let receiptDocumentId: string | undefined;
      if (input.receipt) {
        const { document_id, upload_url } = await myExpensesApi.requestReceiptUpload(
          input.receipt.name,
          input.receipt.type || "application/octet-stream"
        );
        const uploadResponse = await myExpensesApi.uploadToPresignedUrl(upload_url, input.receipt);
        if (!uploadResponse.ok) {
          throw new Error("Receipt upload failed.");
        }
        await myExpensesApi.confirmReceiptUpload(document_id);
        receiptDocumentId = document_id;
      }
      return myExpensesApi.submitClaim({
        description: input.description,
        amount: input.amount,
        receipt_document_id: receiptDocumentId,
      });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: claimsKey }),
  });
}
