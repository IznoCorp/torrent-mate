// Profiles reference (read-only, DESIGN §13 operator feedback). Profiles are a code-defined
// security boundary (core/profiles + adapters/perms), NOT editable config — this panel surfaces
// what each profile grants so the operator understands the `profile` dropdown. It never mutates.
import React from "react";
import * as api from "../api.js";
import { PageIntro } from "../components/Help.jsx";
import useIsMobile from "../useIsMobile.js";
import { useT } from "../i18n/index.jsx";

const { Banner, KeyChip, Badge } = window.KanbanMateDesignSystem_2463ad;

export default function ProfilesPanel() {
  const { t } = useT();
  const isMobile = useIsMobile();
  const [profiles, setProfiles] = React.useState(null);
  const [error, setError] = React.useState(null);
  const [open, setOpen] = React.useState(null);

  React.useEffect(() => {
    api
      .getProfiles()
      .then((r) => setProfiles(r.profiles))
      .catch((e) => setError(e.message));
  }, []);

  return (
    <div style={{ maxWidth: 820, margin: "0 auto" }}>
      <PageIntro title={t("profiles.intro_title")} scope="daemon">
        {t("profiles.intro_body")}
      </PageIntro>
      {error && <Banner tone="error">{error}</Banner>}
      {!profiles && !error && <div>{t("common.loading")}</div>}
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {(profiles || []).map((p) => {
          const expanded = open === p.name;
          return (
            <div
              key={p.name}
              style={{
                background: "var(--card)",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius-lg)",
                boxShadow: "var(--shadow-xs)",
                overflow: "hidden",
              }}
            >
              <button
                onClick={() => setOpen(expanded ? null : p.name)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  width: "100%",
                  textAlign: "left",
                  border: "none",
                  background: "transparent",
                  cursor: "pointer",
                  padding: "12px 14px",
                }}
              >
                <KeyChip>{p.name}</KeyChip>
                {p.name === "merge" && (
                  <Badge tone="red" size="sm">
                    gh pr merge
                  </Badge>
                )}
                <span
                  style={{
                    flex: 1,
                    fontSize: 12.5,
                    color: "var(--muted-foreground)",
                    lineHeight: 1.5,
                  }}
                >
                  {p.summary}
                </span>
                <span
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: 11,
                    color: "var(--muted-foreground)",
                  }}
                >
                  {t("profiles.mode")}: {p.mode}
                </span>
                <span
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: 13,
                    color: "var(--muted-foreground)",
                    transform: expanded ? "rotate(90deg)" : "none",
                  }}
                >
                  ›
                </span>
              </button>
              {expanded && (
                <div
                  style={{
                    borderTop: "1px solid var(--border)",
                    background: "var(--muted)",
                    padding: "12px 14px",
                    display: "grid",
                    gridTemplateColumns: isMobile ? "1fr" : "1fr 1fr",
                    gap: 16,
                  }}
                >
                  <RuleList
                    title={t("profiles.allow_count", { n: p.allow.length })}
                    rules={p.allow}
                    tone="ok"
                  />
                  <RuleList
                    title={t("profiles.deny_count", { n: p.deny.length })}
                    rules={p.deny}
                    tone="no"
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function RuleList({ title, rules, tone }) {
  return (
    <div>
      <div
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: 10,
          letterSpacing: ".06em",
          textTransform: "uppercase",
          color:
            tone === "no"
              ? "var(--health-blocked-fg, var(--destructive))"
              : "var(--col-agent-fg, var(--primary))",
          marginBottom: 6,
        }}
      >
        {title}
      </div>
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 3,
          maxHeight: 260,
          overflow: "auto",
        }}
      >
        {rules.map((r, i) => (
          <code
            key={i}
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 11,
              color: "var(--foreground)",
            }}
          >
            {r}
          </code>
        ))}
      </div>
    </div>
  );
}
