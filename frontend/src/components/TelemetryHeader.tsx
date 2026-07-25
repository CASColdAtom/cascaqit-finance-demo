import { Languages, ShieldCheck } from "lucide-react";
import { useI18n } from "../i18n";

export function TelemetryHeader() {
  const { language, setLanguage, t } = useI18n();
  return (
    <header className="telemetry-header">
      <div className="brand-lockup">
        <img
          className="brand-logo"
          src="/cascoldatom-logo-transparent.png"
          alt="CASColdAtom 中科酷原"
        />
        <div className="brand-title">
          <strong>{t("productTitle")}</strong>
          <span>{t("productSubtitle")}</span>
        </div>
      </div>
      <div className="telemetry-strip">
        <span className="telemetry-item status-live">
          <i aria-hidden="true" /> {t("serviceOnline")}
        </span>
        <span className="telemetry-item telemetry-wide">
          <ShieldCheck size={14} aria-hidden="true" /> {t("auditReady")}
        </span>
        <div className="language-switch" role="group" aria-label="Language / 语言">
          <Languages size={14} aria-hidden="true" />
          <button
            type="button"
            aria-pressed={language === "zh"}
            onClick={() => setLanguage("zh")}
          >
            中文
          </button>
          <button
            type="button"
            aria-pressed={language === "en"}
            onClick={() => setLanguage("en")}
          >
            EN
          </button>
        </div>
      </div>
    </header>
  );
}
