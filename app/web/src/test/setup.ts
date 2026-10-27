// Test ortamı: jest-dom eşleştiricileri, her testten sonra temizlik.
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

afterEach(() => {
  cleanup();
  window.localStorage.clear();
  document.documentElement.style.fontSize = "";
  vi.restoreAllMocks();
  vi.useRealTimers();
});
