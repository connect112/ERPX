import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";

import { Button } from "@/components/ui/button";

interface JitsiMeetAPI {
  dispose: () => void;
  addEventListener: (event: string, listener: (...args: unknown[]) => void) => void;
}

declare global {
  interface Window {
    JitsiMeetExternalAPI?: new (domain: string, options: Record<string, unknown>) => JitsiMeetAPI;
  }
}

interface VideoCallOverlayProps {
  domain: string;
  room: string;
  jwt: string;
  title: string;
  onClose: () => void;
}

const scriptCache = new Map<string, Promise<void>>();

function loadJitsiScript(domain: string): Promise<void> {
  const cached = scriptCache.get(domain);
  if (cached) return cached;

  const promise = new Promise<void>((resolve, reject) => {
    if (window.JitsiMeetExternalAPI) {
      resolve();
      return;
    }
    const script = document.createElement("script");
    script.src = `https://${domain}/external_api.js`;
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("Failed to load the video call script."));
    document.body.appendChild(script);
  });
  scriptCache.set(domain, promise);
  return promise;
}

/**
 * Full-screen embedded Jitsi call — ported from apps/student-portal's own
 * copy (same component, same behavior). One JitsiMeetExternalAPI instance
 * per active call, disposed on unmount, so navigating away or hitting
 * Close actually hangs up rather than leaving a hidden connection running.
 */
export function VideoCallOverlay({ domain, room, jwt, title, onClose }: VideoCallOverlayProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const apiRef = useRef<JitsiMeetAPI | null>(null);
  const [hasEnded, setHasEnded] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setHasEnded(false);

    loadJitsiScript(domain)
      .then(() => {
        if (cancelled || !containerRef.current || !window.JitsiMeetExternalAPI) return;
        const api = new window.JitsiMeetExternalAPI(domain, {
          roomName: room,
          jwt,
          parentNode: containerRef.current,
          width: "100%",
          height: "100%",
          // No userInfo.displayName here on purpose — the JWT's own
          // context.user.name claim (the student's code, e.g.
          // "STU-00001", never their real name) is the sole source of
          // the in-call display name.
          configOverwrite: {
            prejoinPageEnabled: false,
            // The JWT's name claim is the sole source of the in-call
            // display name (set just above) -- without this, anyone can
            // still open their own profile pane and type over it,
            // defeating the anonymization the JWT claim exists for.
            readOnlyName: true,
            // Also strips Jitsi's own "Grant moderator"/"Kick" actions --
            // students are never moderators in this room, so these should
            // never be reachable regardless of who's viewing this menu.
            remoteVideoMenu: { disablePrivateChat: "all", disableGrantModerator: true, disableKick: true },
          },
          interfaceConfigOverwrite: {
            TOOLBAR_BUTTONS: [
              "microphone",
              "camera",
              "desktop",
              "chat",
              "raisehand",
              "tileview",
              // Lets participants see who's actually in the room --
              // names shown are still just the anonymized JWT ones
              // (student codes / "Trainer"), never real names.
              "participants-pane",
              "hangup",
              "fullscreen",
            ],
            // Jitsi's own branding watermark, on by default -- this is
            // ERPX's own embedded call, not a link out to jitsi.org.
            SHOW_JITSI_WATERMARK: false,
          },
        });
        apiRef.current = api;
        api.addEventListener("videoConferenceLeft", () => {
          apiRef.current?.dispose();
          apiRef.current = null;
          setHasEnded(true);
        });
      })
      .catch(() => {
        // Script failed to load (network hiccup, ad-blocker) — nothing to
        // embed; the overlay's own Close button still lets someone back out.
      });

    return () => {
      cancelled = true;
      apiRef.current?.dispose();
      apiRef.current = null;
    };
    // Re-run only when the call identity itself changes.
  }, [domain, room, jwt]);

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-black">
      <div className="flex items-center justify-between bg-black/80 px-4 py-2 text-white">
        <span className="text-sm font-medium">{title}</span>
        <Button
          size="sm"
          variant="ghost"
          className="text-white hover:bg-white/10 hover:text-white"
          onClick={onClose}
        >
          <X className="h-4 w-4" />
          Close
        </Button>
      </div>
      {hasEnded ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-4 text-white">
          <p className="text-lg font-medium">Class ended.</p>
          <Button variant="outline" className="text-white hover:bg-white/10 hover:text-white" onClick={onClose}>
            Back to dashboard
          </Button>
        </div>
      ) : (
        <div ref={containerRef} className="flex-1" />
      )}
    </div>
  );
}
