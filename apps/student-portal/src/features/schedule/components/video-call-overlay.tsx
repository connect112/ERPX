import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";

import { Button } from "@/components/ui/button";

interface JitsiMeetAPI {
  dispose: () => void;
  addEventListener: (event: string, listener: (...args: unknown[]) => void) => void;
  executeCommand: (command: string, ...args: unknown[]) => void;
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
 * Full-screen embedded Jitsi call, mounted in place of the old "open in a
 * new tab" link once a per-join token is minted (see
 * use-join-live-class in schedule-hooks.ts / the Join button in
 * my-schedule-page.tsx). One JitsiMeetExternalAPI instance per active
 * call — disposed on unmount, so navigating away or hitting Close
 * actually hangs up rather than leaving a hidden connection running.
 */
export function VideoCallOverlay({
  domain,
  room,
  jwt,
  title,
  onClose,
}: VideoCallOverlayProps) {
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
          // context.user.name claim (a student's code, never their real
          // name; see modules/live_classes/routes.py) is the sole source
          // of the in-call display name, so there's no client-side value
          // that could show or briefly flash the real name.
          configOverwrite: {
            prejoinPageEnabled: false,
            // The JWT's name claim is the sole source of the in-call
            // display name (set just above) -- without this, a student
            // could still open their own profile pane and type over it,
            // defeating the anonymization the JWT claim exists for.
            readOnlyName: true,
            // Students share this room with other students; a private
            // 1:1 message between two students would bypass that
            // isolation, so it's disabled for everyone (the trainer, who
            // isn't anonymized, is unaffected — this only removes the
            // per-participant "Private chat" menu item). Also strips
            // Jitsi's own "Grant moderator"/"Kick" actions -- students
            // are never moderators in this room, so these should never
            // be reachable regardless of who's viewing this menu.
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
              "fullscreen",
              // No "hangup" here on purpose: Jitsi's own native hangup
              // button renders a "Leave meeting" / "End meeting for
              // everyone" dropdown whenever its local isModerator redux
              // state is (or becomes) true -- which we've seen happen for
              // a real student even though the server-granted MUC role
              // was correctly PARTICIPANT the whole time. Rather than
              // depend on that client-side flag being right, students
              // leave only through the header's own Leave button below,
              // which just disposes the call locally -- there is no
              // native "end for everyone" affordance to mis-render.
            ],
            // Jitsi's own branding watermark, on by default -- this is
            // ERPX's own embedded call, not a link out to jitsi.org.
            SHOW_JITSI_WATERMARK: false,
          },
        });
        apiRef.current = api;
        // The room name itself is an opaque, non-guessable slug (by
        // design -- see build_room_name in jitsi.py), so without this
        // Jitsi's own subject bar inside the call shows that raw slug
        // instead of the class title shown in our own header above it.
        // "localSubject" (not "subject") applies immediately for this
        // client alone, regardless of moderator role.
        api.executeCommand("localSubject", title);
        // videoConferenceLeft fires the instant the local participant
        // leaves (hangup, or being disconnected) -- well before Jitsi's
        // own IFrame client would otherwise show its own end-of-call/
        // feedback screen inside this container. Tearing the connection
        // down right here and showing our own "Class ended" state means
        // nobody sees a Jitsi-branded page and mistakes it for having
        // left the app.
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
          Leave meeting
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
