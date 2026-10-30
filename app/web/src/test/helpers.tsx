// Test yardımcıları: sahte API (fetch) ve sahte WebSocket.
import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { vi } from "vitest";

import { App } from "../App";
import type { Me } from "../auth/authApi";

export type Reply = { status?: number; body: unknown; headers?: Record<string, string> };
/** Sabit cevap, "offline" ya da isteğe göre cevap üreten işlev (yöntem ve gövde ile). */
/** Cevap işlevi Promise de döndürebilir (gecikmeli cevap; ör. kural değişince eski satırlar ekranda kalıyor mu). */
export type Routes = Record<string, Reply | "offline" | ((url: string, init?: RequestInit) => Reply | Promise<Reply>)>;

export const DATA_VERSION = {
  id: 35, location_code: "ORM-01", created_at: "2026-10-27T09:20:00+00:00", load_type: "Tam", is_synthetic: true,
};

/** Oturumdaki deneme kullanıcısı (K-97). */
export const ME: Me = {
  id: 3, user_name: "planlama", full_name: "Mert Planlama", role: "Key user", must_change_password: false,
  password_change_reason: null, idle_seconds_left: 1800, session: { idle_minutes: 30, warning_minutes: 5 },
  policy: { min_length: 10, require_letter_and_digit: true, history_count: 5, lock_after: 5, lock_minutes: 15 },
};

export function mockApi(routes: Routes = {}) {
  const all: Routes = {
    "/api/data-versions/current": { body: DATA_VERSION },
    "/api/jobs": { body: { jobs: [], counters: {} } },
    "/api/auth/me": { body: ME },
    "/api/auth/activity": { body: { idle_seconds_left: 1800 } },
    "/api/auth/logout": { status: 204, body: null },
    "/api/health": { body: { status: "ok", app_version: "0.15.0" } },
    ...routes,
  };
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const key = Object.keys(all).find((k) => url.startsWith(k));
    const route = key ? all[key] : undefined;
    if (!route || route === "offline") throw new TypeError("Failed to fetch");
    const reply = typeof route === "function" ? await route(url, init) : route;
    return new Response(reply.status === 204 ? null : JSON.stringify(reply.body), {
      status: reply.status ?? 200, headers: { "Content-Type": "application/json", ...reply.headers },
    });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

export class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  onmessage: ((e: { data: string }) => void) | null = null;
  onopen: (() => void) | null = null;
  onclose: ((e?: { code: number }) => void) | null = null;
  closed = false;

  constructor(public url: string) {
    FakeWebSocket.instances.push(this);
  }

  open() {
    this.onopen?.();
  }

  send(msg: unknown) {
    this.onmessage?.({ data: JSON.stringify(msg) });
  }

  drop() {
    this.onclose?.();
  }

  /** Sunucu kapattı (ör. 4401: oturum bitti). */
  closeWith(code: number) {
    this.onclose?.({ code });
  }

  close() {
    this.closed = true;
  }
}

export function mockSocket() {
  FakeWebSocket.instances = [];
  vi.stubGlobal("WebSocket", FakeWebSocket);
  return FakeWebSocket;
}

/** me: oturum açık kullanıcı (varsayılan ME); null oturumsuz; "ask" açılışta sunucuya sorulur (mockApi). */
export function renderApp(path = "/ana-sayfa", me: Me | null | "ask" = ME) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App initialMe={me === "ask" ? undefined : me} />
    </MemoryRouter>,
  );
}
