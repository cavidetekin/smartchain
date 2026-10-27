// Yönlendirme: kabuk ve her ekranın sayfası (docs/12).
import { Navigate, Route, Routes } from "react-router";

import { HOME, SCREENS } from "./screens/catalog";
import { NotFound, Placeholder } from "./screens/Placeholder";
import { StyleGuide } from "./screens/StyleGuide";
import { Shell } from "./shell/Shell";

export function App({ userId }: { userId: number }) {
  return (
    <Routes>
      <Route element={<Shell userId={userId} />}>
        <Route index element={<Navigate to={HOME.path} replace />} />
        {SCREENS.map((s) => (
          <Route key={s.no} path={s.path} element={<Placeholder screen={s} />} />
        ))}
        {/* Stil örnekleri (K-85): ekran değildir, menüde yoktur */}
        <Route path="/stil" element={<StyleGuide />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
