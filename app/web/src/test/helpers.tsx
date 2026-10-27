// Test yardımcıları: sahte API (fetch) ve sahte WebSocket.
import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { vi } from "vitest";

import { App } from "../App";

export type Reply = { status?: number; body: unknown };
/** Sabit cevap, "offline" ya da isteğe göre cevap üreten işlev (yöntem ve gövde ile). */
export type Routes = Record<string, Reply | "offline" | ((url: string, init?: RequestInit) => Reply)>;

export const DATA_VERSION = {
  id: 35, location_code: "ORM-01", created_at: "2026-10-27T09:20:00+00:00", load_type: "Tam", is_synthetic: true,
};

export function mockApi(routes: Routes = {}) {
  const all: Routes = {
    "/api/data-versions/current": { body: DATA_VERSION },
    "/api/jobs": { body: { jobs: [], counters: {} } },
    ...routes,
  };
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const key = Object.keys(all).find((k) => url.startsWith(k));
    const route = key ? all[key] : undefined;
    if (!route || route === "offline") throw new TypeError("Failed to fetch");
    const reply = typeof route === "function" ? route(url, init) : route;
    return new Response(JSON.stringify(reply.body), {
      status: reply.status ?? 200, headers: { "Content-Type": "application/json" },
    });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

export class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  onmessage: ((e: { data: string }) => void) | null = null;
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
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

  close() {
    this.closed = true;
  }
}

export function mockSocket() {
  FakeWebSocket.instances = [];
  vi.stubGlobal("WebSocket", FakeWebSocket);
  return FakeWebSocket;
}

export function renderApp(path = "/ana-sayfa", userId = 3) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App userId={userId} />
    </MemoryRouter>,
  );
}
