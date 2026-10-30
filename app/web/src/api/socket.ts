// Anlık bildirim bağlantısı (K-69, fonksiyon 48). Koparsa 10 sn sonra yeniden bağlanır;
// bağlantı yokken çağıran yedek sorguya (30 sn) geçer. Bağlantı oturumla açılır (K-97): sunucu oturum bitti diye
// 4401 ile kapatırsa yeniden bağlanılmaz, oturum denetlenir (giriş sayfasına dönülür).
import { emitAuth } from "./client";

export type ConnectionState = "connected" | "reconnecting";

export const RECONNECT_MS = 10_000;
export const SESSION_CLOSED = 4401;

export function socketUrl(path: string, loc: Location = window.location): string {
  const proto = loc.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${loc.host}${path}`;
}

export interface SocketHandle {
  close(): void;
}

export function connect(
  url: string,
  onMessage: (msg: { type: string; [k: string]: unknown }) => void,
  onState: (state: ConnectionState) => void,
): SocketHandle {
  let ws: WebSocket | null = null;
  let timer: ReturnType<typeof setTimeout> | null = null;
  let closed = false;

  const open = () => {
    ws = new WebSocket(url);
    ws.onmessage = (e) => {
      try {
        onMessage(JSON.parse(String(e.data)));
      } catch {
        // tanınmayan mesaj
      }
    };
    ws.onopen = () => onState("connected");
    ws.onclose = (e) => {
      if (closed) return;
      if (e?.code === SESSION_CLOSED) {
        closed = true;
        onState("reconnecting");
        emitAuth({ kind: "check" });
        return;
      }
      onState("reconnecting");
      timer = setTimeout(open, RECONNECT_MS);
    };
  };
  open();
  return {
    close() {
      closed = true;
      if (timer) clearTimeout(timer);
      ws?.close();
    },
  };
}
