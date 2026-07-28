import { Bell, CheckCheck } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  useMarkAllNotificationsRead,
  useMarkNotificationRead,
  useNotificationsList,
  useUnreadCount,
} from "@/features/notifications/api/notifications-hooks";
import type { NotificationPublic } from "@/features/notifications/api/notifications-api";

function typeDotClass(type: NotificationPublic["notification_type"]): string {
  switch (type) {
    case "success":
      return "bg-emerald-500";
    case "warning":
      return "bg-amber-500";
    case "error":
      return "bg-destructive";
    case "action_required":
      return "bg-blue-500";
    default:
      return "bg-muted-foreground";
  }
}

export function NotificationBell() {
  const navigate = useNavigate();
  const { data: unreadCount } = useUnreadCount();
  const { data } = useNotificationsList({ limit: 10 });
  const markRead = useMarkNotificationRead();
  const markAllRead = useMarkAllNotificationsRead();

  const handleClick = (notification: NotificationPublic) => {
    if (!notification.is_read) {
      markRead.mutate(notification.id);
    }
    if (notification.link_url) {
      navigate(notification.link_url);
    }
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" className="relative" aria-label="Notifications">
          <Bell className="h-4 w-4" />
          {!!unreadCount && unreadCount > 0 && (
            <Badge
              variant="destructive"
              className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full px-1 text-[10px]"
            >
              {unreadCount > 99 ? "99+" : unreadCount}
            </Badge>
          )}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-80">
        <div className="flex items-center justify-between px-2 py-1.5">
          <DropdownMenuLabel className="p-0">Notifications</DropdownMenuLabel>
          {!!unreadCount && unreadCount > 0 && (
            <Button
              variant="ghost"
              size="sm"
              className="h-6 gap-1 px-2 text-xs"
              onClick={() => markAllRead.mutate()}
            >
              <CheckCheck className="h-3 w-3" />
              Mark all read
            </Button>
          )}
        </div>
        <DropdownMenuSeparator />
        {(data?.items.length ?? 0) === 0 && (
          <p className="px-2 py-6 text-center text-sm text-muted-foreground">You're all caught up.</p>
        )}
        <div className="max-h-96 overflow-y-auto">
          {data?.items.map((notification) => (
            <DropdownMenuItem
              key={notification.id}
              className="flex flex-col items-start gap-0.5 whitespace-normal py-2"
              onClick={() => handleClick(notification)}
            >
              <div className="flex w-full items-start gap-2">
                <span
                  className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${typeDotClass(notification.notification_type)}`}
                />
                <div className="min-w-0 flex-1">
                  <p className={`text-sm ${notification.is_read ? "text-muted-foreground" : "font-medium"}`}>
                    {notification.title}
                  </p>
                  {notification.body && (
                    <p className="line-clamp-2 text-xs text-muted-foreground">{notification.body}</p>
                  )}
                  <p className="text-[10px] text-muted-foreground">
                    {new Date(notification.created_at).toLocaleString()}
                  </p>
                </div>
              </div>
            </DropdownMenuItem>
          ))}
        </div>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
