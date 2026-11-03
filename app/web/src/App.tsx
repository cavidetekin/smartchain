// Yönlendirme: giriş sayfası, oturum kapısı, kabuk ve her ekranın sayfası (docs/12; oturum K-97).
import type { ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router";

import type { Me } from "./auth/authApi";
import { AuthProvider } from "./auth/AuthContext";
import { AuthGate } from "./auth/AuthGate";
import { LoginPage } from "./auth/LoginPage";
import { HOME, SCREENS } from "./screens/catalog";
import { ScreenGate } from "./screens/Forbidden";
import { NotFound, Placeholder } from "./screens/Placeholder";
import { StyleGuide } from "./screens/StyleGuide";
import { SystemOwner } from "./screens/SystemOwner";
import { TableDemo } from "./screens/TableDemo";
import { Users } from "./screens/Users";
import { Shell } from "./shell/Shell";

/** Yazılmış ekranlar; öteki ekranlar boş sayfasını gösterir. */
const PAGES: Record<string, ReactNode> = { "22": <Users />, "25": <SystemOwner /> };

/** initialMe yalnız testlerde verilir; verilmezse oturum açılışta sunucuya sorulur. */
export function App({ initialMe }: { initialMe?: Me | null }) {
  return (
    <AuthProvider initialMe={initialMe}>
      <Routes>
        <Route path="/giris" element={<LoginPage />} />
        <Route element={<AuthGate />}>
          <Route element={<Shell />}>
            <Route index element={<Navigate to={HOME.path} replace />} />
            {SCREENS.map((s) => (
              <Route key={s.no} path={s.path} element={<ScreenGate fn={s.fn}>{PAGES[s.no] ?? <Placeholder screen={s} />}</ScreenGate>} />
            ))}
            {/* Ekran 25'in eski adresi (K-104) */}
            <Route path="/yonetim/system-owner" element={<Navigate to="/yonetim/sistem-ayarlari" replace />} />
            {/* Stil örnekleri (K-85): ekran değildir, menüde yoktur */}
            <Route path="/stil" element={<StyleGuide />} />
            {/* Tablo bileşeni denemesi (K-87): ekran değildir, menüde yoktur */}
            <Route path="/tablo" element={<ScreenGate fn={10}><TableDemo /></ScreenGate>} />
            <Route path="*" element={<NotFound />} />
          </Route>
        </Route>
      </Routes>
    </AuthProvider>
  );
}
