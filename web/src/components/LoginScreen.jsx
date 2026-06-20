// Login screen (bridge — protect internet exposure). Shown by App when the server reports auth is
// enabled and the session is not authenticated. POSTs to /api/login; on success the server sets an
// HttpOnly session cookie and onSuccess() re-boots the app. i18n + design-system styled.
import React from "react";
import * as api from "../api.js";
import { useT, LangSwitcher } from "../i18n/index.jsx";

const { Button, Input, Banner } = window.KanbanMateDesignSystem_2463ad;

export default function LoginScreen({ onSuccess }) {
  const { t } = useT();
  const [username, setUsername] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  // Store a FLAG (not the translated string) so the message re-translates on language change.
  const [failed, setFailed] = React.useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setFailed(false);
    try {
      await api.login({ login: username, password });
      onSuccess();
    } catch (_) {
      setFailed(true);
      setBusy(false);
    }
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "var(--background)",
        color: "var(--foreground)",
      }}
    >
      <form
        onSubmit={submit}
        style={{
          width: 360,
          background: "var(--card)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius-lg)",
          boxShadow: "var(--shadow-lg)",
          padding: 28,
          display: "flex",
          flexDirection: "column",
          gap: 16,
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <span
            style={{
              display: "inline-grid",
              placeItems: "center",
              width: 30,
              height: 30,
              borderRadius: "var(--radius-md)",
              background: "var(--primary)",
              color: "var(--primary-foreground)",
              fontFamily: "var(--font-mono)",
              fontWeight: 600,
            }}
          >
            [▸]
          </span>
          <LangSwitcher />
        </div>
        <div>
          <div
            style={{
              fontFamily: "var(--font-display)",
              fontSize: "var(--text-xl)",
              fontWeight: 600,
            }}
          >
            {t("login.title")}
          </div>
          <div
            style={{
              fontSize: 13,
              color: "var(--muted-foreground)",
              marginTop: 4,
              lineHeight: 1.5,
            }}
          >
            {t("login.subtitle")}
          </div>
        </div>
        {failed && <Banner tone="error">{t("login.failed")}</Banner>}
        <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <span
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 11,
              color: "var(--muted-foreground)",
            }}
          >
            {t("login.username")}
          </span>
          <Input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoFocus
            autoComplete="username"
          />
        </label>
        <label style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <span
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 11,
              color: "var(--muted-foreground)",
            }}
          >
            {t("login.password")}
          </span>
          <Input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
          />
        </label>
        <Button type="submit" variant="primary" disabled={busy}>
          {busy ? t("login.signing_in") : t("login.submit")}
        </Button>
      </form>
    </div>
  );
}
