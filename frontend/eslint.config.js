import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import tseslint from "typescript-eslint";

// TorrentMateUI ESLint flat config.
//
// typescript-eslint STRICT + type-checked linting over `src/`. The zero-`any`
// mandate (DESIGN §5.1) is enforced by `no-explicit-any` + the `no-unsafe-*`
// family, all set to `error`. `ban-ts-comment` requires a description so any
// escape hatch is self-documenting. `lint:ds` (DS-adherence oxlint) arrives in
// sub-phase 4.2.
export default tseslint.config(
  {
    ignores: ["dist", "node_modules", "coverage", "src/api/schema.d.ts"],
  },
  {
    files: ["**/*.{ts,tsx}"],
    extends: [
      ...tseslint.configs.strictTypeChecked,
      ...tseslint.configs.stylisticTypeChecked,
    ],
    languageOptions: {
      ecmaVersion: 2022,
      globals: globals.browser,
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      "react-hooks/rules-of-hooks": "error",
      "react-hooks/exhaustive-deps": "warn",
      "react-refresh/only-export-components": [
        "warn",
        { allowConstantExport: true },
      ],
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/no-unsafe-argument": "error",
      "@typescript-eslint/no-unsafe-assignment": "error",
      "@typescript-eslint/no-unsafe-call": "error",
      "@typescript-eslint/no-unsafe-member-access": "error",
      "@typescript-eslint/no-unsafe-return": "error",
      "@typescript-eslint/ban-ts-comment": [
        "error",
        {
          "ts-expect-error": "allow-with-description",
          "ts-ignore": "allow-with-description",
          "ts-nocheck": "allow-with-description",
          "ts-check": false,
          minimumDescriptionLength: 3,
        },
      ],
    },
  },

  // DS adherence — ported from the design-system _adherence config (oxlint lacks esquery).
  // Input, Button, Card, Switch prop-whitelist selectors removed: this project
  // ships shadcn/ui components of the same names (DESIGN-mandated — stock shadcn
  // inherits the theme via DS INTEGRATION.md), so the design-system primitive
  // whitelists only produce false positives. Only the app's own DS primitives
  // (StatusDot, LogLine, StatPanel, etc.) are enforced here.
  {
    files: ["src/**/*.{ts,tsx}"],
    rules: {
      "no-restricted-syntax": [
        "error",
        // Global token guards
        {
          selector: "Literal[value=/#[0-9a-fA-F]{3,8}\\b/]",
          message: "Raw hex color — use a design-system color token via var().",
        },
        {
          // Negative lookbehind for '[' avoids false-positives on Tailwind
          // arbitrary values like ring-[3px] or translate-y-[2px].
          selector: "Literal[value=/(?<!\\[)\\b\\d+px\\b(?!\\])/]",
          message:
            "Raw px value — use a design-system spacing token via var().",
        },
        {
          selector:
            'Literal[value=/font-family\\s*:\\s*(?![\'"\\\\"]?(?:Geist|Geist Mono))/i]',
          message:
            "Font not provided by the design system. Available: Geist, Geist Mono.",
        },

        // <Alert>
        {
          selector:
            "JSXOpeningElement[name.name='Alert'] > JSXAttribute > JSXIdentifier[name!=/^(?:tone|icon|title|className|children|key|ref|className|style|children)$/]",
          message:
            "<Alert> doesn't accept that prop. Declared props: tone, icon, title, className, children.",
        },
        {
          selector:
            "JSXOpeningElement[name.name='Alert'] > JSXAttribute[name.name='tone'] > Literal[value!=/^(?:success|warning|danger|info)$/]",
          message:
            "<Alert> tone must be one of 'success' | 'warning' | 'danger' | 'info'.",
        },

        // <Badge>
        {
          selector:
            "JSXOpeningElement[name.name='Badge'] > JSXAttribute > JSXIdentifier[name!=/^(?:tone|mono|dot|className|children|key|ref|className|style|children)$/]",
          message:
            "<Badge> doesn't accept that prop. Declared props: tone, mono, dot, className, children.",
        },

        // <DiskUsageBar>
        {
          selector:
            "JSXOpeningElement[name.name='DiskUsageBar'] > JSXAttribute > JSXIdentifier[name!=/^(?:name|used|total|icon|unit|className|key|ref|className|style|children)$/]",
          message:
            "<DiskUsageBar> doesn't accept that prop. Declared props: name, used, total, icon, unit, className.",
        },

        // <LogLine>
        {
          selector:
            "JSXOpeningElement[name.name='LogLine'] > JSXAttribute > JSXIdentifier[name!=/^(?:level|time|className|children|key|ref|className|style|children)$/]",
          message:
            "<LogLine> doesn't accept that prop. Declared props: level, time, className, children.",
        },

        // <MediaPoster>
        {
          selector:
            "JSXOpeningElement[name.name='MediaPoster'] > JSXAttribute > JSXIdentifier[name!=/^(?:title|year|kind|quality|src|status|interactive|className|key|ref|className|style|children)$/]",
          message:
            "<MediaPoster> doesn't accept that prop. Declared props: title, year, kind, quality, src, status, interactive, className.",
        },
        {
          selector:
            "JSXOpeningElement[name.name='MediaPoster'] > JSXAttribute[name.name='kind'] > Literal[value!=/^(?:movie|tv)$/]",
          message: "<MediaPoster> kind must be one of 'movie' | 'tv'.",
        },

        // <PipelineStep>
        {
          selector:
            "JSXOpeningElement[name.name='PipelineStep'] > JSXAttribute > JSXIdentifier[name!=/^(?:name|status|meta|key|ref|className|style|children)$/]",
          message:
            "<PipelineStep> doesn't accept that prop. Declared props: name, status, meta.",
        },

        // <Progress>
        {
          selector:
            "JSXOpeningElement[name.name='Progress'] > JSXAttribute > JSXIdentifier[name!=/^(?:value|max|tone|size|label|valueLabel|className|key|ref|className|style|children)$/]",
          message:
            "<Progress> doesn't accept that prop. Declared props: value, max, tone, size, label, valueLabel, className.",
        },
        {
          selector:
            "JSXOpeningElement[name.name='Progress'] > JSXAttribute[name.name='tone'] > Literal[value!=/^(?:primary|success|warning|danger|info)$/]",
          message:
            "<Progress> tone must be one of 'primary' | 'success' | 'warning' | 'danger' | 'info'.",
        },
        {
          selector:
            "JSXOpeningElement[name.name='Progress'] > JSXAttribute[name.name='size'] > Literal[value!=/^(?:sm|md|lg)$/]",
          message: "<Progress> size must be one of 'sm' | 'md' | 'lg'.",
        },

        // <RatioGauge>
        {
          selector:
            "JSXOpeningElement[name.name='RatioGauge'] > JSXAttribute > JSXIdentifier[name!=/^(?:value|target|size|label|className|key|ref|className|style|children)$/]",
          message:
            "<RatioGauge> doesn't accept that prop. Declared props: value, target, size, label, className.",
        },

        // <Spinner>
        {
          selector:
            "JSXOpeningElement[name.name='Spinner'] > JSXAttribute > JSXIdentifier[name!=/^(?:size|className|key|ref|className|style|children)$/]",
          message:
            "<Spinner> doesn't accept that prop. Declared props: size, className.",
        },

        // <StatPanel>
        {
          selector:
            "JSXOpeningElement[name.name='StatPanel'] > JSXAttribute > JSXIdentifier[name!=/^(?:label|icon|value|unit|delta|deltaDir|className|key|ref|className|style|children)$/]",
          message:
            "<StatPanel> doesn't accept that prop. Declared props: label, icon, value, unit, delta, deltaDir, className.",
        },
        {
          selector:
            "JSXOpeningElement[name.name='StatPanel'] > JSXAttribute[name.name='deltaDir'] > Literal[value!=/^(?:up|down|flat)$/]",
          message:
            "<StatPanel> deltaDir must be one of 'up' | 'down' | 'flat'.",
        },

        // <StatusDot>
        {
          selector:
            "JSXOpeningElement[name.name='StatusDot'] > JSXAttribute > JSXIdentifier[name!=/^(?:status|label|showLabel|className|key|ref|className|style|children)$/]",
          message:
            "<StatusDot> doesn't accept that prop. Declared props: status, label, showLabel, className.",
        },

        // <TemperatureBadge>
        {
          selector:
            "JSXOpeningElement[name.name='TemperatureBadge'] > JSXAttribute > JSXIdentifier[name!=/^(?:level|label|glyph|className|key|ref|className|style|children)$/]",
          message:
            "<TemperatureBadge> doesn't accept that prop. Declared props: level, label, glyph, className.",
        },

        // <Tooltip>
        {
          selector:
            "JSXOpeningElement[name.name='Tooltip'] > JSXAttribute > JSXIdentifier[name!=/^(?:content|side|kbd|className|children|key|ref|className|style|children)$/]",
          message:
            "<Tooltip> doesn't accept that prop. Declared props: content, side, kbd, className, children.",
        },
        {
          selector:
            "JSXOpeningElement[name.name='Tooltip'] > JSXAttribute[name.name='side'] > Literal[value!=/^(?:top|bottom)$/]",
          message: "<Tooltip> side must be one of 'top' | 'bottom'.",
        },
      ],
    },
  },
);
