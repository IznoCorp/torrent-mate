/**
 * SchemaForm — recursive JSON Schema → shadcn form control renderer.
 *
 * Renders a Pydantic v2 ``model_json_schema()`` node (with ``$defs``/``$ref``) as
 * a controlled form.  Each schema ``type`` maps to a specific shadcn control;
 * nested objects and arrays recurse into child {@link SchemaForm} instances.
 *
 * The component is **stateless** — every edit produces a NEW values object via
 * ``onChange`` so the parent owns the truth.
 *
 * This module is a thin composition shell: the recursive dispatcher lives in
 * ``./schema/Renderer`` (``SchemaFormRenderer``), the pure schema logic in
 * ``./schema/engine``, and the per-primitive controls in ``./schema/fields``.
 * ``SchemaForm`` is the public alias for the renderer; the props surface is
 * unchanged (P11.1 decomposition).
 */

/* eslint-disable react-refresh/only-export-components */

export { flattenLocToPath } from "./schema/engine";
export type { SchemaFormProps } from "./schema/types";
export { SchemaFormRenderer as SchemaForm } from "./schema/Renderer";
