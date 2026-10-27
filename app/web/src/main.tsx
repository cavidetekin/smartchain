// Giriş. Fontlar paketten gelir (U-20, K-83): @fontsource woff2 dosyalarını derlemeye gömer.
import "@fontsource/instrument-sans/400.css";
import "@fontsource/instrument-sans/500.css";
import "@fontsource/instrument-sans/600.css";
import "@fontsource/jetbrains-mono/400.css";
import "@fontsource/jetbrains-mono/500.css";
import "./styles/tokens.css";
import "./styles/app.css";
import "./styles/components.css";

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";

import { App } from "./App";
import { resolveUserId } from "./prefs";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <App userId={resolveUserId()} />
    </BrowserRouter>
  </StrictMode>,
);
