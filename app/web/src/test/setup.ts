// Test ortamı: jest-dom eşleştiricileri, her testten sonra temizlik.
import "@testing-library/jest-dom/vitest";
import { cleanup, configure } from "@testing-library/react";
import { afterEach, vi } from "vitest";

// findBy / waitFor için bekleme 5 sn (varsayılan 1 sn): tam koşuda dosyalar paralel çalışır, yük altında ilk ekran açılışı 1 sn'yi aşabilir (docs/08).
configure({ asyncUtilTimeout: 5000 });

afterEach(() => {
  cleanup();
  window.localStorage.clear();
  document.documentElement.style.fontSize = "";
  vi.restoreAllMocks();
  vi.useRealTimers();
});
