/* @ds-bundle: {"format":3,"namespace":"KanbanMateDesignSystem_2463ad","components":[{"name":"Button","sourcePath":"components/core/Button.jsx"},{"name":"Card","sourcePath":"components/core/Card.jsx"},{"name":"Checkbox","sourcePath":"components/core/Checkbox.jsx"},{"name":"IconButton","sourcePath":"components/core/IconButton.jsx"},{"name":"Input","sourcePath":"components/core/Input.jsx"},{"name":"SegmentedControl","sourcePath":"components/core/SegmentedControl.jsx"},{"name":"Select","sourcePath":"components/core/Select.jsx"},{"name":"Switch","sourcePath":"components/core/Switch.jsx"},{"name":"Textarea","sourcePath":"components/core/Textarea.jsx"},{"name":"Avatar","sourcePath":"components/data-display/Avatar.jsx"},{"name":"Badge","sourcePath":"components/data-display/Badge.jsx"},{"name":"ColumnClassChip","sourcePath":"components/data-display/ColumnClassChip.jsx"},{"name":"HealthPill","sourcePath":"components/data-display/HealthPill.jsx"},{"name":"KeyChip","sourcePath":"components/data-display/KeyChip.jsx"},{"name":"ProfileTag","sourcePath":"components/data-display/ProfileTag.jsx"},{"name":"Banner","sourcePath":"components/feedback/Banner.jsx"},{"name":"Dialog","sourcePath":"components/feedback/Dialog.jsx"},{"name":"Tooltip","sourcePath":"components/feedback/Tooltip.jsx"},{"name":"ColumnCard","sourcePath":"components/kanban/ColumnCard.jsx"},{"name":"FindingItem","sourcePath":"components/kanban/FindingItem.jsx"},{"name":"TicketCard","sourcePath":"components/kanban/TicketCard.jsx"},{"name":"TransitionRow","sourcePath":"components/kanban/TransitionRow.jsx"}],"sourceHashes":{"components/core/Button.jsx":"7997a0392574","components/core/Card.jsx":"17b52ad53261","components/core/Checkbox.jsx":"6df5d6e0b9f4","components/core/IconButton.jsx":"3a9255942f24","components/core/Input.jsx":"adab195cbfa9","components/core/SegmentedControl.jsx":"eb0d8fee6907","components/core/Select.jsx":"58354504aca6","components/core/Switch.jsx":"80134edaa9e8","components/core/Textarea.jsx":"41077f4f0b32","components/data-display/Avatar.jsx":"a79240a0c4b0","components/data-display/Badge.jsx":"4766265b7d86","components/data-display/ColumnClassChip.jsx":"31cb4f79d76e","components/data-display/HealthPill.jsx":"aa86046bd421","components/data-display/KeyChip.jsx":"110ccc6ae2a2","components/data-display/ProfileTag.jsx":"ac1555b13c5b","components/feedback/Banner.jsx":"63a769204f0c","components/feedback/Dialog.jsx":"32f3eb250728","components/feedback/Tooltip.jsx":"27279807b28e","components/kanban/ColumnCard.jsx":"b9cd506b2051","components/kanban/FindingItem.jsx":"18316b2c1918","components/kanban/TicketCard.jsx":"a52607155343","components/kanban/TransitionRow.jsx":"6be67d7104c1","ui_kits/config/AppShell.jsx":"267b5beb46ff","ui_kits/config/ColumnsPanel.jsx":"64ad23cea7ee","ui_kits/config/SidePanels.jsx":"109c62d413db","ui_kits/config/TransitionsPanel.jsx":"6be64222022a","ui_kits/config/data.js":"224be31aabf5"},"inlinedExternals":[],"unexposedExports":[]} */

