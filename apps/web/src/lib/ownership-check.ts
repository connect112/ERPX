import axios from "axios";

import { apiClient } from "@/api/client";

// The backend answers "this account has no such record" with 404 (or 422 /
// 403 from the ownership dependencies) -- those are the only responses
// that genuinely mean "no". Anything else (a 401 mid-token-refresh, a
// network blip, a 5xx) says nothing about ownership, so it must NOT be
// cached as "no": it's rethrown so React Query retries, instead of
// hiding the trainer/employee/student sections until the next refresh.
const DEFINITIVE_NO = new Set([403, 404, 422]);

export async function checkOwnership(path: string): Promise<boolean> {
  try {
    await apiClient.get(path);
    return true;
  } catch (error) {
    if (axios.isAxiosError(error) && error.response && DEFINITIVE_NO.has(error.response.status)) {
      return false;
    }
    throw error;
  }
}
