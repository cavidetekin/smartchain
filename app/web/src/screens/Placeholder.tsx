// Ekranlar gelene kadar boş sayfa: "Bu ekran X adımında gelecek" (docs/12).
import { FileQuestion, Lock } from "lucide-react";
import { Link } from "react-router";

import { tr } from "../i18n/tr";
import { Card } from "../ui";
import { HOME, type Screen } from "./catalog";

export function Placeholder({ screen }: { screen: Screen }) {
  const Icon = screen.icon;
  return (
    <section className="sc-page">
      <header className="sc-page-head">
        <h1>{screen.name}</h1>
        <p className="sc-muted">{tr.screen.number(screen.no)}</p>
      </header>
      <Card className="sc-placeholder">
        <Icon aria-hidden="true" className="sc-placeholder-icon" />
        <p className="sc-coming">{tr.screen.comingIn(screen.step)}</p>
        <p className="sc-muted">{screen.description}</p>
        {screen.requiresWorkspace && (
          <p className="sc-note"><Lock aria-hidden="true" /> {tr.menu.needsWorkspace}</p>
        )}
      </Card>
    </section>
  );
}

export function NotFound() {
  return (
    <section className="sc-page">
      <header className="sc-page-head">
        <h1>{tr.screen.notFound}</h1>
      </header>
      <Card className="sc-placeholder">
        <FileQuestion aria-hidden="true" className="sc-placeholder-icon" />
        <p className="sc-muted">{tr.screen.notFoundHint}</p>
        <Link to={HOME.path} className="sc-link">{tr.screen.backHome}</Link>
      </Card>
    </section>
  );
}
