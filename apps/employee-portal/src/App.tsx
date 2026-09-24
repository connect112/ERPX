import { QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { RouterProvider } from "react-router-dom";

import { ThemeProvider } from "@/components/theme-provider";
import { queryClient } from "@/lib/query-client";
import { router } from "@/router";

export default function App() {
  return (
    <ThemeProvider defaultTheme="system" storageKey="erpx-theme">
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
        {import.meta.env.DEV && <ReactQueryDevtools initialIsOpen={false} />}
      </QueryClientProvider>
    </ThemeProvider>
  );
}
