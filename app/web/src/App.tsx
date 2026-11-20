// Yönlendirme: giriş sayfası, oturum kapısı, kabuk ve her ekranın sayfası (docs/12; oturum K-97).
import { Fragment, type ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router";

import type { Me } from "./auth/authApi";
import { AuditLog } from "./screens/AuditLog";
import { CapacityManagement } from "./screens/CapacityManagement";
import { ModelConstraints } from "./screens/ModelConstraints";
import { DataLoad } from "./screens/DataLoad";
import { DataQuality } from "./screens/DataQuality";
import { Parameters } from "./screens/Parameters";
import { Scenarios } from "./screens/Scenarios";
import { DataRules } from "./screens/DataRules";
import { RawCompare } from "./screens/RawCompare";
import { ValidationRules } from "./screens/ValidationRules";
import { Integration } from "./screens/Integration";
import { AuthProvider } from "./auth/AuthContext";
import { AuthGate } from "./auth/AuthGate";
import { LoginPage } from "./auth/LoginPage";
import { HOME, SCREENS } from "./screens/catalog";
import { ScreenGate } from "./screens/Forbidden";
import { MasterData } from "./screens/MasterData";
import { NotFound, Placeholder } from "./screens/Placeholder";
import { StyleGuide } from "./screens/StyleGuide";
import { SystemHealth } from "./screens/SystemHealth";
import { SystemOwner } from "./screens/SystemOwner";
import { TransactionData } from "./screens/TransactionData";
import { TableDemo } from "./screens/TableDemo";
import { Users } from "./screens/Users";
import { Shell } from "./shell/Shell";
import { useShell } from "./shell/ShellContext";

/** Yazılmış ekranlar; öteki ekranlar boş sayfasını gösterir. */
const PAGES: Record<string, ReactNode> = { "02": <DataLoad />, "03": <MasterData />, "29": <TransactionData />, "28": <RawCompare />, "04": <DataRules />, "05": <DataQuality />, "06": <Parameters />, "30": <CapacityManagement />, "31": <ModelConstraints />, "07": <Scenarios />, "22": <Users />, "23": <Integration />, "24": <SystemHealth />, "25": <SystemOwner />, "26": <AuditLog />, "27": <ValidationRules /> };

/** Senaryoya bağlı ekran (K-177): seçili senaryo yüklenince çizilir, senaryo değişince baştan yüklenir (taslak ve durum sıfırlanır). */
function ScenarioBound({ children }: { children: ReactNode }) {
  const { scenario } = useShell();
  return scenario ? <Fragment key={scenario.id}>{children}</Fragment> : null;
}

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
              <Route key={s.no} path={s.path} element={<ScreenGate fn={s.fn} orFn={s.orFn}>{s.scenarioBound ? <ScenarioBound>{PAGES[s.no]}</ScenarioBound> : PAGES[s.no] ?? <Placeholder screen={s} />}</ScreenGate>} />
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
