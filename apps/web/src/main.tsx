import React from "react";
import ReactDOM from "react-dom/client";

import App from "@/App";

import { reloadOnStaleChunk } from "@/lib/reload-on-stale-chunk";
import { installZodMessages } from "@/lib/zod-messages";

import "@/styles/globals.css";

reloadOnStaleChunk();
installZodMessages();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
