// Yönlendirme: giriş sayfası, oturum kapısı, kabuk ve her ekranın sayfası (docs/12; oturum K-97).
import { Navigate, Route, Routes } from "react-router";

import type { Me } from "./auth/authApi";
import { AuthProvider } from "./auth/AuthContext";
import { AuthGate } from "./auth/AuthGate";
import { LoginPage } from "./auth/LoginPage";
import { HOME, SCREENS } from "./screens/catalog";
import { NotFound, Placeholder } from "./screens/Placeholder";
import { StyleGuide } from "./screens/StyleGuide";
import { TableDemo } from "./screens/TableDemo";
import { Shell } from "./shell/Shell";

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
              <Route key={s.no} path={s.path} element={<Placeholder screen={s} />} />
            ))}
            {/* Stil örnekleri (K-85): ekran değildir, menüde yoktur */}
            <Route path="/stil" element={<StyleGuide />} />
            {/* Tablo bileşeni denemesi (K-87): ekran değildir, menüde yoktur */}
            <Route path="/tablo" element={<TableDemo />} />
            <Route path="*" element={<NotFound />} />
          </Route>
        </Route>
      </Routes>
    </AuthProvider>
  );
}