(() => {
  const __ds_ns = (window.KanbanMateDesignSystem_2463ad =
    window.KanbanMateDesignSystem_2463ad || {});

  const __ds_scope = {};

  __ds_ns.__errors = __ds_ns.__errors || [];

  // components/core/Button.jsx
  try {
    (() => {
      function _extends() {
        return (
          (_extends = Object.assign
            ? Object.assign.bind()
            : function (n) {
                for (var e = 1; e < arguments.length; e++) {
                  var t = arguments[e];
                  for (var r in t)
                    ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]);
                }
                return n;
              }),
          _extends.apply(null, arguments)
        );
      }
      /**
       * KanbanMate primary control. Variants map to intent: `primary` (signal-green,
       * the one committing action per view), `secondary` (bordered neutral), `ghost`
       * (text-only), `danger` (destructive — e.g. delete a column/transition).
       */
      function Button({
        children,
        variant = "secondary",
        size = "md",
        type = "button",
        disabled = false,
        loading = false,
        fullWidth = false,
        leadingIcon = null,
        trailingIcon = null,
        onClick,
        style,
        ...rest
      }) {
        const [hover, setHover] = React.useState(false);
        const [active, setActive] = React.useState(false);
        const [focus, setFocus] = React.useState(false);
        const sizes = {
          sm: {
            h: 32,
            px: "var(--space-5)",
            fs: "var(--text-sm)",
            gap: 6,
          },
          md: {
            h: 36,
            px: "var(--space-6)",
            fs: "var(--text-sm)",
            gap: 8,
          },
          lg: {
            h: 40,
            px: "var(--space-7)",
            fs: "var(--text-base)",
            gap: 8,
          },
        };
        const s = sizes[size] || sizes.md;

        /* shadcn variants: default=primary, outline=secondary, ghost, destructive=danger */
        const palettes = {
          primary: {
            bg: "var(--primary)",
            bgHover: "color-mix(in oklch, var(--primary) 90%, transparent)",
            bgActive: "color-mix(in oklch, var(--primary) 82%, black)",
            fg: "var(--primary-foreground)",
            bd: "transparent",
            shadow: "var(--shadow-xs)",
          },
          secondary: {
            bg: "var(--card)",
            bgHover: "var(--accent)",
            bgActive: "var(--accent)",
            fg: "var(--accent-foreground)",
            bd: "var(--border)",
            shadow: "var(--shadow-xs)",
          },
          ghost: {
            bg: "transparent",
            bgHover: "var(--accent)",
            bgActive: "var(--accent)",
            fg: "var(--foreground)",
            bd: "transparent",
            shadow: "none",
          },
          danger: {
            bg: "var(--destructive)",
            bgHover: "color-mix(in oklch, var(--destructive) 90%, transparent)",
            bgActive: "color-mix(in oklch, var(--destructive) 82%, black)",
            fg: "var(--destructive-foreground)",
            bd: "transparent",
            shadow: "var(--shadow-xs)",
          },
        };
        const p = palettes[variant] || palettes.secondary;
        const isDisabled = disabled || loading;
        const bg = active ? p.bgActive : hover ? p.bgHover : p.bg;
        return /*#__PURE__*/ React.createElement(
          "button",
          _extends(
            {
              type: type,
              disabled: isDisabled,
              onClick: onClick,
              onMouseEnter: () => setHover(true),
              onMouseLeave: () => {
                setHover(false);
                setActive(false);
              },
              onMouseDown: () => setActive(true),
              onMouseUp: () => setActive(false),
              onFocus: () => setFocus(true),
              onBlur: () => setFocus(false),
              style: {
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                gap: s.gap,
                height: s.h,
                padding: `0 ${s.px}`,
                width: fullWidth ? "100%" : "auto",
                fontFamily: "var(--font-sans)",
                fontSize: s.fs,
                fontWeight: "var(--weight-medium)",
                lineHeight: 1,
                whiteSpace: "nowrap",
                color: isDisabled ? "var(--muted-foreground)" : p.fg,
                background: isDisabled ? "var(--muted)" : bg,
                border: `1px solid ${isDisabled ? "var(--border)" : p.bd}`,
                borderRadius: "var(--radius-md)",
                cursor: isDisabled ? "not-allowed" : "pointer",
                opacity: isDisabled ? 0.5 : 1,
                boxShadow:
                  focus && !isDisabled
                    ? "var(--shadow-focus)"
                    : isDisabled
                      ? "none"
                      : p.shadow,
                transition:
                  "background var(--dur-fast) var(--ease-standard), box-shadow var(--dur-fast) var(--ease-standard)",
                outline: "none",
                ...style,
              },
            },
            rest,
          ),
          loading && /*#__PURE__*/ React.createElement(Spinner, null),
          !loading && leadingIcon,
          children,
          !loading && trailingIcon,
        );
      }
      function Spinner() {
        return /*#__PURE__*/ React.createElement(
          "span",
          {
            style: {
              width: 13,
              height: 13,
              borderRadius: "50%",
              border: "2px solid currentColor",
              borderTopColor: "transparent",
              display: "inline-block",
              animation: "km-spin 0.6s linear infinite",
              opacity: 0.9,
            },
          },
          /*#__PURE__*/ React.createElement(
            "style",
            null,
            "@keyframes km-spin{to{transform:rotate(360deg)}}",
          ),
        );
      }
      Object.assign(__ds_scope, { Button });
    })();
  } catch (e) {
    __ds_ns.__errors.push({
      path: "components/core/Button.jsx",
      error: String((e && e.message) || e),
    });
  }

  // components/core/Card.jsx
  try {
    (() => {
      /**
       * Generic surface container — the white panel with a 1px border that everything
       * sits in. `padding` and `header`/`footer` slots cover most config-panel needs.
       */
      function Card({
        children,
        header = null,
        footer = null,
        padding = "md",
        interactive = false,
        onClick,
        style,
      }) {
        const [hover, setHover] = React.useState(false);
        const pads = {
          none: 0,
          sm: "var(--space-5)",
          md: "var(--space-7)",
          lg: "var(--space-8)",
        };
        const pad = pads[padding] != null ? pads[padding] : pads.md;
        return /*#__PURE__*/ React.createElement(
          "div",
          {
            onClick: onClick,
            onMouseEnter: () => interactive && setHover(true),
            onMouseLeave: () => interactive && setHover(false),
            style: {
              background: "var(--card)",
              border: `1px solid ${hover ? "var(--border)" : "var(--border)"}`,
              borderRadius: "var(--radius-xl)",
              boxShadow: hover ? "var(--shadow-sm)" : "var(--shadow-xs)",
              color: "var(--card-foreground)",
              cursor: interactive ? "pointer" : "default",
              overflow: "hidden",
              transition:
                "border-color var(--dur-fast) var(--ease-standard), box-shadow var(--dur-fast) var(--ease-standard)",
              ...style,
            },
          },
          header &&
            /*#__PURE__*/ React.createElement(
              "div",
              {
                style: {
                  padding: "14px 20px",
                  borderBottom: "1px solid var(--border)",
                  fontFamily: "var(--font-display)",
                  fontWeight: 600,
                  fontSize: "var(--text-md)",
                  letterSpacing: "var(--tracking-tight)",
                  color: "var(--foreground)",
                },
              },
              header,
            ),
          /*#__PURE__*/ React.createElement(
            "div",
            {
              style: {
                padding: pad,
              },
            },
            children,
          ),
          footer &&
            /*#__PURE__*/ React.createElement(
              "div",
              {
                style: {
                  padding: "14px 20px",
                  borderTop: "1px solid var(--border)",
                  background: "var(--muted)",
                },
              },
              footer,
            ),
        );
      }
      Object.assign(__ds_scope, { Card });
    })();
  } catch (e) {
    __ds_ns.__errors.push({
      path: "components/core/Card.jsx",
      error: String((e && e.message) || e),
    });
  }

  // components/core/Checkbox.jsx
  try {
    (() => {
      function _extends() {
        return (
          (_extends = Object.assign
            ? Object.assign.bind()
            : function (n) {
                for (var e = 1; e < arguments.length; e++) {
                  var t = arguments[e];
                  for (var r in t)
                    ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]);
                }
                return n;
              }),
          _extends.apply(null, arguments)
        );
      }
      /** Checkbox with the brand check colour. For multi-select / opt-in rows. */
      function Checkbox({
        checked = false,
        indeterminate = false,
        disabled = false,
        label = null,
        onChange,
        style,
        ...rest
      }) {
        const [focus, setFocus] = React.useState(false);
        const on = checked || indeterminate;
        const box = /*#__PURE__*/ React.createElement(
          "button",
          _extends(
            {
              type: "button",
              role: "checkbox",
              "aria-checked": indeterminate ? "mixed" : checked,
              disabled: disabled,
              onClick: () => !disabled && onChange && onChange(!checked),
              onFocus: () => setFocus(true),
              onBlur: () => setFocus(false),
              style: {
                width: 17,
                height: 17,
                flex: "none",
                padding: 0,
                display: "grid",
                placeItems: "center",
                borderRadius: "var(--radius-sm)",
                cursor: disabled ? "not-allowed" : "pointer",
                background: on ? "var(--primary)" : "var(--card)",
                border: `1px solid ${on ? "var(--primary)" : "var(--input)"}`,
                boxShadow: focus ? "var(--shadow-focus)" : "var(--shadow-2xs)",
                outline: "none",
                opacity: disabled ? 0.5 : 1,
                transition:
                  "background var(--dur-fast) var(--ease-standard), border-color var(--dur-fast) var(--ease-standard)",
              },
            },
            rest,
          ),
          indeterminate
            ? /*#__PURE__*/ React.createElement("span", {
                style: {
                  width: 8,
                  height: 2,
                  background: "var(--primary-foreground)",
                  borderRadius: 1,
                },
              })
            : checked
              ? /*#__PURE__*/ React.createElement(
                  "svg",
                  {
                    width: "11",
                    height: "11",
                    viewBox: "0 0 12 12",
                    fill: "none",
                  },
                  /*#__PURE__*/ React.createElement("path", {
                    d: "M2.5 6.2L4.8 8.5L9.5 3.5",
                    stroke: "var(--primary-foreground)",
                    strokeWidth: "1.8",
                    strokeLinecap: "round",
                    strokeLinejoin: "round",
                  }),
                )
              : null,
        );
        if (!label) return box;
        return /*#__PURE__*/ React.createElement(
          "label",
          {
            style: {
              display: "inline-flex",
              alignItems: "center",
              gap: "var(--space-4)",
              cursor: disabled ? "not-allowed" : "pointer",
              fontSize: "var(--text-sm)",
              color: "var(--foreground)",
              ...style,
            },
          },
          box,
          label,
        );
      }
      Object.assign(__ds_scope, { Checkbox });
    })();
  } catch (e) {
    __ds_ns.__errors.push({
      path: "components/core/Checkbox.jsx",
      error: String((e && e.message) || e),
    });
  }

  // components/core/IconButton.jsx
  try {
    (() => {
      function _extends() {
        return (
          (_extends = Object.assign
            ? Object.assign.bind()
            : function (n) {
                for (var e = 1; e < arguments.length; e++) {
                  var t = arguments[e];
                  for (var r in t)
                    ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]);
                }
                return n;
              }),
          _extends.apply(null, arguments)
        );
      }
      /**
       * Square icon-only button. Same interaction language as Button but for a single
       * glyph — board toolbar actions, row controls (drag handle, delete, expand).
       * Always pass `aria-label`.
       */
      function IconButton({
        children,
        variant = "ghost",
        size = "md",
        disabled = false,
        active = false,
        onClick,
        style,
        ...rest
      }) {
        const [hover, setHover] = React.useState(false);
        const [press, setPress] = React.useState(false);
        const [focus, setFocus] = React.useState(false);
        const dims = {
          sm: 26,
          md: 32,
          lg: 38,
        };
        const d = dims[size] || dims.md;
        const palettes = {
          ghost: {
            bg: "transparent",
            bgHover: "var(--accent)",
            fg: "var(--muted-foreground)",
            fgHover: "var(--accent-foreground)",
            bd: "transparent",
          },
          secondary: {
            bg: "var(--card)",
            bgHover: "var(--accent)",
            fg: "var(--foreground)",
            fgHover: "var(--accent-foreground)",
            bd: "var(--border)",
          },
          danger: {
            bg: "transparent",
            bgHover: "var(--health-blocked-bg)",
            fg: "var(--muted-foreground)",
            fgHover: "var(--destructive)",
            bd: "transparent",
          },
        };
        const p = palettes[variant] || palettes.ghost;
        const isActive = active || press;
        return /*#__PURE__*/ React.createElement(
          "button",
          _extends(
            {
              type: "button",
              disabled: disabled,
              onClick: onClick,
              onMouseEnter: () => setHover(true),
              onMouseLeave: () => {
                setHover(false);
                setPress(false);
              },
              onMouseDown: () => setPress(true),
              onMouseUp: () => setPress(false),
              onFocus: () => setFocus(true),
              onBlur: () => setFocus(false),
              style: {
                display: "inline-grid",
                placeItems: "center",
                width: d,
                height: d,
                flex: "none",
                color: hover || isActive ? p.fgHover : p.fg,
                background: isActive
                  ? "var(--accent)"
                  : hover
                    ? p.bgHover
                    : p.bg,
                border: `1px solid ${p.bd}`,
                borderRadius: "var(--radius-md)",
                cursor: disabled ? "not-allowed" : "pointer",
                opacity: disabled ? 0.45 : 1,
                boxShadow: focus ? "var(--shadow-focus)" : "none",
                outline: "none",
                transition:
                  "background var(--dur-fast) var(--ease-standard), color var(--dur-fast) var(--ease-standard)",
                ...style,
              },
            },
            rest,
          ),
          children,
        );
      }
      Object.assign(__ds_scope, { IconButton });
    })();
  } catch (e) {
    __ds_ns.__errors.push({
      path: "components/core/IconButton.jsx",
      error: String((e && e.message) || e),
    });
  }

  // components/core/Input.jsx
  try {
    (() => {
      function _extends() {
        return (
          (_extends = Object.assign
            ? Object.assign.bind()
            : function (n) {
                for (var e = 1; e < arguments.length; e++) {
                  var t = arguments[e];
                  for (var r in t)
                    ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]);
                }
                return n;
              }),
          _extends.apply(null, arguments)
        );
      }
      /**
       * Text input. Mono variant for literal identifiers the daemon reads (column
       * keys, permission_mode, placeholder tokens) so the field reads like the config
       * file. `invalid` paints the error border used by validation findings.
       */
      function Input({
        value,
        defaultValue,
        placeholder,
        type = "text",
        mono = false,
        size = "md",
        invalid = false,
        disabled = false,
        leadingAddon = null,
        onChange,
        style,
        ...rest
      }) {
        const [focus, setFocus] = React.useState(false);
        const sizes = {
          sm: {
            h: 32,
            fs: "var(--text-sm)",
          },
          md: {
            h: 36,
            fs: "var(--text-sm)",
          },
          lg: {
            h: 40,
            fs: "var(--text-base)",
          },
        };
        const s = sizes[size] || sizes.md;
        const border = invalid
          ? "var(--destructive)"
          : focus
            ? "var(--ring)"
            : "var(--input)";
        const field = /*#__PURE__*/ React.createElement(
          "input",
          _extends(
            {
              type: type,
              value: value,
              defaultValue: defaultValue,
              placeholder: placeholder,
              disabled: disabled,
              onChange: onChange,
              onFocus: () => setFocus(true),
              onBlur: () => setFocus(false),
              style: {
                flex: 1,
                minWidth: 0,
                height: s.h,
                padding: `0 ${leadingAddon ? "8px" : "var(--space-5)"}`,
                fontFamily: mono ? "var(--font-mono)" : "var(--font-sans)",
                fontSize: s.fs,
                color: "var(--foreground)",
                background: "transparent",
                border: "none",
                outline: "none",
                width: "100%",
              },
            },
            rest,
          ),
        );
        return /*#__PURE__*/ React.createElement(
          "div",
          {
            style: {
              display: "flex",
              alignItems: "center",
              background: disabled ? "var(--muted)" : "var(--card)",
              border: `1px solid ${border}`,
              borderRadius: "var(--radius-md)",
              boxShadow: focus
                ? invalid
                  ? "0 0 0 3px color-mix(in oklch, var(--destructive) 28%, transparent)"
                  : "var(--shadow-focus)"
                : "var(--shadow-2xs)",
              opacity: disabled ? 0.6 : 1,
              transition:
                "border-color var(--dur-fast) var(--ease-standard), box-shadow var(--dur-fast) var(--ease-standard)",
              ...style,
            },
          },
          leadingAddon &&
            /*#__PURE__*/ React.createElement(
              "span",
              {
                style: {
                  paddingLeft: "var(--space-5)",
                  color: "var(--muted-foreground)",
                  fontFamily: "var(--font-mono)",
                  fontSize: s.fs,
                  whiteSpace: "nowrap",
                },
              },
              leadingAddon,
            ),
          field,
        );
      }
      Object.assign(__ds_scope, { Input });
    })();
  } catch (e) {
    __ds_ns.__errors.push({
      path: "components/core/Input.jsx",
      error: String((e && e.message) || e),
    });
  }

  // components/core/SegmentedControl.jsx
  try {
    (() => {
      /**
       * Segmented control — the inline single-choice picker used across the config UI
       * (e.g. column_class reactive/inert, a small view toggle). Mono labels by
       * default since the options are usually literal config values.
       */
      function SegmentedControl({
        options = [],
        value,
        onChange,
        size = "md",
        mono = false,
        fullWidth = false,
        style,
      }) {
        const sizes = {
          sm: {
            h: 26,
            fs: "var(--text-xs)",
            px: 10,
          },
          md: {
            h: 32,
            fs: "var(--text-sm)",
            px: 12,
          },
        };
        const s = sizes[size] || sizes.md;
        return /*#__PURE__*/ React.createElement(
          "div",
          {
            role: "tablist",
            style: {
              display: "inline-flex",
              width: fullWidth ? "100%" : "auto",
              padding: 3,
              gap: 2,
              background: "var(--muted)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-lg)",
              ...style,
            },
          },
          options.map((o) => {
            const opt =
              typeof o === "string"
                ? {
                    value: o,
                    label: o,
                  }
                : o;
            const selected = opt.value === value;
            return /*#__PURE__*/ React.createElement(
              "button",
              {
                key: opt.value,
                type: "button",
                role: "tab",
                "aria-selected": selected,
                onClick: () => onChange && onChange(opt.value),
                style: {
                  flex: fullWidth ? 1 : "none",
                  height: s.h,
                  padding: `0 ${s.px}px`,
                  fontFamily: mono ? "var(--font-mono)" : "var(--font-sans)",
                  fontSize: s.fs,
                  fontWeight: "var(--weight-medium)",
                  whiteSpace: "nowrap",
                  color: selected
                    ? "var(--foreground)"
                    : "var(--muted-foreground)",
                  background: selected ? "var(--card)" : "transparent",
                  border: `1px solid ${selected ? "var(--border)" : "transparent"}`,
                  borderRadius: "var(--radius-sm)",
                  cursor: "pointer",
                  boxShadow: selected ? "var(--shadow-xs)" : "none",
                  transition:
                    "background var(--dur-fast) var(--ease-standard), color var(--dur-fast) var(--ease-standard)",
                },
              },
              opt.label,
            );
          }),
        );
      }
      Object.assign(__ds_scope, { SegmentedControl });
    })();
  } catch (e) {
    __ds_ns.__errors.push({
      path: "components/core/SegmentedControl.jsx",
      error: String((e && e.message) || e),
    });
  }

  // components/core/Select.jsx
  try {
    (() => {
      function _extends() {
        return (
          (_extends = Object.assign
            ? Object.assign.bind()
            : function (n) {
                for (var e = 1; e < arguments.length; e++) {
                  var t = arguments[e];
                  for (var r in t)
                    ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]);
                }
                return n;
              }),
          _extends.apply(null, arguments)
        );
      }
      /**
       * Native select styled to KanbanMate. Used for enum config fields — profile,
       * permission_mode, advance directive, column_class. Mono by default since the
       * options are literal values.
       */
      function Select({
        value,
        defaultValue,
        options = [],
        size = "md",
        mono = true,
        invalid = false,
        disabled = false,
        onChange,
        style,
        ...rest
      }) {
        const [focus, setFocus] = React.useState(false);
        const sizes = {
          sm: {
            h: 32,
            fs: "var(--text-sm)",
          },
          md: {
            h: 36,
            fs: "var(--text-sm)",
          },
          lg: {
            h: 40,
            fs: "var(--text-base)",
          },
        };
        const s = sizes[size] || sizes.md;
        const border = invalid
          ? "var(--destructive)"
          : focus
            ? "var(--ring)"
            : "var(--input)";
        return /*#__PURE__*/ React.createElement(
          "div",
          {
            style: {
              position: "relative",
              display: "inline-flex",
              ...style,
            },
          },
          /*#__PURE__*/ React.createElement(
            "select",
            _extends(
              {
                value: value,
                defaultValue: defaultValue,
                disabled: disabled,
                onChange: onChange,
                onFocus: () => setFocus(true),
                onBlur: () => setFocus(false),
                style: {
                  appearance: "none",
                  WebkitAppearance: "none",
                  height: s.h,
                  padding: "0 30px 0 var(--space-5)",
                  width: "100%",
                  fontFamily: mono ? "var(--font-mono)" : "var(--font-sans)",
                  fontSize: s.fs,
                  color: "var(--foreground)",
                  background: disabled ? "var(--muted)" : "var(--card)",
                  border: `1px solid ${border}`,
                  borderRadius: "var(--radius-md)",
                  boxShadow: focus
                    ? "var(--shadow-focus)"
                    : "var(--shadow-2xs)",
                  cursor: disabled ? "not-allowed" : "pointer",
                  opacity: disabled ? 0.6 : 1,
                  outline: "none",
                  transition:
                    "border-color var(--dur-fast) var(--ease-standard), box-shadow var(--dur-fast) var(--ease-standard)",
                },
              },
              rest,
            ),
            options.map((o) => {
              const opt =
                typeof o === "string"
                  ? {
                      value: o,
                      label: o,
                    }
                  : o;
              return /*#__PURE__*/ React.createElement(
                "option",
                {
                  key: opt.value,
                  value: opt.value,
                  disabled: opt.disabled,
                },
                opt.label,
              );
            }),
          ),
          /*#__PURE__*/ React.createElement(
            "span",
            {
              style: {
                position: "absolute",
                right: 10,
                top: "50%",
                transform: "translateY(-50%)",
                pointerEvents: "none",
                color: "var(--muted-foreground)",
                fontSize: 11,
              },
            },
            "\u25BE",
          ),
        );
      }
      Object.assign(__ds_scope, { Select });
    })();
  } catch (e) {
    __ds_ns.__errors.push({
      path: "components/core/Select.jsx",
      error: String((e && e.message) || e),
    });
  }

  // components/core/Switch.jsx
  try {
    (() => {
      function _extends() {
        return (
          (_extends = Object.assign
            ? Object.assign.bind()
            : function (n) {
                for (var e = 1; e < arguments.length; e++) {
                  var t = arguments[e];
                  for (var r in t)
                    ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]);
                }
                return n;
              }),
          _extends.apply(null, arguments)
        );
      }
      /** On/off switch. Green when on (the brand "go" colour). For boolean config
       * flags like interactive-only / unattended. */
      function Switch({
        checked = false,
        disabled = false,
        onChange,
        size = "md",
        style,
        ...rest
      }) {
        const [focus, setFocus] = React.useState(false);
        const dims = {
          sm: {
            w: 30,
            h: 17,
            k: 13,
          },
          md: {
            w: 38,
            h: 22,
            k: 17,
          },
        };
        const d = dims[size] || dims.md;
        return /*#__PURE__*/ React.createElement(
          "button",
          _extends(
            {
              type: "button",
              role: "switch",
              "aria-checked": checked,
              disabled: disabled,
              onClick: () => !disabled && onChange && onChange(!checked),
              onFocus: () => setFocus(true),
              onBlur: () => setFocus(false),
              style: {
                position: "relative",
                width: d.w,
                height: d.h,
                flex: "none",
                padding: 0,
                border: "none",
                borderRadius: "var(--radius-pill)",
                cursor: disabled ? "not-allowed" : "pointer",
                background: checked ? "var(--primary)" : "var(--input)",
                opacity: disabled ? 0.5 : 1,
                boxShadow: focus ? "var(--shadow-focus)" : "var(--shadow-2xs)",
                outline: "none",
                transition: "background var(--dur-base) var(--ease-standard)",
                ...style,
              },
            },
            rest,
          ),
          /*#__PURE__*/ React.createElement("span", {
            style: {
              position: "absolute",
              top: (d.h - d.k) / 2,
              left: checked ? d.w - d.k - (d.h - d.k) / 2 : (d.h - d.k) / 2,
              width: d.k,
              height: d.k,
              borderRadius: "50%",
              background: "var(--card)",
              boxShadow: "var(--shadow-sm)",
              transition: "left var(--dur-base) var(--ease-out)",
            },
          }),
        );
      }
      Object.assign(__ds_scope, { Switch });
    })();
  } catch (e) {
    __ds_ns.__errors.push({
      path: "components/core/Switch.jsx",
      error: String((e && e.message) || e),
    });
  }

  // components/core/Textarea.jsx
  try {
    (() => {
      function _extends() {
        return (
          (_extends = Object.assign
            ? Object.assign.bind()
            : function (n) {
                for (var e = 1; e < arguments.length; e++) {
                  var t = arguments[e];
                  for (var r in t)
                    ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]);
                }
                return n;
              }),
          _extends.apply(null, arguments)
        );
      }
      /**
       * Multi-line text for prompts and scripts. Mono by default (prompts carry slash
       * commands + {{tokens}}). Auto-shows the error border for finding-linked fields.
       */
      function Textarea({
        value,
        defaultValue,
        placeholder,
        rows = 3,
        mono = true,
        invalid = false,
        disabled = false,
        onChange,
        style,
        ...rest
      }) {
        const [focus, setFocus] = React.useState(false);
        const border = invalid
          ? "var(--destructive)"
          : focus
            ? "var(--ring)"
            : "var(--input)";
        return /*#__PURE__*/ React.createElement(
          "textarea",
          _extends(
            {
              value: value,
              defaultValue: defaultValue,
              placeholder: placeholder,
              rows: rows,
              disabled: disabled,
              onChange: onChange,
              onFocus: () => setFocus(true),
              onBlur: () => setFocus(false),
              style: {
                width: "100%",
                padding: "var(--space-5)",
                resize: "vertical",
                fontFamily: mono ? "var(--font-mono)" : "var(--font-sans)",
                fontSize: "var(--text-sm)",
                lineHeight: 1.6,
                color: "var(--foreground)",
                background: disabled ? "var(--muted)" : "var(--card)",
                border: `1px solid ${border}`,
                borderRadius: "var(--radius-md)",
                boxShadow: focus ? "var(--shadow-focus)" : "var(--shadow-2xs)",
                outline: "none",
                transition:
                  "border-color var(--dur-fast) var(--ease-standard), box-shadow var(--dur-fast) var(--ease-standard)",
                ...style,
              },
            },
            rest,
          ),
        );
      }
      Object.assign(__ds_scope, { Textarea });
    })();
  } catch (e) {
    __ds_ns.__errors.push({
      path: "components/core/Textarea.jsx",
      error: String((e && e.message) || e),
    });
  }

  // components/data-display/Avatar.jsx
  try {
    (() => {
      /**
       * Small identity avatar — an agent (mono initials on a tinted square, the agent
       * violet) or a human (GitHub-style rounded). Used on ticket cards and agent rows.
       */
      function Avatar({
        label = "?",
        kind = "human",
        src = null,
        size = "md",
        style,
      }) {
        const sizes = {
          xs: 18,
          sm: 22,
          md: 28,
          lg: 36,
        };
        const d = sizes[size] || sizes.md;
        const isAgent = kind === "agent";
        const initials = String(label).trim().slice(0, 2).toUpperCase();
        return /*#__PURE__*/ React.createElement(
          "span",
          {
            title: label,
            style: {
              display: "inline-grid",
              placeItems: "center",
              width: d,
              height: d,
              flex: "none",
              borderRadius: isAgent ? "var(--radius-sm)" : "50%",
              overflow: "hidden",
              background: isAgent
                ? "var(--col-agent-bg)"
                : "var(--surface-sunken)",
              border: `1px solid ${isAgent ? "var(--col-agent-bd)" : "var(--border-subtle)"}`,
              color: isAgent ? "var(--col-agent-fg)" : "var(--text-muted)",
              fontFamily: "var(--font-mono)",
              fontSize: d <= 22 ? 9 : 11,
              fontWeight: 600,
              ...style,
            },
          },
          src
            ? /*#__PURE__*/ React.createElement("img", {
                src: src,
                alt: label,
                style: {
                  width: "100%",
                  height: "100%",
                  objectFit: "cover",
                },
              })
            : initials,
        );
      }
      Object.assign(__ds_scope, { Avatar });
    })();
  } catch (e) {
    __ds_ns.__errors.push({
      path: "components/data-display/Avatar.jsx",
      error: String((e && e.message) || e),
    });
  }

  // components/data-display/Badge.jsx
  try {
    (() => {
      /**
       * Generic small status/label pill. For semantic tones use HealthPill /
       * ColumnClassChip / ProfileTag instead — this is the neutral primitive they and
       * everything else build on (counts, "default", "no profile", etc).
       */
      function Badge({
        children,
        tone = "neutral",
        variant = "soft",
        size = "md",
        dot = false,
        mono = false,
        style,
      }) {
        const tones = {
          neutral: {
            fg: "var(--text-muted)",
            bg: "var(--surface-sunken)",
            bd: "var(--border-subtle)",
            solid: "var(--gray-500)",
          },
          accent: {
            fg: "var(--accent-text)",
            bg: "var(--accent-weak)",
            bd: "var(--accent-weak-border)",
            solid: "var(--accent)",
          },
          red: {
            fg: "var(--red-700)",
            bg: "var(--red-50)",
            bd: "var(--red-300)",
            solid: "var(--red-500)",
          },
          amber: {
            fg: "var(--amber-700)",
            bg: "var(--amber-50)",
            bd: "var(--amber-300)",
            solid: "var(--amber-500)",
          },
          blue: {
            fg: "var(--blue-700)",
            bg: "var(--blue-50)",
            bd: "var(--blue-300)",
            solid: "var(--blue-500)",
          },
          violet: {
            fg: "var(--violet-700)",
            bg: "var(--violet-50)",
            bd: "var(--violet-300)",
            solid: "var(--violet-500)",
          },
        };
        const t = tones[tone] || tones.neutral;
        const sizes = {
          sm: {
            h: 18,
            px: 7,
            fs: "var(--text-2xs)",
          },
          md: {
            h: 22,
            px: 9,
            fs: "var(--text-xs)",
          },
        };
        const s = sizes[size] || sizes.md;
        const solid = variant === "solid";
        return /*#__PURE__*/ React.createElement(
          "span",
          {
            style: {
              display: "inline-flex",
              alignItems: "center",
              gap: 5,
              height: s.h,
              padding: `0 ${s.px}px`,
              fontFamily: mono ? "var(--font-mono)" : "var(--font-sans)",
              fontSize: s.fs,
              fontWeight: "var(--weight-semibold)",
              lineHeight: 1,
              whiteSpace: "nowrap",
              color: solid ? "var(--primary-foreground)" : t.fg,
              background: solid ? t.solid : t.bg,
              border: `1px solid ${solid ? "transparent" : t.bd}`,
              borderRadius: "var(--radius-sm)",
              ...style,
            },
          },
          dot &&
            /*#__PURE__*/ React.createElement("span", {
              style: {
                width: 6,
                height: 6,
                borderRadius: "50%",
                background: solid ? "#fff" : t.solid,
              },
            }),
          children,
        );
      }
      Object.assign(__ds_scope, { Badge });
    })();
  } catch (e) {
    __ds_ns.__errors.push({
      path: "components/data-display/Badge.jsx",
      error: String((e && e.message) || e),
    });
  }

  // components/data-display/ColumnClassChip.jsx
  try {
    (() => {
      const CLASSES = {
        agent: {
          fg: "var(--col-agent-fg)",
          bg: "var(--col-agent-bg)",
          bd: "var(--col-agent-bd)",
          solid: "var(--col-agent-solid)",
        },
        reactive: {
          fg: "var(--col-reactive-fg)",
          bg: "var(--col-reactive-bg)",
          bd: "var(--col-reactive-bd)",
          solid: "var(--col-reactive-solid)",
        },
        inert: {
          fg: "var(--col-inert-fg)",
          bg: "var(--col-inert-bg)",
          bd: "var(--col-inert-bd)",
          solid: "var(--col-inert-solid)",
        },
      };

      /**
       * Marks a board column's class — agent (launches an agent), reactive (mechanical
       * side-effect), or inert (human gate / terminal). Square-dot + mono label.
       */
      function ColumnClassChip({ columnClass = "inert", size = "md", style }) {
        const c = CLASSES[columnClass] || CLASSES.inert;
        const sizes = {
          sm: {
            h: 18,
            px: 7,
            fs: "var(--text-2xs)",
          },
          md: {
            h: 22,
            px: 9,
            fs: "var(--text-xs)",
          },
        };
        const s = sizes[size] || sizes.md;
        return /*#__PURE__*/ React.createElement(
          "span",
          {
            style: {
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              height: s.h,
              padding: `0 ${s.px}px`,
              fontFamily: "var(--font-mono)",
              fontSize: s.fs,
              fontWeight: "var(--weight-semibold)",
              color: c.fg,
              background: c.bg,
              border: `1px solid ${c.bd}`,
              borderRadius: "var(--radius-xs)",
              whiteSpace: "nowrap",
              ...style,
            },
          },
          /*#__PURE__*/ React.createElement("span", {
            style: {
              width: 7,
              height: 7,
              borderRadius: 2,
              background: c.solid,
              flex: "none",
            },
          }),
          columnClass,
        );
      }
      Object.assign(__ds_scope, { ColumnClassChip });
    })();
  } catch (e) {
    __ds_ns.__errors.push({
      path: "components/data-display/ColumnClassChip.jsx",
      error: String((e && e.message) || e),
    });
  }

  // components/data-display/HealthPill.jsx
  try {
    (() => {
      const HEALTH = {
        INACTIVE: {
          fg: "var(--health-inactive-fg)",
          bg: "var(--health-inactive-bg)",
          bd: "var(--health-inactive-bd)",
          github: "Inactive",
        },
        BLOCKED: {
          fg: "var(--health-blocked-fg)",
          bg: "var(--health-blocked-bg)",
          bd: "var(--health-blocked-bd)",
          github: "Off track",
        },
        WAITING: {
          fg: "var(--health-waiting-fg)",
          bg: "var(--health-waiting-bg)",
          bd: "var(--health-waiting-bd)",
          github: "At risk",
        },
        ACTIVE: {
          fg: "var(--health-active-fg)",
          bg: "var(--health-active-bg)",
          bd: "var(--health-active-bd)",
          github: "On track",
        },
        COMPLETE: {
          fg: "var(--health-complete-fg)",
          bg: "var(--health-complete-bg)",
          bd: "var(--health-complete-bd)",
          github: "Complete",
        },
      };

      /**
       * The KanbanMate dashboard health pill — its single most important status
       * signal. `status` is one of the five health states; `pulse` animates the dot
       * for the live ACTIVE state.
       */
      function HealthPill({
        status = "ACTIVE",
        size = "md",
        pulse = false,
        showGithub = false,
        style,
      }) {
        const h = HEALTH[status] || HEALTH.INACTIVE;
        const sizes = {
          sm: {
            h: 20,
            px: 8,
            fs: "var(--text-2xs)",
            dot: 6,
          },
          md: {
            h: 24,
            px: 10,
            fs: "var(--text-xs)",
            dot: 7,
          },
          lg: {
            h: 30,
            px: 13,
            fs: "var(--text-sm)",
            dot: 8,
          },
        };
        const s = sizes[size] || sizes.md;
        return /*#__PURE__*/ React.createElement(
          "span",
          {
            style: {
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
            },
          },
          /*#__PURE__*/ React.createElement(
            "span",
            {
              style: {
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                height: s.h,
                padding: `0 ${s.px}px`,
                fontFamily: "var(--font-mono)",
                fontSize: s.fs,
                fontWeight: "var(--weight-semibold)",
                letterSpacing: "0.04em",
                color: h.fg,
                background: h.bg,
                border: `1px solid ${h.bd}`,
                borderRadius: "var(--radius-pill)",
                whiteSpace: "nowrap",
                ...style,
              },
            },
            /*#__PURE__*/ React.createElement(
              "span",
              {
                style: {
                  position: "relative",
                  width: s.dot,
                  height: s.dot,
                  flex: "none",
                },
              },
              /*#__PURE__*/ React.createElement("span", {
                style: {
                  position: "absolute",
                  inset: 0,
                  borderRadius: "50%",
                  background: h.fg,
                },
              }),
              pulse &&
                /*#__PURE__*/ React.createElement(
                  "span",
                  {
                    style: {
                      position: "absolute",
                      inset: 0,
                      borderRadius: "50%",
                      background: h.fg,
                      animation: "km-ping 1.6s var(--ease-out) infinite",
                    },
                  },
                  /*#__PURE__*/ React.createElement(
                    "style",
                    null,
                    "@keyframes km-ping{0%{transform:scale(1);opacity:.7}70%,100%{transform:scale(2.6);opacity:0}}",
                  ),
                ),
            ),
            status,
          ),
          showGithub &&
            /*#__PURE__*/ React.createElement(
              "span",
              {
                style: {
                  fontFamily: "var(--font-sans)",
                  fontSize: "var(--text-xs)",
                  color: "var(--text-subtle)",
                },
              },
              "GitHub: ",
              h.github,
            ),
        );
      }
      Object.assign(__ds_scope, { HealthPill });
    })();
  } catch (e) {
    __ds_ns.__errors.push({
      path: "components/data-display/HealthPill.jsx",
      error: String((e && e.message) || e),
    });
  }

  // components/data-display/KeyChip.jsx
  try {
    (() => {
      /**
       * Inline monospace chip for a literal identifier the daemon reads — a column key
       * (`InProgress`), a placeholder token (`{{branch}}`), a path. `copyable` adds a
       * click-to-copy affordance. This is how the UI signals "exact string".
       */
      function KeyChip({
        children,
        tone = "neutral",
        copyable = false,
        size = "md",
        style,
      }) {
        const [copied, setCopied] = React.useState(false);
        const tones = {
          neutral: {
            fg: "var(--text-body)",
            bg: "var(--surface-sunken)",
            bd: "var(--border-subtle)",
          },
          accent: {
            fg: "var(--accent-text)",
            bg: "var(--accent-weak)",
            bd: "var(--accent-weak-border)",
          },
          token: {
            fg: "var(--col-agent-fg)",
            bg: "var(--col-agent-bg)",
            bd: "var(--col-agent-bd)",
          },
        };
        const t = tones[tone] || tones.neutral;
        const sizes = {
          sm: {
            h: 18,
            fs: "var(--text-2xs)",
          },
          md: {
            h: 21,
            fs: "var(--text-xs)",
          },
        };
        const s = sizes[size] || sizes.md;
        const copy = () => {
          if (!copyable) return;
          try {
            navigator.clipboard.writeText(String(children));
          } catch (e) {
            /* noop */
          }
          setCopied(true);
          setTimeout(() => setCopied(false), 1100);
        };
        return /*#__PURE__*/ React.createElement(
          "span",
          {
            onClick: copy,
            title: copyable ? "Copy" : undefined,
            style: {
              display: "inline-flex",
              alignItems: "center",
              gap: 5,
              height: s.h,
              padding: "0 7px",
              fontFamily: "var(--font-mono)",
              fontSize: s.fs,
              fontWeight: "var(--weight-medium)",
              color: t.fg,
              background: t.bg,
              border: `1px solid ${t.bd}`,
              borderRadius: "var(--radius-xs)",
              whiteSpace: "nowrap",
              cursor: copyable ? "pointer" : "default",
              ...style,
            },
          },
          children,
          copyable &&
            /*#__PURE__*/ React.createElement(
              "span",
              {
                style: {
                  fontSize: 10,
                  opacity: 0.6,
                },
              },
              copied ? "✓" : "⧉",
            ),
        );
      }
      Object.assign(__ds_scope, { KeyChip });
    })();
  } catch (e) {
    __ds_ns.__errors.push({
      path: "components/data-display/KeyChip.jsx",
      error: String((e && e.message) || e),
    });
  }

  // components/data-display/ProfileTag.jsx
  try {
    (() => {
      const PROFILES = {
        docs: "blue",
        prepare: "neutral",
        dev: "accent",
        check: "violet",
        merge: "red",
        "": "neutral",
      };
      const TONES = {
        neutral: {
          fg: "var(--text-muted)",
          bg: "var(--surface-sunken)",
          bd: "var(--border-subtle)",
        },
        accent: {
          fg: "var(--accent-text)",
          bg: "var(--accent-weak)",
          bd: "var(--accent-weak-border)",
        },
        blue: {
          fg: "var(--blue-700)",
          bg: "var(--blue-50)",
          bd: "var(--blue-300)",
        },
        violet: {
          fg: "var(--violet-700)",
          bg: "var(--violet-50)",
          bd: "var(--violet-300)",
        },
        red: {
          fg: "var(--red-700)",
          bg: "var(--red-50)",
          bd: "var(--red-300)",
        },
      };

      /**
       * Permission-profile tag (docs / prepare / dev / check / merge). Each profile
       * owns a tone so the launch safety level reads at a glance.
       */
      function ProfileTag({ profile = "", size = "md", style }) {
        const tone = PROFILES[profile] != null ? PROFILES[profile] : "neutral";
        const t = TONES[tone] || TONES.neutral;
        const label = profile || "no profile";
        const sizes = {
          sm: {
            h: 18,
            fs: "var(--text-2xs)",
          },
          md: {
            h: 21,
            fs: "var(--text-xs)",
          },
        };
        const s = sizes[size] || sizes.md;
        return /*#__PURE__*/ React.createElement(
          "span",
          {
            style: {
              display: "inline-flex",
              alignItems: "center",
              height: s.h,
              padding: "0 8px",
              fontFamily: "var(--font-mono)",
              fontSize: s.fs,
              fontWeight: "var(--weight-semibold)",
              color: profile ? t.fg : "var(--text-subtle)",
              background: profile ? t.bg : "transparent",
              border: `1px dashed ${profile ? "transparent" : "var(--border-default)"}`,
              borderStyle: profile ? "solid" : "dashed",
              borderColor: profile ? t.bd : "var(--border-default)",
              borderRadius: "var(--radius-xs)",
              whiteSpace: "nowrap",
              ...style,
            },
          },
          label,
        );
      }
      Object.assign(__ds_scope, { ProfileTag });
    })();
  } catch (e) {
    __ds_ns.__errors.push({
      path: "components/data-display/ProfileTag.jsx",
      error: String((e && e.message) || e),
    });
  }

  // components/feedback/Banner.jsx
  try {
    (() => {
      /**
       * Inline message banner. `tone` carries intent; the save-blocked summary, the
       * "config reloaded" notice, and warnings all use this. Optional title + action.
       */
      function Banner({
        tone = "info",
        title = null,
        children,
        icon = null,
        action = null,
        onDismiss = null,
        style,
      }) {
        // Tones lean on the dark-aware --health-* tokens (identical to the raw
        // ramp in light mode, but they flip to dark surfaces + light text in
        // dark mode). The raw --*-50/-700 ramp stops are NOT theme-aware, so a
        // banner built on them stayed light-on-light in dark mode (invisible).
        const tones = {
          info: {
            fg: "var(--health-complete-fg)",
            bg: "var(--health-complete-bg)",
            bd: "var(--health-complete-bd)",
          },
          success: {
            fg: "var(--health-active-fg)",
            bg: "var(--health-active-bg)",
            bd: "var(--health-active-bd)",
          },
          warning: {
            fg: "var(--health-waiting-fg)",
            bg: "var(--health-waiting-bg)",
            bd: "var(--health-waiting-bd)",
          },
          error: {
            fg: "var(--health-blocked-fg)",
            bg: "var(--health-blocked-bg)",
            bd: "var(--health-blocked-bd)",
          },
          neutral: {
            fg: "var(--text-body)",
            bg: "var(--surface-sunken)",
            bd: "var(--border-subtle)",
          },
        };
        const t = tones[tone] || tones.info;
        return /*#__PURE__*/ React.createElement(
          "div",
          {
            style: {
              display: "flex",
              gap: "var(--space-5)",
              padding: "11px 13px",
              background: t.bg,
              border: `1px solid ${t.bd}`,
              borderRadius: "var(--radius-sm)",
              ...style,
            },
          },
          icon != null
            ? /*#__PURE__*/ React.createElement(
                "span",
                {
                  style: {
                    color: t.fg,
                    flex: "none",
                    marginTop: 1,
                  },
                },
                icon,
              )
            : /*#__PURE__*/ React.createElement("span", {
                style: {
                  width: 7,
                  height: 7,
                  borderRadius: "50%",
                  background: t.fg,
                  flex: "none",
                  marginTop: 6,
                },
              }),
          /*#__PURE__*/ React.createElement(
            "div",
            {
              style: {
                flex: 1,
                minWidth: 0,
              },
            },
            title &&
              /*#__PURE__*/ React.createElement(
                "div",
                {
                  style: {
                    fontWeight: "var(--weight-semibold)",
                    fontSize: "var(--text-sm)",
                    color: t.fg,
                    marginBottom: children ? 2 : 0,
                  },
                },
                title,
              ),
            children &&
              /*#__PURE__*/ React.createElement(
                "div",
                {
                  style: {
                    fontSize: "var(--text-sm)",
                    color: t.fg,
                    lineHeight: 1.5,
                  },
                },
                children,
              ),
          ),
          action,
          onDismiss &&
            /*#__PURE__*/ React.createElement(
              "button",
              {
                onClick: onDismiss,
                "aria-label": "Dismiss",
                style: {
                  flex: "none",
                  border: "none",
                  background: "transparent",
                  color: t.fg,
                  cursor: "pointer",
                  fontSize: 15,
                  lineHeight: 1,
                  opacity: 0.7,
                },
              },
              "\xD7",
            ),
        );
      }
      Object.assign(__ds_scope, { Banner });
    })();
  } catch (e) {
    __ds_ns.__errors.push({
      path: "components/feedback/Banner.jsx",
      error: String((e && e.message) || e),
    });
  }

  // components/feedback/Dialog.jsx
  try {
    (() => {
      /**
       * Modal dialog with a flat ink scrim (no blur) and a bordered surface. Used for
       * editing a transition, confirming a destructive action, or the YAML preview.
       */
      function Dialog({
        open = false,
        title = null,
        description = null,
        children,
        footer = null,
        onClose,
        width = 480,
      }) {
        if (!open) return null;
        return /*#__PURE__*/ React.createElement(
          "div",
          {
            onClick: onClose,
            style: {
              position: "fixed",
              inset: 0,
              zIndex: 400,
              display: "grid",
              placeItems: "center",
              padding: "var(--space-7)",
              background:
                "color-mix(in oklch, var(--gray-950) 52%, transparent)",
              animation: "km-fade var(--dur-base) var(--ease-standard)",
            },
          },
          /*#__PURE__*/ React.createElement(
            "style",
            null,
            "@keyframes km-fade{from{opacity:0}to{opacity:1}}@keyframes km-pop{from{opacity:0;transform:translateY(6px) scale(.99)}to{opacity:1;transform:none}}",
          ),
          /*#__PURE__*/ React.createElement(
            "div",
            {
              role: "dialog",
              "aria-modal": "true",
              onClick: (e) => e.stopPropagation(),
              style: {
                width: "100%",
                maxWidth: width,
                maxHeight: "88vh",
                display: "flex",
                flexDirection: "column",
                background: "var(--surface-raised)",
                border: "1px solid var(--border-default)",
                borderRadius: "var(--radius-lg)",
                boxShadow: "var(--shadow-lg)",
                overflow: "hidden",
                animation: "km-pop var(--dur-base) var(--ease-out)",
              },
            },
            (title || onClose) &&
              /*#__PURE__*/ React.createElement(
                "div",
                {
                  style: {
                    display: "flex",
                    alignItems: "flex-start",
                    gap: "var(--space-5)",
                    padding: "14px 16px",
                    borderBottom: "1px solid var(--border-subtle)",
                  },
                },
                /*#__PURE__*/ React.createElement(
                  "div",
                  {
                    style: {
                      flex: 1,
                      minWidth: 0,
                    },
                  },
                  title &&
                    /*#__PURE__*/ React.createElement(
                      "div",
                      {
                        style: {
                          fontFamily: "var(--font-display)",
                          fontWeight: 600,
                          fontSize: "var(--text-lg)",
                          color: "var(--text-strong)",
                        },
                      },
                      title,
                    ),
                  description &&
                    /*#__PURE__*/ React.createElement(
                      "div",
                      {
                        style: {
                          fontSize: "var(--text-sm)",
                          color: "var(--text-muted)",
                          marginTop: 3,
                        },
                      },
                      description,
                    ),
                ),
                onClose &&
                  /*#__PURE__*/ React.createElement(
                    "button",
                    {
                      onClick: onClose,
                      "aria-label": "Close",
                      style: {
                        flex: "none",
                        width: 28,
                        height: 28,
                        display: "grid",
                        placeItems: "center",
                        border: "none",
                        background: "transparent",
                        color: "var(--text-muted)",
                        cursor: "pointer",
                        borderRadius: "var(--radius-xs)",
                        fontSize: 17,
                      },
                    },
                    "\xD7",
                  ),
              ),
            /*#__PURE__*/ React.createElement(
              "div",
              {
                style: {
                  padding: 16,
                  overflow: "auto",
                  flex: 1,
                },
              },
              children,
            ),
            footer &&
              /*#__PURE__*/ React.createElement(
                "div",
                {
                  style: {
                    display: "flex",
                    justifyContent: "flex-end",
                    gap: "var(--space-4)",
                    padding: "12px 16px",
                    borderTop: "1px solid var(--border-subtle)",
                    background: "var(--surface-app)",
                  },
                },
                footer,
              ),
          ),
        );
      }
      Object.assign(__ds_scope, { Dialog });
    })();
  } catch (e) {
    __ds_ns.__errors.push({
      path: "components/feedback/Dialog.jsx",
      error: String((e && e.message) || e),
    });
  }

  // components/feedback/Tooltip.jsx
  try {
    (() => {
      /**
       * Lightweight hover tooltip on the dark inverse surface. Wraps any trigger;
       * shows `label` above it. For terse hints (what a permission_mode does, etc).
       */
      function Tooltip({ label, children, placement = "top", style }) {
        const [show, setShow] = React.useState(false);
        // Computed fixed-position rect for the popup; null until measured on show.
        const [coords, setCoords] = React.useState(null);
        const triggerRef = React.useRef(null);
        const tipRef = React.useRef(null);
        const tipId = React.useId();
        // Measure the trigger + popup and compute a viewport-clamped fixed
        // position. `position: fixed` is viewport-relative, so the popup ESCAPES
        // any ancestor `overflow: hidden` (the narrow collapsed sidebar rail,
        // edge containers) instead of being clipped. Placement is collision-
        // aware: flip to the opposite side when there is no room, then shift the
        // cross-axis to keep the popup inside the viewport.
        const place = React.useCallback(() => {
          const trig = triggerRef.current;
          const tip = tipRef.current;
          if (!trig || !tip) return;
          const r = trig.getBoundingClientRect();
          const tw = tip.offsetWidth;
          const th = tip.offsetHeight;
          const vw = window.innerWidth;
          const vh = window.innerHeight;
          const gap = 6;
          const margin = 4; // keep this far from the viewport edge
          let side = placement;
          if (side === "top" && r.top - th - gap < margin) side = "bottom";
          else if (side === "bottom" && r.bottom + th + gap > vh - margin)
            side = "top";
          else if (side === "left" && r.left - tw - gap < margin)
            side = "right";
          else if (side === "right" && r.right + tw + gap > vw - margin)
            side = "left";
          let top;
          let left;
          if (side === "top" || side === "bottom") {
            top = side === "top" ? r.top - th - gap : r.bottom + gap;
            left = r.left + r.width / 2 - tw / 2; // centre on the trigger
          } else {
            left = side === "left" ? r.left - tw - gap : r.right + gap;
            top = r.top + r.height / 2 - th / 2;
          }
          left = Math.max(margin, Math.min(left, vw - tw - margin));
          top = Math.max(margin, Math.min(top, vh - th - margin));
          setCoords({ top, left });
        }, [placement]);
        // Re-measure on show and on scroll/resize while visible (fixed coords
        // are viewport-relative, so they drift if the page scrolls).
        React.useLayoutEffect(() => {
          if (!show) {
            setCoords(null);
            return undefined;
          }
          place();
          const onMove = () => place();
          window.addEventListener("scroll", onMove, true);
          window.addEventListener("resize", onMove);
          return () => {
            window.removeEventListener("scroll", onMove, true);
            window.removeEventListener("resize", onMove);
          };
        }, [show, place]);
        return /*#__PURE__*/ React.createElement(
          "span",
          {
            ref: triggerRef,
            onMouseEnter: () => setShow(true),
            onMouseLeave: () => setShow(false),
            onFocus: () => setShow(true),
            onBlur: () => setShow(false),
            onClick: () => setShow(!show),
            style: {
              position: "relative",
              display: "inline-flex",
              ...style,
            },
          },
          React.isValidElement(children)
            ? React.cloneElement(
                children,
                Object.assign(
                  { "aria-describedby": tipId },
                  typeof label === "string" &&
                    children.props &&
                    !children.props["aria-label"]
                    ? { "aria-label": label }
                    : {},
                ),
              )
            : children,
          show &&
            /*#__PURE__*/ React.createElement(
              "span",
              {
                id: tipId,
                ref: tipRef,
                role: "tooltip",
                style: {
                  position: "fixed",
                  // Off-screen until measured to avoid a one-frame flash at (0,0).
                  top: coords ? coords.top : -9999,
                  left: coords ? coords.left : -9999,
                  zIndex: 1000,
                  whiteSpace: "nowrap",
                  pointerEvents: "none",
                  background: "var(--tooltip-bg)",
                  color: "var(--tooltip-text)",
                  fontFamily: "var(--font-sans)",
                  fontSize: "var(--text-xs)",
                  fontWeight: 500,
                  padding: "5px 9px",
                  borderRadius: "var(--radius-xs)",
                  boxShadow: "var(--shadow-md)",
                  animation: "km-tip var(--dur-fast) var(--ease-out)",
                },
              },
              /*#__PURE__*/ React.createElement(
                "style",
                null,
                "@keyframes km-tip{from{opacity:0}to{opacity:1}}",
              ),
              label,
            ),
        );
      }
      Object.assign(__ds_scope, { Tooltip });
    })();
  } catch (e) {
    __ds_ns.__errors.push({
      path: "components/feedback/Tooltip.jsx",
      error: String((e && e.message) || e),
    });
  }

  // components/kanban/ColumnCard.jsx
  try {
    (() => {
      const CLASS_TONE = {
        agent: {
          fg: "var(--col-agent-fg)",
          bg: "var(--col-agent-bg)",
          bd: "var(--col-agent-bd)",
          solid: "var(--col-agent-solid)",
        },
        reactive: {
          fg: "var(--col-reactive-fg)",
          bg: "var(--col-reactive-bg)",
          bd: "var(--col-reactive-bd)",
          solid: "var(--col-reactive-solid)",
        },
        inert: {
          fg: "var(--col-inert-fg)",
          bg: "var(--col-inert-bg)",
          bd: "var(--col-inert-bd)",
          solid: "var(--col-inert-solid)",
        },
      };

      /**
       * A board column header/lane. Shows the human name, the mono key, the class
       * chip, and a ticket count. Agent/reactive columns get a thin top accent rule in
       * their class colour so a glance down the board reads the pipeline shape.
       * Self-contained (renders its own class chip) so it has no cross-component deps.
       */
      function ColumnCard({
        name,
        columnKey,
        columnClass = "inert",
        count = 0,
        children,
        selected = false,
        onClick,
        style,
      }) {
        const c = CLASS_TONE[columnClass] || CLASS_TONE.inert;
        const accent = columnClass === "inert" ? "transparent" : c.solid;
        return /*#__PURE__*/ React.createElement(
          "div",
          {
            onClick: onClick,
            style: {
              display: "flex",
              flexDirection: "column",
              minWidth: 0,
              background: "var(--surface-card)",
              border: `1px solid ${selected ? "var(--border-focus)" : "var(--border-subtle)"}`,
              borderRadius: "var(--radius-md)",
              overflow: "hidden",
              boxShadow: selected ? "var(--shadow-focus)" : "var(--shadow-xs)",
              cursor: onClick ? "pointer" : "default",
              ...style,
            },
          },
          /*#__PURE__*/ React.createElement("div", {
            style: {
              height: 3,
              background: accent,
              flex: "none",
            },
          }),
          /*#__PURE__*/ React.createElement(
            "div",
            {
              style: {
                display: "flex",
                alignItems: "center",
                gap: "var(--space-4)",
                padding: "10px 12px",
                borderBottom: children
                  ? "1px solid var(--border-subtle)"
                  : "none",
              },
            },
            /*#__PURE__*/ React.createElement(
              "div",
              {
                style: {
                  minWidth: 0,
                  flex: 1,
                },
              },
              /*#__PURE__*/ React.createElement(
                "div",
                {
                  style: {
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                  },
                },
                /*#__PURE__*/ React.createElement(
                  "span",
                  {
                    style: {
                      fontFamily: "var(--font-display)",
                      fontWeight: 600,
                      fontSize: "var(--text-md)",
                      color: "var(--text-strong)",
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                    },
                  },
                  name,
                ),
                /*#__PURE__*/ React.createElement(
                  "span",
                  {
                    style: {
                      fontFamily: "var(--font-mono)",
                      fontSize: "var(--text-2xs)",
                      color: "var(--text-subtle)",
                    },
                  },
                  count,
                ),
              ),
              /*#__PURE__*/ React.createElement(
                "div",
                {
                  style: {
                    fontFamily: "var(--font-mono)",
                    fontSize: "var(--text-2xs)",
                    color: "var(--text-subtle)",
                    marginTop: 2,
                  },
                },
                columnKey,
              ),
            ),
            /*#__PURE__*/ React.createElement(
              "span",
              {
                style: {
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                  height: 18,
                  padding: "0 7px",
                  fontFamily: "var(--font-mono)",
                  fontSize: "var(--text-2xs)",
                  fontWeight: 600,
                  color: c.fg,
                  background: c.bg,
                  border: `1px solid ${c.bd}`,
                  borderRadius: "var(--radius-xs)",
                  whiteSpace: "nowrap",
                },
              },
              /*#__PURE__*/ React.createElement("span", {
                style: {
                  width: 7,
                  height: 7,
                  borderRadius: 2,
                  background: c.solid,
                  flex: "none",
                },
              }),
              columnClass,
            ),
          ),
          children &&
            /*#__PURE__*/ React.createElement(
              "div",
              {
                style: {
                  display: "flex",
                  flexDirection: "column",
                  gap: 8,
                  padding: 10,
                  background: "var(--surface-app)",
                },
              },
              children,
            ),
        );
      }
      Object.assign(__ds_scope, { ColumnCard });
    })();
  } catch (e) {
    __ds_ns.__errors.push({
      path: "components/kanban/ColumnCard.jsx",
      error: String((e && e.message) || e),
    });
  }

  // components/kanban/FindingItem.jsx
  try {
    (() => {
      /**
       * A single validation Finding (config_validate.py). `error` blocks save and
       * paints red; `warning` is advisory amber. Shows the dot-path field locus in
       * mono and the message, matching the API's `{field, message, severity}` shape.
       */
      function FindingItem({
        severity = "error",
        field,
        message,
        onClick,
        style,
      }) {
        const isErr = severity === "error";
        const c = isErr
          ? {
              fg: "var(--red-700)",
              bg: "var(--red-50)",
              bd: "var(--red-300)",
              dot: "var(--red-500)",
              label: "error",
            }
          : {
              fg: "var(--amber-700)",
              bg: "var(--amber-50)",
              bd: "var(--amber-300)",
              dot: "var(--amber-500)",
              label: "warning",
            };
        return /*#__PURE__*/ React.createElement(
          "div",
          {
            onClick: onClick,
            style: {
              display: "flex",
              gap: "var(--space-5)",
              padding: "10px 12px",
              background: c.bg,
              border: `1px solid ${c.bd}`,
              borderRadius: "var(--radius-sm)",
              cursor: onClick ? "pointer" : "default",
              ...style,
            },
          },
          /*#__PURE__*/ React.createElement("span", {
            style: {
              width: 8,
              height: 8,
              borderRadius: "50%",
              background: c.dot,
              flex: "none",
              marginTop: 5,
            },
          }),
          /*#__PURE__*/ React.createElement(
            "div",
            {
              style: {
                minWidth: 0,
                flex: 1,
              },
            },
            /*#__PURE__*/ React.createElement(
              "div",
              {
                style: {
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  marginBottom: 3,
                },
              },
              /*#__PURE__*/ React.createElement(
                "span",
                {
                  style: {
                    fontFamily: "var(--font-mono)",
                    fontSize: "var(--text-2xs)",
                    fontWeight: 700,
                    textTransform: "uppercase",
                    letterSpacing: "0.06em",
                    color: c.fg,
                  },
                },
                c.label,
              ),
              field &&
                /*#__PURE__*/ React.createElement(
                  "span",
                  {
                    style: {
                      fontFamily: "var(--font-mono)",
                      fontSize: "var(--text-2xs)",
                      color: c.fg,
                      opacity: 0.85,
                      background: "rgba(0,0,0,0.04)",
                      padding: "1px 5px",
                      borderRadius: "var(--radius-xs)",
                    },
                  },
                  field,
                ),
            ),
            /*#__PURE__*/ React.createElement(
              "div",
              {
                style: {
                  fontSize: "var(--text-sm)",
                  color: "var(--text-body)",
                  lineHeight: 1.45,
                },
              },
              message,
            ),
          ),
        );
      }
      Object.assign(__ds_scope, { FindingItem });
    })();
  } catch (e) {
    __ds_ns.__errors.push({
      path: "components/kanban/FindingItem.jsx",
      error: String((e && e.message) || e),
    });
  }

  // components/kanban/TicketCard.jsx
  try {
    (() => {
      /**
       * A ticket card as it sits in a board lane. Shows the issue number + title, an
       * optional running-agent row, and an optional health dot. Lifts on hover; tilts
       * + heavy-shadows while dragging.
       */
      function TicketCard({
        number,
        title,
        agent = null,
        health = null,
        dragging = false,
        onClick,
        style,
      }) {
        const [hover, setHover] = React.useState(false);
        return /*#__PURE__*/ React.createElement(
          "div",
          {
            onClick: onClick,
            onMouseEnter: () => setHover(true),
            onMouseLeave: () => setHover(false),
            style: {
              background: "var(--surface-card)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "var(--radius-sm)",
              padding: "9px 11px",
              cursor: onClick ? "pointer" : "grab",
              boxShadow: dragging
                ? "var(--shadow-lg)"
                : hover
                  ? "var(--shadow-sm)"
                  : "var(--shadow-xs)",
              transform: dragging ? "rotate(1.5deg)" : "none",
              transition:
                "box-shadow var(--dur-fast) var(--ease-standard), transform var(--dur-fast) var(--ease-out)",
              ...style,
            },
          },
          /*#__PURE__*/ React.createElement(
            "div",
            {
              style: {
                display: "flex",
                alignItems: "flex-start",
                gap: 8,
              },
            },
            /*#__PURE__*/ React.createElement(
              "span",
              {
                style: {
                  fontFamily: "var(--font-mono)",
                  fontSize: "var(--text-2xs)",
                  color: "var(--text-subtle)",
                  paddingTop: 1,
                },
              },
              "#",
              number,
            ),
            /*#__PURE__*/ React.createElement(
              "span",
              {
                style: {
                  fontSize: "var(--text-sm)",
                  color: "var(--text-strong)",
                  fontWeight: "var(--weight-medium)",
                  lineHeight: 1.35,
                  flex: 1,
                  minWidth: 0,
                },
              },
              title,
            ),
            health &&
              /*#__PURE__*/ React.createElement("span", {
                style: {
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  background: `var(--health-${String(health).toLowerCase()}-fg)`,
                  flex: "none",
                  marginTop: 4,
                },
              }),
          ),
          agent &&
            /*#__PURE__*/ React.createElement(
              "div",
              {
                style: {
                  display: "flex",
                  alignItems: "center",
                  gap: 7,
                  marginTop: 9,
                  paddingTop: 8,
                  borderTop: "1px solid var(--border-subtle)",
                },
              },
              /*#__PURE__*/ React.createElement(__ds_scope.Avatar, {
                kind: "agent",
                label: agent.label || "A",
                size: "xs",
              }),
              /*#__PURE__*/ React.createElement(
                "span",
                {
                  style: {
                    fontFamily: "var(--font-mono)",
                    fontSize: "var(--text-2xs)",
                    color: "var(--text-muted)",
                    flex: 1,
                    minWidth: 0,
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                  },
                },
                agent.session || agent.label,
              ),
              agent.status &&
                /*#__PURE__*/ React.createElement(__ds_scope.HealthPill, {
                  status: agent.status,
                  size: "sm",
                  pulse: agent.status === "ACTIVE",
                }),
            ),
        );
      }
      Object.assign(__ds_scope, { TicketCard });
    })();
  } catch (e) {
    __ds_ns.__errors.push({
      path: "components/kanban/TicketCard.jsx",
      error: String((e && e.message) || e),
    });
  }

  // components/kanban/TransitionRow.jsx
  try {
    (() => {
      /**
       * One whitelist transition row in the config editor: `from → to` plus its
       * profile, permission_mode, and a launch/no-op marker. This is the central
       * object of the configuration interface. `invalid` paints the error rail used
       * when a validation finding targets this row.
       */
      function TransitionRow({
        fromCol,
        toCol,
        profile = "",
        permissionMode = "auto",
        willLaunch = false,
        advance = "stop",
        selected = false,
        invalid = false,
        onClick,
        actions = null,
        style,
      }) {
        const [hover, setHover] = React.useState(false);
        const rail = invalid
          ? "var(--red-500)"
          : selected
            ? "var(--border-focus)"
            : "transparent";
        return /*#__PURE__*/ React.createElement(
          "div",
          {
            onClick: onClick,
            onMouseEnter: () => setHover(true),
            onMouseLeave: () => setHover(false),
            style: {
              display: "flex",
              alignItems: "center",
              gap: "var(--space-5)",
              padding: "10px 12px 10px 10px",
              background: selected
                ? "var(--accent-weak)"
                : hover
                  ? "var(--surface-hover)"
                  : "var(--surface-card)",
              borderLeft: `2.5px solid ${rail}`,
              borderBottom: "1px solid var(--border-subtle)",
              cursor: onClick ? "pointer" : "default",
              transition: "background var(--dur-fast) var(--ease-standard)",
              ...style,
            },
          },
          /*#__PURE__*/ React.createElement(
            "span",
            {
              style: {
                color: "var(--text-subtle)",
                cursor: "grab",
                fontSize: 13,
                flex: "none",
                lineHeight: 1,
              },
            },
            "\u283F",
          ),
          /*#__PURE__*/ React.createElement(
            "div",
            {
              style: {
                display: "flex",
                alignItems: "center",
                gap: 8,
                flex: 1,
                minWidth: 0,
                flexWrap: "wrap",
              },
            },
            /*#__PURE__*/ React.createElement(
              __ds_scope.KeyChip,
              null,
              Array.isArray(fromCol) ? fromCol.join(" · ") : fromCol,
            ),
            /*#__PURE__*/ React.createElement(
              "span",
              {
                style: {
                  color: "var(--col-agent-fg)",
                  fontFamily: "var(--font-mono)",
                  fontWeight: 600,
                },
              },
              "\u2192",
            ),
            /*#__PURE__*/ React.createElement(
              __ds_scope.KeyChip,
              {
                tone: "accent",
              },
              Array.isArray(toCol) ? toCol.join(" · ") : toCol,
            ),
          ),
          /*#__PURE__*/ React.createElement(
            "div",
            {
              style: {
                display: "flex",
                alignItems: "center",
                gap: 8,
                flex: "none",
              },
            },
            willLaunch
              ? /*#__PURE__*/ React.createElement(
                  "span",
                  {
                    style: {
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 5,
                      fontFamily: "var(--font-mono)",
                      fontSize: "var(--text-2xs)",
                      fontWeight: 600,
                      color: "var(--col-agent-fg)",
                    },
                  },
                  /*#__PURE__*/ React.createElement("span", {
                    style: {
                      width: 6,
                      height: 6,
                      borderRadius: 2,
                      background: "var(--col-agent-solid)",
                    },
                  }),
                  "launches",
                )
              : /*#__PURE__*/ React.createElement(
                  "span",
                  {
                    style: {
                      fontFamily: "var(--font-mono)",
                      fontSize: "var(--text-2xs)",
                      color: "var(--text-subtle)",
                    },
                  },
                  "no-op",
                ),
            /*#__PURE__*/ React.createElement(__ds_scope.ProfileTag, {
              profile: profile,
              size: "sm",
            }),
            /*#__PURE__*/ React.createElement(
              "span",
              {
                style: {
                  fontFamily: "var(--font-mono)",
                  fontSize: "var(--text-2xs)",
                  color: "var(--text-muted)",
                  minWidth: 84,
                  textAlign: "right",
                },
              },
              permissionMode,
            ),
            actions,
          ),
        );
      }
      Object.assign(__ds_scope, { TransitionRow });
    })();
  } catch (e) {
    __ds_ns.__errors.push({
      path: "components/kanban/TransitionRow.jsx",
      error: String((e && e.message) || e),
    });
  }

  // ui_kits/config/AppShell.jsx
  try {
    (() => {
      // KanbanMate config — AppShell: sidebar + header chrome. Uses shadcn sidebar tokens.
      const { HealthPill, Button, IconButton, Badge } =
        window.KanbanMateDesignSystem_2463ad;
      function Wordmark({ size = 16 }) {
        return /*#__PURE__*/ React.createElement(
          "span",
          {
            style: {
              display: "inline-flex",
              alignItems: "center",
              gap: 10,
              fontFamily: "var(--font-display)",
              fontWeight: 700,
              letterSpacing: "var(--tracking-tight)",
              color: "var(--sidebar-foreground)",
              lineHeight: 1,
              fontSize: size,
            },
          },
          /*#__PURE__*/ React.createElement(
            "span",
            {
              style: {
                display: "inline-grid",
                placeItems: "center",
                width: size * 1.6,
                height: size * 1.6,
                borderRadius: "var(--radius-md)",
                background: "var(--primary)",
                color: "var(--primary-foreground)",
                fontFamily: "var(--font-mono)",
                fontWeight: 600,
                fontSize: size * 0.95,
                flex: "none",
              },
            },
            "[\u25B8]",
          ),
          "KanbanMate",
        );
      }
      const NAV = [
        {
          id: "columns",
          label: "Columns",
          key: "columns.yml",
        },
        {
          id: "transitions",
          label: "Transitions",
          key: "transitions.yml",
        },
        {
          id: "defaults",
          label: "Defaults",
          key: "defaults",
        },
        {
          id: "validation",
          label: "Validation",
          key: "V1–V10",
        },
        {
          id: "yaml",
          label: "YAML preview",
          key: "read-only",
        },
      ];
      function NavItem({ item, active, onClick, badge }) {
        const [hover, setHover] = React.useState(false);
        return /*#__PURE__*/ React.createElement(
          "button",
          {
            onClick: onClick,
            onMouseEnter: () => setHover(true),
            onMouseLeave: () => setHover(false),
            style: {
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 8,
              width: "100%",
              padding: "7px 10px",
              border: "none",
              cursor: "pointer",
              textAlign: "left",
              borderRadius: "var(--radius-md)",
              fontFamily: "var(--font-sans)",
              fontSize: "var(--text-sm)",
              fontWeight: active ? 600 : 500,
              color: active
                ? "var(--sidebar-accent-foreground)"
                : "var(--muted-foreground)",
              background: active
                ? "var(--sidebar-accent)"
                : hover
                  ? "var(--sidebar-accent)"
                  : "transparent",
              transition:
                "background var(--dur-fast) var(--ease-standard), color var(--dur-fast) var(--ease-standard)",
            },
          },
          /*#__PURE__*/ React.createElement(
            "span",
            {
              style: {
                display: "flex",
                alignItems: "center",
                gap: 9,
              },
            },
            /*#__PURE__*/ React.createElement("span", {
              style: {
                width: 6,
                height: 6,
                borderRadius: 2,
                flex: "none",
                background: active ? "var(--primary)" : "var(--border)",
              },
            }),
            item.label,
          ),
          badge != null && badge > 0
            ? /*#__PURE__*/ React.createElement(
                Badge,
                {
                  tone: "red",
                  size: "sm",
                },
                badge,
              )
            : /*#__PURE__*/ React.createElement(
                "span",
                {
                  style: {
                    fontFamily: "var(--font-mono)",
                    fontSize: 10,
                    color: "var(--muted-foreground)",
                    opacity: 0.7,
                  },
                },
                item.key,
              ),
        );
      }
      function AppShell({
        active,
        onNav,
        errorCount = 0,
        dirty = false,
        onSave,
        children,
        mobile = false,
      }) {
        const data = window.KMConfigData;
        const blocked = errorCount > 0;
        const sidebar = /*#__PURE__*/ React.createElement(
          "aside",
          {
            style: {
              width: 248,
              flex: "none",
              display: "flex",
              flexDirection: "column",
              background: "var(--sidebar)",
              borderRight: "1px solid var(--sidebar-border)",
              ...(mobile
                ? {
                    display: "none",
                  }
                : {}),
            },
          },
          /*#__PURE__*/ React.createElement(
            "div",
            {
              style: {
                padding: "16px 16px 14px",
                borderBottom: "1px solid var(--sidebar-border)",
              },
            },
            /*#__PURE__*/ React.createElement(Wordmark, null),
            /*#__PURE__*/ React.createElement(
              "div",
              {
                style: {
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  marginTop: 12,
                  fontFamily: "var(--font-mono)",
                  fontSize: 11,
                  color: "var(--muted-foreground)",
                },
              },
              /*#__PURE__*/ React.createElement(
                "span",
                {
                  style: {
                    width: 14,
                    height: 14,
                    display: "inline-grid",
                    placeItems: "center",
                  },
                },
                "\u2387",
              ),
              data.binding.project,
            ),
          ),
          /*#__PURE__*/ React.createElement(
            "nav",
            {
              style: {
                display: "flex",
                flexDirection: "column",
                gap: 2,
                padding: 10,
                flex: 1,
              },
            },
            /*#__PURE__*/ React.createElement(
              "div",
              {
                style: {
                  fontFamily: "var(--font-mono)",
                  fontSize: 10,
                  letterSpacing: ".09em",
                  textTransform: "uppercase",
                  color: "var(--muted-foreground)",
                  padding: "6px 10px 8px",
                },
              },
              "Configuration",
            ),
            NAV.map((n) =>
              /*#__PURE__*/ React.createElement(NavItem, {
                key: n.id,
                item: n,
                active: active === n.id,
                onClick: () => onNav(n.id),
                badge: n.id === "validation" ? errorCount : null,
              }),
            ),
          ),
          /*#__PURE__*/ React.createElement(
            "div",
            {
              style: {
                padding: 12,
                borderTop: "1px solid var(--sidebar-border)",
                display: "flex",
                alignItems: "center",
                gap: 8,
              },
            },
            /*#__PURE__*/ React.createElement(
              "span",
              {
                style: {
                  width: 26,
                  height: 26,
                  borderRadius: "50%",
                  background: "var(--muted)",
                  border: "1px solid var(--border)",
                  display: "grid",
                  placeItems: "center",
                  fontFamily: "var(--font-mono)",
                  fontSize: 10,
                  fontWeight: 600,
                  color: "var(--muted-foreground)",
                },
              },
              "kd",
            ),
            /*#__PURE__*/ React.createElement(
              "div",
              {
                style: {
                  minWidth: 0,
                  flex: 1,
                },
              },
              /*#__PURE__*/ React.createElement(
                "div",
                {
                  style: {
                    fontSize: 12,
                    fontWeight: 500,
                    color: "var(--foreground)",
                  },
                },
                "kanban daemon",
              ),
              /*#__PURE__*/ React.createElement(
                "div",
                {
                  style: {
                    fontFamily: "var(--font-mono)",
                    fontSize: 10,
                    color: "var(--muted-foreground)",
                  },
                },
                "polling \xB7 30s",
              ),
            ),
          ),
        );
        const headerTitle = NAV.find((n) => n.id === active) || NAV[0];
        return /*#__PURE__*/ React.createElement(
          "div",
          {
            style: {
              display: "flex",
              height: "100%",
              minHeight: 0,
              background: "var(--background)",
              color: "var(--foreground)",
            },
          },
          sidebar,
          /*#__PURE__*/ React.createElement(
            "div",
            {
              style: {
                flex: 1,
                minWidth: 0,
                display: "flex",
                flexDirection: "column",
              },
            },
            /*#__PURE__*/ React.createElement(
              "header",
              {
                style: {
                  display: "flex",
                  alignItems: "center",
                  gap: 14,
                  padding: mobile ? "12px 16px" : "14px 22px",
                  borderBottom: "1px solid var(--border)",
                  background:
                    "color-mix(in oklch, var(--card) 86%, transparent)",
                  backdropFilter: "blur(8px)",
                  position: "sticky",
                  top: 0,
                  zIndex: 50,
                },
              },
              mobile &&
                /*#__PURE__*/ React.createElement(
                  "span",
                  {
                    style: {
                      marginRight: 2,
                    },
                  },
                  /*#__PURE__*/ React.createElement(Wordmark, {
                    size: 14,
                  }),
                ),
              /*#__PURE__*/ React.createElement(
                "div",
                {
                  style: {
                    flex: 1,
                    minWidth: 0,
                  },
                },
                !mobile &&
                  /*#__PURE__*/ React.createElement(
                    "div",
                    {
                      style: {
                        display: "flex",
                        alignItems: "center",
                        gap: 8,
                      },
                    },
                    /*#__PURE__*/ React.createElement(
                      "h1",
                      {
                        style: {
                          fontFamily: "var(--font-display)",
                          fontSize: "var(--text-xl)",
                          fontWeight: 600,
                          letterSpacing: "var(--tracking-tight)",
                        },
                      },
                      headerTitle.label,
                    ),
                    /*#__PURE__*/ React.createElement(
                      "span",
                      {
                        style: {
                          fontFamily: "var(--font-mono)",
                          fontSize: 11,
                          color: "var(--muted-foreground)",
                          background: "var(--muted)",
                          border: "1px solid var(--border)",
                          padding: "1px 7px",
                          borderRadius: "var(--radius-sm)",
                          whiteSpace: "nowrap",
                        },
                      },
                      headerTitle.key,
                    ),
                  ),
              ),
              /*#__PURE__*/ React.createElement(HealthPill, {
                status: blocked ? "BLOCKED" : dirty ? "WAITING" : "ACTIVE",
                size: "md",
                pulse: !blocked && !dirty,
              }),
              /*#__PURE__*/ React.createElement(
                Button,
                {
                  variant: "secondary",
                  size: "md",
                },
                "Reload",
              ),
              /*#__PURE__*/ React.createElement(
                Button,
                {
                  variant: "primary",
                  size: "md",
                  disabled: blocked,
                  onClick: onSave,
                },
                blocked
                  ? `${errorCount} error${errorCount > 1 ? "s" : ""} block save`
                  : dirty
                    ? "Save config"
                    : "Saved",
              ),
            ),
            /*#__PURE__*/ React.createElement(
              "main",
              {
                style: {
                  flex: 1,
                  minHeight: 0,
                  overflow: "auto",
                  padding: mobile ? "16px 16px 72px" : "22px 26px 72px",
                  background: "var(--background)",
                },
              },
              children,
            ),
          ),
        );
      }
      Object.assign(window, {
        AppShell,
        Wordmark,
        KMNav: NAV,
      });
    })();
  } catch (e) {
    __ds_ns.__errors.push({
      path: "ui_kits/config/AppShell.jsx",
      error: String((e && e.message) || e),
    });
  }

  // ui_kits/config/ColumnsPanel.jsx
  try {
    (() => {
      // KanbanMate config — Columns panel. The board's 11 columns; agent columns expose
      // prompt / profile / permission_mode / interactive_only. Composes ColumnClassChip,
      // KeyChip, ProfileTag, Badge, Switch, IconButton, Button.
      const KMNS = window.KanbanMateDesignSystem_2463ad;
      function ColumnsPanel() {
        const data = window.KMConfigData;
        const [cols, setCols] = React.useState(data.columns);
        const [openKey, setOpenKey] = React.useState("InProgress");
        const {
          ColumnClassChip,
          KeyChip,
          ProfileTag,
          Badge,
          Switch,
          IconButton,
          Button,
        } = KMNS;
        const count = {
          agent: cols.filter((c) => c.cls === "agent").length,
          reactive: cols.filter((c) => c.cls === "reactive").length,
          inert: cols.filter((c) => c.cls === "inert").length,
        };
        return /*#__PURE__*/ React.createElement(
          "div",
          {
            style: {
              maxWidth: 880,
              margin: "0 auto",
            },
          },
          /*#__PURE__*/ React.createElement(
            "div",
            {
              style: {
                display: "flex",
                alignItems: "center",
                gap: 12,
                marginBottom: 18,
              },
            },
            /*#__PURE__*/ React.createElement(
              "p",
              {
                style: {
                  margin: 0,
                  flex: 1,
                  fontSize: "var(--text-sm)",
                  color: "var(--muted-foreground)",
                  lineHeight: 1.5,
                },
              },
              "Board columns mirror ",
              /*#__PURE__*/ React.createElement(
                "code",
                {
                  style: {
                    fontFamily: "var(--font-mono)",
                  },
                },
                "columns.yml",
              ),
              " order. Moving a card into an ",
              /*#__PURE__*/ React.createElement(
                "b",
                {
                  style: {
                    color: "var(--col-agent-fg)",
                  },
                },
                "agent",
              ),
              " column launches a Claude Code agent; a ",
              /*#__PURE__*/ React.createElement(
                "b",
                {
                  style: {
                    color: "var(--col-reactive-fg)",
                  },
                },
                "reactive",
              ),
              " column runs a side-effect; ",
              /*#__PURE__*/ React.createElement("b", null, "inert"),
              " columns are human gates or terminal states.",
            ),
            /*#__PURE__*/ React.createElement(
              Button,
              {
                variant: "secondary",
                size: "sm",
              },
              "+ Add column",
            ),
          ),
          /*#__PURE__*/ React.createElement(
            "div",
            {
              style: {
                display: "flex",
                gap: 8,
                marginBottom: 16,
              },
            },
            /*#__PURE__*/ React.createElement(
              "span",
              {
                style: {
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                },
              },
              /*#__PURE__*/ React.createElement(ColumnClassChip, {
                columnClass: "agent",
                size: "sm",
              }),
              /*#__PURE__*/ React.createElement(
                "span",
                {
                  style: {
                    fontFamily: "var(--font-mono)",
                    fontSize: 12,
                    color: "var(--muted-foreground)",
                  },
                },
                count.agent,
              ),
            ),
            /*#__PURE__*/ React.createElement(
              "span",
              {
                style: {
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                },
              },
              /*#__PURE__*/ React.createElement(ColumnClassChip, {
                columnClass: "reactive",
                size: "sm",
              }),
              /*#__PURE__*/ React.createElement(
                "span",
                {
                  style: {
                    fontFamily: "var(--font-mono)",
                    fontSize: 12,
                    color: "var(--muted-foreground)",
                  },
                },
                count.reactive,
              ),
            ),
            /*#__PURE__*/ React.createElement(
              "span",
              {
                style: {
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                },
              },
              /*#__PURE__*/ React.createElement(ColumnClassChip, {
                columnClass: "inert",
                size: "sm",
              }),
              /*#__PURE__*/ React.createElement(
                "span",
                {
                  style: {
                    fontFamily: "var(--font-mono)",
                    fontSize: 12,
                    color: "var(--muted-foreground)",
                  },
                },
                count.inert,
              ),
            ),
          ),
          /*#__PURE__*/ React.createElement(
            "div",
            {
              style: {
                display: "flex",
                flexDirection: "column",
                gap: 8,
              },
            },
            cols.map((c, i) => {
              const open = openKey === c.key && c.cls === "agent";
              const accent =
                c.cls === "agent"
                  ? "var(--col-agent-solid)"
                  : c.cls === "reactive"
                    ? "var(--col-reactive-solid)"
                    : "transparent";
              return /*#__PURE__*/ React.createElement(
                "div",
                {
                  key: c.key,
                  style: {
                    background: "var(--card)",
                    border: "1px solid var(--border)",
                    borderRadius: "var(--radius-lg)",
                    boxShadow: "var(--shadow-xs)",
                    overflow: "hidden",
                  },
                },
                /*#__PURE__*/ React.createElement(
                  "div",
                  {
                    onClick: () =>
                      c.cls === "agent" && setOpenKey(open ? null : c.key),
                    style: {
                      display: "flex",
                      alignItems: "center",
                      gap: 12,
                      padding: "12px 14px",
                      cursor: c.cls === "agent" ? "pointer" : "default",
                    },
                  },
                  /*#__PURE__*/ React.createElement(
                    "span",
                    {
                      style: {
                        fontFamily: "var(--font-mono)",
                        fontSize: 11,
                        color: "var(--muted-foreground)",
                        width: 18,
                        flex: "none",
                      },
                    },
                    String(i + 1).padStart(2, "0"),
                  ),
                  /*#__PURE__*/ React.createElement("span", {
                    style: {
                      width: 3,
                      height: 26,
                      borderRadius: 2,
                      background: accent,
                      flex: "none",
                    },
                  }),
                  /*#__PURE__*/ React.createElement(
                    "div",
                    {
                      style: {
                        minWidth: 0,
                        flex: 1,
                      },
                    },
                    /*#__PURE__*/ React.createElement(
                      "div",
                      {
                        style: {
                          display: "flex",
                          alignItems: "center",
                          gap: 9,
                          flexWrap: "wrap",
                        },
                      },
                      /*#__PURE__*/ React.createElement(
                        "span",
                        {
                          style: {
                            fontFamily: "var(--font-display)",
                            fontWeight: 600,
                            fontSize: "var(--text-md)",
                            color: "var(--foreground)",
                          },
                        },
                        c.name,
                      ),
                      /*#__PURE__*/ React.createElement(KeyChip, null, c.key),
                      c.key === "Merge" &&
                        /*#__PURE__*/ React.createElement(
                          Badge,
                          {
                            tone: "red",
                            size: "sm",
                          },
                          "human only",
                        ),
                    ),
                    c.note &&
                      /*#__PURE__*/ React.createElement(
                        "div",
                        {
                          style: {
                            fontSize: 12,
                            color: "var(--muted-foreground)",
                            marginTop: 4,
                            lineHeight: 1.45,
                          },
                        },
                        c.note,
                      ),
                  ),
                  /*#__PURE__*/ React.createElement(ColumnClassChip, {
                    columnClass: c.cls,
                  }),
                  c.cls === "agent" &&
                    /*#__PURE__*/ React.createElement(
                      "span",
                      {
                        style: {
                          fontFamily: "var(--font-mono)",
                          fontSize: 13,
                          color: "var(--muted-foreground)",
                          transform: open ? "rotate(90deg)" : "none",
                          transition:
                            "transform var(--dur-fast) var(--ease-standard)",
                        },
                      },
                      "\u203A",
                    ),
                ),
                open &&
                  /*#__PURE__*/ React.createElement(
                    "div",
                    {
                      style: {
                        borderTop: "1px solid var(--border)",
                        background: "var(--muted)",
                        padding: "14px 14px 14px 50px",
                        display: "grid",
                        gridTemplateColumns: "repeat(2, minmax(0,1fr))",
                        gap: 14,
                      },
                    },
                    /*#__PURE__*/ React.createElement(
                      Field,
                      {
                        label: "prompt",
                      },
                      /*#__PURE__*/ React.createElement(
                        KeyChip,
                        {
                          tone: "token",
                        },
                        c.prompt,
                      ),
                    ),
                    /*#__PURE__*/ React.createElement(
                      Field,
                      {
                        label: "permission_profile",
                      },
                      /*#__PURE__*/ React.createElement(ProfileTag, {
                        profile: c.profile,
                      }),
                    ),
                    /*#__PURE__*/ React.createElement(
                      Field,
                      {
                        label: "permission_mode",
                      },
                      /*#__PURE__*/ React.createElement(
                        KeyChip,
                        null,
                        c.permission_mode,
                      ),
                    ),
                    /*#__PURE__*/ React.createElement(
                      Field,
                      {
                        label: "interactive_only",
                      },
                      /*#__PURE__*/ React.createElement(
                        "span",
                        {
                          style: {
                            display: "inline-flex",
                            alignItems: "center",
                            gap: 8,
                          },
                        },
                        /*#__PURE__*/ React.createElement(Switch, {
                          checked: !!c.interactive_only,
                          size: "sm",
                          onChange: () => {},
                        }),
                        /*#__PURE__*/ React.createElement(
                          "span",
                          {
                            style: {
                              fontFamily: "var(--font-mono)",
                              fontSize: 12,
                              color: "var(--muted-foreground)",
                            },
                          },
                          c.interactive_only
                            ? "true"
                            : "false — fires unattended",
                        ),
                      ),
                    ),
                  ),
              );
            }),
          ),
        );
      }
      function Field({ label, children }) {
        return /*#__PURE__*/ React.createElement(
          "div",
          {
            style: {
              display: "flex",
              flexDirection: "column",
              gap: 6,
            },
          },
          /*#__PURE__*/ React.createElement(
            "span",
            {
              style: {
                fontFamily: "var(--font-mono)",
                fontSize: 10,
                letterSpacing: ".06em",
                textTransform: "uppercase",
                color: "var(--muted-foreground)",
              },
            },
            label,
          ),
          /*#__PURE__*/ React.createElement("span", null, children),
        );
      }
      Object.assign(window, {
        ColumnsPanel,
      });
    })();
  } catch (e) {
    __ds_ns.__errors.push({
      path: "ui_kits/config/ColumnsPanel.jsx",
      error: String((e && e.message) || e),
    });
  }

  // ui_kits/config/SidePanels.jsx
  try {
    (() => {
      // KanbanMate config — Defaults, Validation, and YAML preview panels.
      const KMS = window.KanbanMateDesignSystem_2463ad;

      // ---- Defaults: board-wide concurrency_cap + move_rate_limit_per_hour ----
      function DefaultsPanel() {
        const data = window.KMConfigData;
        const { Card, Input, Banner, KeyChip } = KMS;
        const [cc, setCc] = React.useState(data.defaults.concurrency_cap);
        const [rl, setRl] = React.useState(
          data.defaults.move_rate_limit_per_hour,
        );
        return /*#__PURE__*/ React.createElement(
          "div",
          {
            style: {
              maxWidth: 620,
              margin: "0 auto",
              display: "flex",
              flexDirection: "column",
              gap: 16,
            },
          },
          /*#__PURE__*/ React.createElement(
            Banner,
            {
              tone: "neutral",
            },
            "Board-wide pipeline defaults from the ",
            /*#__PURE__*/ React.createElement(KeyChip, null, "transitions.yml"),
            " ",
            /*#__PURE__*/ React.createElement(KeyChip, null, "defaults:"),
            " block. The daemon and agents always run non-root.",
          ),
          /*#__PURE__*/ React.createElement(
            Card,
            {
              padding: "none",
            },
            /*#__PURE__*/ React.createElement(
              SettingRow,
              {
                label: "concurrency_cap",
                hint: "Maximum concurrent agent sessions across the whole project.",
              },
              /*#__PURE__*/ React.createElement(Input, {
                type: "number",
                value: cc,
                onChange: (e) => setCc(e.target.value),
                mono: true,
                style: {
                  width: 88,
                },
              }),
            ),
            /*#__PURE__*/ React.createElement("div", {
              style: {
                height: 1,
                background: "var(--border)",
              },
            }),
            /*#__PURE__*/ React.createElement(
              SettingRow,
              {
                label: "move_rate_limit_per_hour",
                hint: "Per-item AUTO / bot move rate limit per hour.",
              },
              /*#__PURE__*/ React.createElement(Input, {
                type: "number",
                value: rl,
                onChange: (e) => setRl(e.target.value),
                mono: true,
                style: {
                  width: 88,
                },
              }),
            ),
          ),
        );
      }
      function SettingRow({ label, hint, children }) {
        return /*#__PURE__*/ React.createElement(
          "div",
          {
            style: {
              display: "flex",
              alignItems: "center",
              gap: 16,
              padding: "14px 18px",
            },
          },
          /*#__PURE__*/ React.createElement(
            "div",
            {
              style: {
                flex: 1,
                minWidth: 0,
              },
            },
            /*#__PURE__*/ React.createElement(
              "div",
              {
                style: {
                  fontFamily: "var(--font-mono)",
                  fontSize: "var(--text-sm)",
                  fontWeight: 600,
                  color: "var(--foreground)",
                },
              },
              label,
            ),
            /*#__PURE__*/ React.createElement(
              "div",
              {
                style: {
                  fontSize: 12,
                  color: "var(--muted-foreground)",
                  marginTop: 3,
                  lineHeight: 1.45,
                },
              },
              hint,
            ),
          ),
          children,
        );
      }

      // ---- Validation: V1–V10 findings; errors block save, warnings advisory ----
      function ValidationPanel({ findings = [], onGoto }) {
        const { FindingItem, Banner } = KMS;
        const errs = findings.filter((f) => f.severity === "error");
        const warns = findings.filter((f) => f.severity === "warning");
        return /*#__PURE__*/ React.createElement(
          "div",
          {
            style: {
              maxWidth: 760,
              margin: "0 auto",
              display: "flex",
              flexDirection: "column",
              gap: 14,
            },
          },
          errs.length > 0
            ? /*#__PURE__*/ React.createElement(
                Banner,
                {
                  tone: "error",
                  title: `${errs.length} error${errs.length > 1 ? "s" : ""} block save`,
                },
                "Fix the located fields below \u2014 nothing is written until they pass.",
              )
            : /*#__PURE__*/ React.createElement(
                Banner,
                {
                  tone: "success",
                  title: "Config is valid",
                },
                "All semantic checks pass. Save writes columns.yml + transitions.yml.",
              ),
          warns.length > 0 &&
            /*#__PURE__*/ React.createElement(
              "div",
              {
                style: {
                  fontFamily: "var(--font-mono)",
                  fontSize: 11,
                  letterSpacing: ".06em",
                  textTransform: "uppercase",
                  color: "var(--muted-foreground)",
                  marginTop: 4,
                },
              },
              warns.length,
              " advisory warning",
              warns.length > 1 ? "s" : "",
            ),
          /*#__PURE__*/ React.createElement(
            "div",
            {
              style: {
                display: "flex",
                flexDirection: "column",
                gap: 8,
              },
            },
            findings.map((f, i) =>
              /*#__PURE__*/ React.createElement(FindingItem, {
                key: i,
                severity: f.severity,
                field: f.field,
                message: f.message,
                onClick: () => onGoto && onGoto(f.field),
              }),
            ),
          ),
        );
      }

      // ---- YAML preview: read-only render of the two config files ----
      function YamlPanel() {
        const data = window.KMConfigData;
        const { SegmentedControl } = KMS;
        const [file, setFile] = React.useState("transitions.yml");
        const transitions = [
          `project: ${data.binding.project}`,
          "",
          "defaults:",
          `  concurrency_cap: ${data.defaults.concurrency_cap}`,
          `  move_rate_limit_per_hour: ${data.defaults.move_rate_limit_per_hour}`,
          "",
          "transitions:",
          ...data.transitions.flatMap((t) => {
            const from = Array.isArray(t.from)
              ? `[${t.from.join(", ")}]`
              : t.from;
            const lines = [`  - from: ${from}`, `    to: ${t.to}`];
            if (t.profile) lines.push(`    profile: ${t.profile}`);
            if (t.prompt) lines.push(`    prompt: ${t.prompt}`);
            if (t.script) lines.push(`    script: ${t.script}`);
            lines.push(`    advance: ${t.advance}`);
            lines.push(`    permission_mode: ${t.permission_mode}`);
            return [...lines, ""];
          }),
        ];
        const columns = [
          "columns:",
          ...data.columns.flatMap((c) => {
            const lines = [`  - key: ${c.key}`, `    name: ${c.name}`];
            if (c.cls === "agent") {
              lines.push("    triggers_agent: true");
              if (c.prompt) lines.push(`    prompt: ${c.prompt}`);
              if (c.profile) lines.push(`    permission_profile: ${c.profile}`);
            }
            if (c.cls === "reactive") lines.push("    action: teardown");
            return [...lines, ""];
          }),
        ];
        const lines = file === "transitions.yml" ? transitions : columns;
        return /*#__PURE__*/ React.createElement(
          "div",
          {
            style: {
              maxWidth: 760,
              margin: "0 auto",
              display: "flex",
              flexDirection: "column",
              gap: 14,
            },
          },
          /*#__PURE__*/ React.createElement(SegmentedControl, {
            mono: true,
            options: ["transitions.yml", "columns.yml"],
            value: file,
            onChange: setFile,
          }),
          /*#__PURE__*/ React.createElement(
            "div",
            {
              style: {
                background: "var(--surface-inverse)",
                borderRadius: "var(--radius-lg)",
                border: "1px solid var(--border)",
                overflow: "hidden",
                boxShadow: "var(--shadow-sm)",
              },
            },
            /*#__PURE__*/ React.createElement(
              "div",
              {
                style: {
                  display: "flex",
                  alignItems: "center",
                  gap: 7,
                  padding: "9px 14px",
                  borderBottom: "1px solid rgba(255,255,255,0.08)",
                },
              },
              /*#__PURE__*/ React.createElement("span", {
                style: {
                  width: 9,
                  height: 9,
                  borderRadius: "50%",
                  background: "#e0494e",
                },
              }),
              /*#__PURE__*/ React.createElement("span", {
                style: {
                  width: 9,
                  height: 9,
                  borderRadius: "50%",
                  background: "#d98e29",
                },
              }),
              /*#__PURE__*/ React.createElement("span", {
                style: {
                  width: 9,
                  height: 9,
                  borderRadius: "50%",
                  background: "#1f9d54",
                },
              }),
              /*#__PURE__*/ React.createElement(
                "span",
                {
                  style: {
                    marginLeft: 8,
                    fontFamily: "var(--font-mono)",
                    fontSize: 11,
                    color: "rgba(255,255,255,0.55)",
                  },
                },
                ".claude/kanban/",
                file,
              ),
            ),
            /*#__PURE__*/ React.createElement(
              "pre",
              {
                style: {
                  margin: 0,
                  padding: "14px 18px",
                  fontFamily: "var(--font-mono)",
                  fontSize: 12.5,
                  lineHeight: 1.65,
                  color: "#e2e2d6",
                  overflow: "auto",
                  maxHeight: 460,
                },
              },
              lines.map((l, i) =>
                /*#__PURE__*/ React.createElement(
                  "div",
                  {
                    key: i,
                  },
                  /*#__PURE__*/ React.createElement(
                    "span",
                    {
                      style: {
                        display: "inline-block",
                        width: 26,
                        color: "rgba(255,255,255,0.28)",
                        userSelect: "none",
                      },
                    },
                    l ? i + 1 : "",
                  ),
                  /*#__PURE__*/ React.createElement("span", {
                    dangerouslySetInnerHTML: {
                      __html: highlight(l),
                    },
                  }),
                ),
              ),
            ),
          ),
        );
      }
      function highlight(line) {
        const esc = line.replace(/&/g, "&amp;").replace(/</g, "&lt;");
        return esc
          .replace(
            /^(\s*-?\s*)([a-z_]+)(:)/,
            '$1<span style="color:#6cd097">$2</span><span style="color:rgba(255,255,255,0.4)">$3</span>',
          )
          .replace(
            /(triggers_agent|action): (true|teardown)/,
            '<span style="color:#6cd097">$1</span><span style="color:rgba(255,255,255,0.4)">:</span> <span style="color:#b6a3e6">$2</span>',
          );
      }
      Object.assign(window, {
        DefaultsPanel,
        ValidationPanel,
        YamlPanel,
      });
    })();
  } catch (e) {
    __ds_ns.__errors.push({
      path: "ui_kits/config/SidePanels.jsx",
      error: String((e && e.message) || e),
    });
  }

  // ui_kits/config/TransitionsPanel.jsx
  try {
    (() => {
      // KanbanMate config — Transitions whitelist panel. The central object of the editor:
      // from → to rows carrying profile / permission_mode / advance / launch marker. Editing
      // a row opens a Dialog. Composes TransitionRow, Dialog, Select, Input, Textarea, Button,
      // IconButton, KeyChip, ProfileTag, Banner.
      const KMT = window.KanbanMateDesignSystem_2463ad;
      function TransitionsPanel({ findings = [] }) {
        const data = window.KMConfigData;
        const [rows] = React.useState(data.transitions);
        const [editIdx, setEditIdx] = React.useState(null);
        const {
          TransitionRow,
          Dialog,
          Select,
          Textarea,
          Button,
          IconButton,
          KeyChip,
          ProfileTag,
          Banner,
        } = KMT;
        const colKeys = data.columns.map((c) => c.key);
        const invalidIdx = new Set(
          findings
            .filter((f) => f.severity === "error")
            .map((f) => {
              const m = /transitions\[(\d+)\]/.exec(f.field);
              return m ? Number(m[1]) : -1;
            }),
        );
        const edit = editIdx != null ? rows[editIdx] : null;
        const fmt = (v) => (Array.isArray(v) ? v.join(" · ") : v);
        return /*#__PURE__*/ React.createElement(
          "div",
          {
            style: {
              maxWidth: 900,
              margin: "0 auto",
            },
          },
          /*#__PURE__*/ React.createElement(
            Banner,
            {
              tone: "neutral",
              style: {
                marginBottom: 16,
              },
            },
            /*#__PURE__*/ React.createElement(
              "span",
              null,
              "The whitelist is order-sensitive \u2014 earlier rows win, and a ",
              /*#__PURE__*/ React.createElement(KeyChip, null, "*"),
              " wildcard shadows specific rows below it. A row ",
              /*#__PURE__*/ React.createElement(
                "b",
                {
                  style: {
                    color: "var(--col-agent-fg)",
                  },
                },
                "launches",
              ),
              " when its destination is an agent column.",
            ),
          ),
          /*#__PURE__*/ React.createElement(
            "div",
            {
              style: {
                background: "var(--card)",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius-lg)",
                overflow: "hidden",
                boxShadow: "var(--shadow-xs)",
              },
            },
            /*#__PURE__*/ React.createElement(
              "div",
              {
                style: {
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "10px 14px",
                  borderBottom: "1px solid var(--border)",
                  background: "var(--muted)",
                },
              },
              /*#__PURE__*/ React.createElement(
                "span",
                {
                  style: {
                    fontFamily: "var(--font-mono)",
                    fontSize: 11,
                    letterSpacing: ".06em",
                    textTransform: "uppercase",
                    color: "var(--muted-foreground)",
                    flex: 1,
                  },
                },
                "transitions.yml \xB7 ",
                rows.length,
                " rows",
              ),
              /*#__PURE__*/ React.createElement(
                Button,
                {
                  variant: "secondary",
                  size: "sm",
                },
                "+ Add transition",
              ),
            ),
            rows.map((r, i) =>
              /*#__PURE__*/ React.createElement(TransitionRow, {
                key: i,
                fromCol: r.from,
                toCol: r.to,
                profile: r.profile,
                permissionMode: r.permission_mode,
                willLaunch: r.willLaunch,
                advance: r.advance,
                invalid: invalidIdx.has(i),
                selected: editIdx === i,
                onClick: () => setEditIdx(i),
                actions: /*#__PURE__*/ React.createElement(
                  IconButton,
                  {
                    "aria-label": "edit",
                    size: "sm",
                    onClick: (e) => {
                      e.stopPropagation();
                      setEditIdx(i);
                    },
                  },
                  "\u270E",
                ),
              }),
            ),
          ),
          /*#__PURE__*/ React.createElement(
            Dialog,
            {
              open: edit != null,
              onClose: () => setEditIdx(null),
              width: 560,
              title: edit ? "Edit transition" : "",
              description: edit ? `${fmt(edit.from)} → ${fmt(edit.to)}` : "",
              footer: /*#__PURE__*/ React.createElement(
                React.Fragment,
                null,
                /*#__PURE__*/ React.createElement(
                  Button,
                  {
                    variant: "ghost",
                    onClick: () => setEditIdx(null),
                  },
                  "Cancel",
                ),
                /*#__PURE__*/ React.createElement(
                  Button,
                  {
                    variant: "primary",
                    onClick: () => setEditIdx(null),
                  },
                  "Apply",
                ),
              ),
            },
            edit &&
              /*#__PURE__*/ React.createElement(
                "div",
                {
                  style: {
                    display: "flex",
                    flexDirection: "column",
                    gap: 16,
                  },
                },
                invalidIdx.has(editIdx) &&
                  /*#__PURE__*/ React.createElement(
                    Banner,
                    {
                      tone: "error",
                      title: "This row blocks save",
                    },
                    findings.find((f) =>
                      f.field.startsWith(`transitions[${editIdx}]`),
                    )?.message,
                  ),
                /*#__PURE__*/ React.createElement(
                  "div",
                  {
                    style: {
                      display: "grid",
                      gridTemplateColumns: "1fr auto 1fr",
                      gap: 12,
                      alignItems: "end",
                    },
                  },
                  /*#__PURE__*/ React.createElement(
                    DField,
                    {
                      label: "from",
                    },
                    /*#__PURE__*/ React.createElement(Select, {
                      options: ["*", ...colKeys],
                      defaultValue: Array.isArray(edit.from) ? "*" : edit.from,
                      style: {
                        width: "100%",
                      },
                    }),
                  ),
                  /*#__PURE__*/ React.createElement(
                    "span",
                    {
                      style: {
                        paddingBottom: 8,
                        color: "var(--col-agent-fg)",
                        fontFamily: "var(--font-mono)",
                        fontWeight: 600,
                        fontSize: 16,
                      },
                    },
                    "\u2192",
                  ),
                  /*#__PURE__*/ React.createElement(
                    DField,
                    {
                      label: "to",
                    },
                    /*#__PURE__*/ React.createElement(Select, {
                      options: colKeys,
                      defaultValue: edit.to,
                      style: {
                        width: "100%",
                      },
                    }),
                  ),
                ),
                /*#__PURE__*/ React.createElement(
                  "div",
                  {
                    style: {
                      display: "grid",
                      gridTemplateColumns: "1fr 1fr",
                      gap: 12,
                    },
                  },
                  /*#__PURE__*/ React.createElement(
                    DField,
                    {
                      label: "profile",
                    },
                    /*#__PURE__*/ React.createElement(Select, {
                      options: ["", "docs", "prepare", "dev", "check"],
                      defaultValue: edit.profile,
                      style: {
                        width: "100%",
                      },
                    }),
                  ),
                  /*#__PURE__*/ React.createElement(
                    DField,
                    {
                      label: "permission_mode",
                    },
                    /*#__PURE__*/ React.createElement(Select, {
                      options: ["auto", "default", "plan", "acceptEdits"],
                      defaultValue:
                        edit.permission_mode === "bypassPermissions"
                          ? "acceptEdits"
                          : edit.permission_mode,
                      invalid: invalidIdx.has(editIdx),
                      style: {
                        width: "100%",
                      },
                    }),
                  ),
                ),
                /*#__PURE__*/ React.createElement(
                  "div",
                  {
                    style: {
                      display: "grid",
                      gridTemplateColumns: "1fr 1fr",
                      gap: 12,
                    },
                  },
                  /*#__PURE__*/ React.createElement(
                    DField,
                    {
                      label: "advance",
                    },
                    /*#__PURE__*/ React.createElement(Select, {
                      options: [
                        "stop",
                        "auto:PRCI",
                        "auto:Review",
                        "auto:Done",
                      ],
                      defaultValue: edit.advance,
                      style: {
                        width: "100%",
                      },
                    }),
                  ),
                  /*#__PURE__*/ React.createElement(
                    DField,
                    {
                      label: "on_fail",
                    },
                    /*#__PURE__*/ React.createElement(Select, {
                      options: ["", "move:Blocked", "rollback"],
                      defaultValue: edit.on_fail || "",
                      style: {
                        width: "100%",
                      },
                    }),
                  ),
                ),
                /*#__PURE__*/ React.createElement(
                  DField,
                  {
                    label: "prompt",
                  },
                  /*#__PURE__*/ React.createElement(Textarea, {
                    rows: 3,
                    defaultValue: edit.prompt || "",
                    placeholder:
                      "No prompt \u2014 script-only / no-op transition",
                  }),
                ),
                /*#__PURE__*/ React.createElement(
                  "div",
                  {
                    style: {
                      fontFamily: "var(--font-mono)",
                      fontSize: 11,
                      color: "var(--muted-foreground)",
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                    },
                  },
                  "launch: ",
                  edit.willLaunch
                    ? /*#__PURE__*/ React.createElement(
                        "span",
                        {
                          style: {
                            color: "var(--col-agent-fg)",
                            fontWeight: 600,
                          },
                        },
                        "fires agent",
                      )
                    : /*#__PURE__*/ React.createElement("span", null, "no-op"),
                  "\xB7 ",
                  /*#__PURE__*/ React.createElement(
                    "span",
                    {
                      style: {
                        color: "var(--health-blocked-fg)",
                      },
                    },
                    "bypassPermissions is never allowed",
                  ),
                ),
              ),
          ),
        );
      }
      function DField({ label, children }) {
        return /*#__PURE__*/ React.createElement(
          "label",
          {
            style: {
              display: "flex",
              flexDirection: "column",
              gap: 7,
            },
          },
          /*#__PURE__*/ React.createElement(
            "span",
            {
              style: {
                fontFamily: "var(--font-mono)",
                fontSize: 11,
                color: "var(--muted-foreground)",
              },
            },
            label,
          ),
          children,
        );
      }
      Object.assign(window, {
        TransitionsPanel,
      });
    })();
  } catch (e) {
    __ds_ns.__errors.push({
      path: "ui_kits/config/TransitionsPanel.jsx",
      error: String((e && e.message) || e),
    });
  }

  // ui_kits/config/data.js
  try {
    (() => {
      // KanbanMate configuration interface — seed data.
      // Grounded in the real model: columns.yml (11 shipped columns), transitions.yml
      // (whitelist rows: from→to + profile/prompt/script/advance/on_fail/permission_mode),
      // defaults (concurrency_cap, move_rate_limit_per_hour) and the GitHub binding.
      // Source: IznoCorp/kanban-mate — core/config_model.py, docs/columns.md.

      window.KMConfigData = {
        binding: {
          project: "IznoCorp/kanban-mate",
          branch: "main",
        },
        defaults: {
          concurrency_cap: 3,
          move_rate_limit_per_hour: 10,
        },
        // The 11 shipped columns (docs/columns.md). class: agent | reactive | inert.
        columns: [
          {
            key: "Backlog",
            name: "Backlog",
            cls: "inert",
            note: "Manual entry point. Also the reset target from Cancel.",
          },
          {
            key: "Spec",
            name: "Spec",
            cls: "inert",
            note: "Human gate. Brainstorming is interactive.",
          },
          {
            key: "Planned",
            name: "Planned",
            cls: "inert",
            note: "Human gate. Create-branch is interactive.",
          },
          {
            key: "ReadyToDev",
            name: "Ready to dev",
            cls: "inert",
            note: "Final go / no-go before development.",
          },
          {
            key: "InProgress",
            name: "In Progress",
            cls: "agent",
            note: "Unattended-safe.",
            prompt: "/implement:phase",
            profile: "dev",
            permission_mode: "acceptEdits",
            interactive_only: false,
          },
          {
            key: "PRCI",
            name: "PR / CI",
            cls: "agent",
            note: "",
            prompt: "/implement:feature-pr",
            profile: "dev",
            permission_mode: "acceptEdits",
            interactive_only: false,
          },
          {
            key: "Review",
            name: "Review",
            cls: "agent",
            note: "No auto-merge.",
            prompt: "/implement:pr-review",
            profile: "check",
            permission_mode: "plan",
            interactive_only: false,
          },
          {
            key: "Merge",
            name: "Merge",
            cls: "inert",
            note: "Human only — the bot cannot reach it. Merge is always a human action.",
          },
          {
            key: "Cancel",
            name: "Cancel",
            cls: "reactive",
            note: "action: teardown. Moving here kills the session. Cancel → Backlog = resume reset.",
            script: "teardown.sh",
          },
          {
            key: "Done",
            name: "Done",
            cls: "inert",
            note: "Terminal column for completed work.",
          },
          {
            key: "Blocked",
            name: "Blocked",
            cls: "inert",
            note: "The daemon or reaper parks stalled / broken tickets here.",
          },
        ],
        // Whitelist transition rows (transitions.yml authoring shape). willLaunch = to_col is an agent column.
        transitions: [
          {
            from: "ReadyToDev",
            to: "InProgress",
            profile: "dev",
            permission_mode: "acceptEdits",
            advance: "auto:PRCI",
            willLaunch: true,
            prompt: "/implement:phase",
          },
          {
            from: "InProgress",
            to: "PRCI",
            profile: "dev",
            permission_mode: "acceptEdits",
            advance: "auto:Review",
            willLaunch: true,
            prompt: "/implement:feature-pr",
          },
          {
            from: "PRCI",
            to: "Review",
            profile: "check",
            permission_mode: "plan",
            advance: "stop",
            willLaunch: true,
            prompt: "/implement:pr-review",
          },
          {
            from: "Review",
            to: "Merge",
            profile: "",
            permission_mode: "auto",
            advance: "stop",
            willLaunch: false,
            prompt: null,
          },
          {
            from: ["Backlog", "Spec", "Planned", "ReadyToDev"],
            to: "Cancel",
            profile: "",
            permission_mode: "auto",
            advance: "stop",
            on_fail: "",
            willLaunch: false,
            script: "teardown.sh",
          },
          {
            from: "Cancel",
            to: "Backlog",
            profile: "",
            permission_mode: "auto",
            advance: "stop",
            willLaunch: false,
            prompt: null,
          },
          {
            from: "*",
            to: "Blocked",
            profile: "",
            permission_mode: "auto",
            advance: "stop",
            willLaunch: false,
            prompt: null,
          },
        ],
        // Validation findings (config_validate.py V1–V10). error blocks save; warning advisory.
        findings: [
          {
            severity: "error",
            field: "transitions[2].permission_mode",
            message:
              'permission_mode "bypassPermissions" is not allowed. bypassPermissions is NEVER allowed — use plan, acceptEdits, or auto.',
          },
          {
            severity: "warning",
            field: "transitions[6].from",
            message:
              'wildcard "*" shadows 2 earlier rows. Later specific transitions from the same source are unreachable — move this row last.',
          },
          {
            severity: "warning",
            field: "defaults.concurrency_cap",
            message:
              "concurrency_cap 3 with 4 agent edges: under burst, queued moves wait. Raise the cap or accept serialized launches.",
          },
        ],
      };
    })();
  } catch (e) {
    __ds_ns.__errors.push({
      path: "ui_kits/config/data.js",
      error: String((e && e.message) || e),
    });
  }

  __ds_ns.Button = __ds_scope.Button;

  __ds_ns.Card = __ds_scope.Card;

  __ds_ns.Checkbox = __ds_scope.Checkbox;

  __ds_ns.IconButton = __ds_scope.IconButton;

  __ds_ns.Input = __ds_scope.Input;

  __ds_ns.SegmentedControl = __ds_scope.SegmentedControl;

  __ds_ns.Select = __ds_scope.Select;

  __ds_ns.Switch = __ds_scope.Switch;

  __ds_ns.Textarea = __ds_scope.Textarea;

  __ds_ns.Avatar = __ds_scope.Avatar;

  __ds_ns.Badge = __ds_scope.Badge;

  __ds_ns.ColumnClassChip = __ds_scope.ColumnClassChip;

  __ds_ns.HealthPill = __ds_scope.HealthPill;

  __ds_ns.KeyChip = __ds_scope.KeyChip;

  __ds_ns.ProfileTag = __ds_scope.ProfileTag;

  __ds_ns.Banner = __ds_scope.Banner;

  __ds_ns.Dialog = __ds_scope.Dialog;

  __ds_ns.Tooltip = __ds_scope.Tooltip;

  __ds_ns.ColumnCard = __ds_scope.ColumnCard;

  __ds_ns.FindingItem = __ds_scope.FindingItem;

  __ds_ns.TicketCard = __ds_scope.TicketCard;

  __ds_ns.TransitionRow = __ds_scope.TransitionRow;
})();
