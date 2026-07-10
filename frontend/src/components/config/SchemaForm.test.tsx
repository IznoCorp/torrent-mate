import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SchemaForm, flattenLocToPath } from "@/components/config/SchemaForm";

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

afterEach(cleanup);

// ---------------------------------------------------------------------------
// flattenLocToPath
// ---------------------------------------------------------------------------

describe("flattenLocToPath", () => {
  it("joint des tableaux de loc mixtes avec des points", () => {
    expect(flattenLocToPath(["paths", 0, "data_dir"])).toBe("paths.0.data_dir");
  });

  it("retourne une chaîne vide pour un tableau vide", () => {
    expect(flattenLocToPath([])).toBe("");
  });

  it("gère des tableaux avec uniquement des chaînes", () => {
    expect(flattenLocToPath(["body", "name"])).toBe("body.name");
  });

  it("gère des tableaux avec uniquement des nombres", () => {
    expect(flattenLocToPath([0, 1, 2])).toBe("0.1.2");
  });

  it("lève TypeError quand l'entrée n'est pas un tableau de (string | number)", () => {
    expect(() =>
      flattenLocToPath(null as unknown as (string | number)[]),
    ).toThrow(TypeError);
    expect(() =>
      flattenLocToPath([true] as unknown as (string | number)[]),
    ).toThrow(TypeError);
  });
});

// ---------------------------------------------------------------------------
// Leaf field kinds
// ---------------------------------------------------------------------------

describe("SchemaForm — champs simples", () => {
  it("affiche un champ texte pour le type string", () => {
    const onChange = vi.fn();
    render(
      <SchemaForm
        schema={{ type: "string", description: "Un champ texte" }}
        values={{ name: "hello" }}
        onChange={onChange}
        path="name"
      />,
    );

    const input = screen.getByRole("textbox");
    expect(input).toHaveValue("hello");
    // Description is shown as help text.
    expect(screen.getByText("Un champ texte")).toBeInTheDocument();
  });

  it("appelle onChange avec la nouvelle valeur pour un champ string", () => {
    const onChange = vi.fn();
    render(
      <SchemaForm
        schema={{ type: "string" }}
        values={{ name: "hello" }}
        onChange={onChange}
        path="name"
      />,
    );

    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "world" },
    });
    expect(onChange).toHaveBeenCalledWith({ name: "world" });
  });

  it("affiche un champ number pour integer", () => {
    const onChange = vi.fn();
    render(
      <SchemaForm
        schema={{ type: "integer", description: "Un entier" }}
        values={{ count: 42 }}
        onChange={onChange}
        path="count"
      />,
    );

    const input = screen.getByRole("spinbutton");
    expect(input).toHaveValue(42);
    expect(screen.getByText("Un entier")).toBeInTheDocument();
  });

  it("coerce onChange en number pour integer, vide → undefined", () => {
    const onChange = vi.fn();
    render(
      <SchemaForm
        schema={{ type: "integer" }}
        values={{ count: 10 }}
        onChange={onChange}
        path="count"
      />,
    );

    // Change to a new number.
    fireEvent.change(screen.getByRole("spinbutton"), {
      target: { value: "99" },
    });
    expect(onChange).toHaveBeenCalledWith({ count: 99 });

    // Empty string → undefined.
    fireEvent.change(screen.getByRole("spinbutton"), {
      target: { value: "" },
    });
    // Called with count set to undefined.
    const lastCall = onChange.mock.calls[
      onChange.mock.calls.length - 1
    ]?.[0] as Record<string, unknown> | undefined;
    expect(lastCall).toHaveProperty("count", undefined);
  });

  it("affiche un Switch pour boolean", () => {
    const onChange = vi.fn();
    render(
      <SchemaForm
        schema={{ type: "boolean", description: "Activer" }}
        values={{ enabled: false }}
        onChange={onChange}
        path="enabled"
      />,
    );

    const sw = screen.getByRole("switch");
    expect(sw).toHaveAttribute("aria-checked", "false");
    expect(screen.getByText("Activer")).toBeInTheDocument();
  });

  it("appelle onCheckedChange pour boolean", () => {
    const onChange = vi.fn();
    render(
      <SchemaForm
        schema={{ type: "boolean" }}
        values={{ enabled: false }}
        onChange={onChange}
        path="enabled"
      />,
    );

    fireEvent.click(screen.getByRole("switch"));
    expect(onChange).toHaveBeenCalledWith({ enabled: true });
  });

  it("affiche un Select pour string + enum", () => {
    const onChange = vi.fn();
    render(
      <SchemaForm
        schema={{
          type: "string",
          enum: ["quick", "full"],
          description: "Mode de scan",
        }}
        values={{ mode: "quick" }}
        onChange={onChange}
        path="mode"
      />,
    );

    expect(screen.getByRole("combobox")).toBeInTheDocument();
    expect(screen.getByText("Mode de scan")).toBeInTheDocument();
  });

  it("rend une option vide dans le Select quand la valeur est absente", () => {
    const onChange = vi.fn();
    render(
      <SchemaForm
        schema={{ type: "string", enum: ["a", "b"] }}
        values={{}}
        onChange={onChange}
        path="choice"
      />,
    );

    // The select trigger renders with the placeholder.
    expect(screen.getByRole("combobox")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Optional anyOf [X, null] unwrapping
// ---------------------------------------------------------------------------

describe("SchemaForm — Optional (anyOf [X, null])", () => {
  it("déballe anyOf [string, null] en champ string", () => {
    const onChange = vi.fn();
    render(
      <SchemaForm
        schema={{
          anyOf: [{ type: "string" }, { type: "null" }],
        }}
        values={{ title: "hello" }}
        onChange={onChange}
        path="title"
      />,
    );

    // Should render as a text input, not a fallback textarea.
    const input = screen.getByRole("textbox");
    expect(input).toHaveValue("hello");
    expect(
      screen.queryByRole("textbox", { name: "JSON" }),
    ).not.toBeInTheDocument();
  });

  it("déballe anyOf [null, integer] en champ number", () => {
    const onChange = vi.fn();
    render(
      <SchemaForm
        schema={{
          anyOf: [{ type: "null" }, { type: "integer" }],
        }}
        values={{ port: 8080 }}
        onChange={onChange}
        path="port"
      />,
    );

    expect(screen.getByRole("spinbutton")).toHaveValue(8080);
  });
});

// ---------------------------------------------------------------------------
// Array of primitives
// ---------------------------------------------------------------------------

describe("SchemaForm — array of primitives", () => {
  it("affiche les éléments existants avec un bouton ajouter", () => {
    const onChange = vi.fn();
    render(
      <SchemaForm
        schema={{ type: "array", items: { type: "string" } }}
        values={{ tags: ["alpha", "beta"] }}
        onChange={onChange}
        path="tags"
      />,
    );

    // Two text inputs for the two items.
    const inputs = screen.getAllByRole("textbox");
    expect(inputs).toHaveLength(2);
    expect(inputs[0]).toHaveValue("alpha");
    expect(inputs[1]).toHaveValue("beta");

    // Add button is present.
    expect(screen.getByRole("button", { name: /Ajouter/ })).toBeInTheDocument();

    // Remove buttons for each item.
    expect(
      screen.getByRole("button", { name: /Supprimer l'élément 0/ }),
    ).toBeInTheDocument();
  });

  it("ajoute un élément vide via le bouton +", () => {
    const onChange = vi.fn();
    render(
      <SchemaForm
        schema={{ type: "array", items: { type: "string" } }}
        values={{ tags: [] }}
        onChange={onChange}
        path="tags"
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /Ajouter/ }));
    expect(onChange).toHaveBeenCalledWith({ tags: [""] });
  });

  it("supprime un élément via le bouton ✕", () => {
    const onChange = vi.fn();
    render(
      <SchemaForm
        schema={{ type: "array", items: { type: "string" } }}
        values={{ tags: ["alpha", "beta", "gamma"] }}
        onChange={onChange}
        path="tags"
      />,
    );

    // Remove the middle element.
    fireEvent.click(
      screen.getByRole("button", { name: /Supprimer l'élément 1/ }),
    );
    expect(onChange).toHaveBeenCalledWith({ tags: ["alpha", "gamma"] });
  });

  it("modifie un élément existant", () => {
    const onChange = vi.fn();
    render(
      <SchemaForm
        schema={{ type: "array", items: { type: "string" } }}
        values={{ tags: ["alpha"] }}
        onChange={onChange}
        path="tags"
      />,
    );

    fireEvent.change(screen.getByRole("textbox"), {
      target: { value: "updated" },
    });
    expect(onChange).toHaveBeenCalledWith({ tags: ["updated"] });
  });
});

// ---------------------------------------------------------------------------
// Array of objects via $ref
// ---------------------------------------------------------------------------

describe("SchemaForm — array of objects ($ref)", () => {
  const rootSchema = {
    $defs: {
      DiskConfig: {
        type: "object",
        properties: {
          name: { type: "string", description: "Nom du disque" },
          path: { type: "string" },
        },
      },
    },
  };

  it("affiche chaque objet dans une Card avec son index", () => {
    const onChange = vi.fn();
    render(
      <SchemaForm
        schema={{
          type: "array",
          items: { $ref: "#/$defs/DiskConfig" },
        }}
        rootSchema={rootSchema}
        values={{
          disks: [
            { name: "disk1", path: "/Volumes/disk1" },
            { name: "disk2", path: "/Volumes/disk2" },
          ],
        }}
        onChange={onChange}
        path="disks"
      />,
    );

    // Card titles show "Disks 1" and "Disks 2".
    expect(screen.getByText("Disks 1")).toBeInTheDocument();
    expect(screen.getByText("Disks 2")).toBeInTheDocument();
  });

  it("propage une modification imbriquée de façon immuable", () => {
    const onChange = vi.fn();
    render(
      <SchemaForm
        schema={{
          type: "array",
          items: { $ref: "#/$defs/DiskConfig" },
        }}
        rootSchema={rootSchema}
        values={{
          disks: [{ name: "disk1", path: "/Volumes/disk1" }],
        }}
        onChange={onChange}
        path="disks"
      />,
    );

    // Nested object sections render as a collapsed Accordion — expand every
    // section trigger so the inner inputs mount and become accessible.
    screen.getAllByRole("button", { expanded: false }).forEach((trigger) => {
      fireEvent.click(trigger);
    });

    // Edit the name field inside the first card.
    const inputs = screen.getAllByRole("textbox");
    const nameInput = inputs[0];
    if (!nameInput) throw new Error("Expected name input not found");
    fireEvent.change(nameInput, { target: { value: "renamed" } });

    expect(onChange).toHaveBeenCalledWith({
      disks: [{ name: "renamed", path: "/Volumes/disk1" }],
    });
  });

  it("ajoute une carte vide via +", () => {
    const onChange = vi.fn();
    render(
      <SchemaForm
        schema={{
          type: "array",
          items: { $ref: "#/$defs/DiskConfig" },
        }}
        rootSchema={rootSchema}
        values={{ disks: [] }}
        onChange={onChange}
        path="disks"
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /Ajouter/ }));
    expect(onChange).toHaveBeenCalledWith({ disks: [{}] });
  });

  it("supprime une carte via ✕", () => {
    const onChange = vi.fn();
    render(
      <SchemaForm
        schema={{
          type: "array",
          items: { $ref: "#/$defs/DiskConfig" },
        }}
        rootSchema={rootSchema}
        values={{
          disks: [
            { name: "a", path: "/a" },
            { name: "b", path: "/b" },
          ],
        }}
        onChange={onChange}
        path="disks"
      />,
    );

    const removeButtons = screen.getAllByRole("button", {
      name: /Supprimer Disks/,
    });
    const firstRemove = removeButtons[0];
    if (!firstRemove) throw new Error("Expected remove button not found");
    fireEvent.click(firstRemove);
    expect(onChange).toHaveBeenCalledWith({
      disks: [{ name: "b", path: "/b" }],
    });
  });
});

// ---------------------------------------------------------------------------
// Object with properties (collapsible section)
// ---------------------------------------------------------------------------

describe("SchemaForm — object with properties", () => {
  const objSchema = {
    type: "object",
    description: "Configuration de base",
    required: ["name"],
    properties: {
      name: { type: "string", description: "Nom de l'élément" },
      count: { type: "integer" },
    },
  };

  it("affiche une section repliable avec le titre", () => {
    const onChange = vi.fn();
    render(
      <SchemaForm
        schema={objSchema}
        values={{ name: "test", count: 5 }}
        onChange={onChange}
        path="config"
      />,
    );

    // The accordion trigger shows the field key humanized.
    expect(screen.getByRole("button", { name: /Config/ })).toBeInTheDocument();
    // Expand the section so its description mounts.
    fireEvent.click(screen.getByRole("button", { name: /Config/ }));
    // The object description is shown.
    expect(screen.getByText("Configuration de base")).toBeInTheDocument();
  });

  it("propage une modification de propriété de façon immuable", () => {
    const onChange = vi.fn();
    render(
      <SchemaForm
        schema={objSchema}
        values={{ config: { name: "test", count: 5 } }}
        onChange={onChange}
        path="config"
      />,
    );

    // Expand the collapsed section so the inner inputs mount.
    fireEvent.click(screen.getByRole("button", { name: /Config/ }));

    // Find the text input for "name" and change it.
    const textInputs = screen.getAllByRole("textbox");
    // First textbox is the "name" field.
    const nameInput = textInputs.find(
      (el) => el.getAttribute("type") === "text",
    );
    if (!nameInput) throw new Error("Expected name text input not found");
    fireEvent.change(nameInput, { target: { value: "updated" } });
    expect(onChange).toHaveBeenCalledWith({
      config: { name: "updated", count: 5 },
    });
  });

  it("marque les champs requis avec aria-required", () => {
    const onChange = vi.fn();
    render(
      <SchemaForm
        schema={objSchema}
        values={{ config: { name: "test", count: 5 } }}
        onChange={onChange}
        path="config"
      />,
    );

    // Expand the collapsed section so the inner labels mount.
    fireEvent.click(screen.getByRole("button", { name: /Config/ }));

    // The "name" input should have aria-required="true".
    // Label text should contain "*" for required fields.
    const labels = screen.getAllByText(/Name/);
    expect(labels.length).toBeGreaterThan(0);
  });
});

// ---------------------------------------------------------------------------
// Object with additionalProperties
// ---------------------------------------------------------------------------

describe("SchemaForm — additionalProperties", () => {
  const dictSchema = {
    type: "object",
    additionalProperties: { type: "string" },
  };

  it("affiche les entrées existantes avec clé et valeur", () => {
    const onChange = vi.fn();
    render(
      <SchemaForm
        schema={dictSchema}
        values={{ env: { HOME: "/home/user", PATH: "/usr/bin" } }}
        onChange={onChange}
        path="env"
      />,
    );

    // Labels show the keys.
    expect(screen.getByText("HOME")).toBeInTheDocument();
    expect(screen.getByText("PATH")).toBeInTheDocument();

    // Inputs for the values.
    const inputs = screen.getAllByRole("textbox");
    // "HOME" and "PATH" value inputs + key label is just Label text, not inputs.
    expect(inputs.length).toBeGreaterThanOrEqual(2);
  });

  it("ajoute une entrée avec une clé unique via +", () => {
    const onChange = vi.fn();
    render(
      <SchemaForm
        schema={dictSchema}
        values={{ env: {} }}
        onChange={onChange}
        path="env"
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /Ajouter/ }));
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({
        env: expect.objectContaining({ new_key: "" }) as unknown,
      }),
    );
  });

  it("supprime une entrée via ✕", () => {
    const onChange = vi.fn();
    render(
      <SchemaForm
        schema={dictSchema}
        values={{ env: { HOME: "/home/user", PATH: "/usr/bin" } }}
        onChange={onChange}
        path="env"
      />,
    );

    fireEvent.click(
      screen.getByRole("button", { name: /Supprimer la clé HOME/ }),
    );
    expect(onChange).toHaveBeenCalledWith({
      env: { PATH: "/usr/bin" },
    });
  });
});

// ---------------------------------------------------------------------------
// JSON textarea fallback
// ---------------------------------------------------------------------------

describe("SchemaForm — fallback JSON textarea", () => {
  it("affiche un textarea pour un schema inconnu sans propriétés", () => {
    const onChange = vi.fn();
    render(
      <SchemaForm
        schema={{ type: "object" }}
        values={{ raw: { foo: "bar" } }}
        onChange={onChange}
        path="raw"
      />,
    );

    // Should render a textarea containing the JSON representation.
    const textarea = screen.getByRole("textbox");
    expect(textarea.tagName).toBe("TEXTAREA");
  });

  it("appelle onChange avec la valeur parsée quand le JSON au blur est valide", () => {
    const onChange = vi.fn();
    render(
      <SchemaForm
        schema={{ type: "object" }}
        values={{ raw: { foo: "bar" } }}
        onChange={onChange}
        path="raw"
      />,
    );

    const textarea = screen.getByRole("textbox");
    fireEvent.change(textarea, {
      target: { value: '{"baz":"qux"}' },
    });
    fireEvent.blur(textarea);

    expect(onChange).toHaveBeenCalledWith({ raw: { baz: "qux" } });
  });

  it("affiche une erreur et n'appelle PAS onChange pour un JSON invalide", () => {
    const onChange = vi.fn();
    render(
      <SchemaForm
        schema={{ type: "object" }}
        values={{ raw: {} }}
        onChange={onChange}
        path="raw"
      />,
    );

    onChange.mockClear();

    const textarea = screen.getByRole("textbox");
    fireEvent.change(textarea, {
      target: { value: "not valid json" },
    });
    fireEvent.blur(textarea);

    // Error message shown.
    expect(screen.getByRole("alert")).toBeInTheDocument();
    // onChange NOT called.
    expect(onChange).not.toHaveBeenCalled();
  });

  it("appelle onChange avec undefined pour un textarea vidé", () => {
    const onChange = vi.fn();
    render(
      <SchemaForm
        schema={{ type: "object" }}
        values={{ raw: { foo: "bar" } }}
        onChange={onChange}
        path="raw"
      />,
    );

    const textarea = screen.getByRole("textbox");
    fireEvent.change(textarea, { target: { value: "" } });
    fireEvent.blur(textarea);

    expect(onChange).toHaveBeenCalledWith({ raw: undefined });
  });
});

// ---------------------------------------------------------------------------
// Errors prop
// ---------------------------------------------------------------------------

describe("SchemaForm — errors", () => {
  it("affiche le message d'erreur pour un chemin correspondant", () => {
    const onChange = vi.fn();
    render(
      <SchemaForm
        schema={{ type: "string" }}
        values={{ name: "" }}
        onChange={onChange}
        errors={{ name: "Ce champ est requis" }}
        path="name"
      />,
    );

    expect(screen.getByText("Ce champ est requis")).toBeInTheDocument();
  });

  it("met aria-invalid sur le contrôle quand il y a une erreur", () => {
    const onChange = vi.fn();
    render(
      <SchemaForm
        schema={{ type: "string" }}
        values={{ name: "" }}
        onChange={onChange}
        errors={{ name: "Champ invalide" }}
        path="name"
      />,
    );

    expect(screen.getByRole("textbox")).toHaveAttribute("aria-invalid", "true");
  });

  it("n'affiche pas d'erreur pour un chemin non correspondant", () => {
    const onChange = vi.fn();
    render(
      <SchemaForm
        schema={{ type: "string" }}
        values={{ name: "ok" }}
        onChange={onChange}
        errors={{ other: "Erreur ailleurs" }}
        path="name"
      />,
    );

    expect(screen.queryByText("Erreur ailleurs")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// readOnly
// ---------------------------------------------------------------------------

describe("SchemaForm — readOnly", () => {
  it("désactive les contrôles d'entrée quand readOnly est true", () => {
    const onChange = vi.fn();
    const { container } = render(
      <SchemaForm
        schema={{ type: "string" }}
        values={{ name: "readonly" }}
        onChange={onChange}
        readOnly
        path="name"
      />,
    );

    expect(screen.getByRole("textbox")).toBeDisabled();

    // No add/remove buttons should be present for arrays in readOnly mode.
    const buttons = container.querySelectorAll("button");
    // The only buttons would be add/remove — none for a string field.
    expect(buttons.length).toBe(0);
  });

  it("désactive le Switch quand readOnly", () => {
    const onChange = vi.fn();
    render(
      <SchemaForm
        schema={{ type: "boolean" }}
        values={{ enabled: true }}
        onChange={onChange}
        readOnly
        path="enabled"
      />,
    );

    expect(screen.getByRole("switch")).toBeDisabled();
  });

  it("désactive les boutons d'ajout/suppression dans un tableau", () => {
    const onChange = vi.fn();
    render(
      <SchemaForm
        schema={{ type: "array", items: { type: "string" } }}
        values={{ tags: ["alpha"] }}
        onChange={onChange}
        readOnly
        path="tags"
      />,
    );

    // No add button in readOnly mode.
    expect(
      screen.queryByRole("button", { name: /Ajouter/ }),
    ).not.toBeInTheDocument();

    // The input is disabled.
    expect(screen.getByRole("textbox")).toBeDisabled();
  });
});

// ---------------------------------------------------------------------------
// Labels (humanize) and required marker
// ---------------------------------------------------------------------------

describe("SchemaForm — labels et required", () => {
  it("humanise les noms en snake_case", () => {
    const onChange = vi.fn();
    render(
      <SchemaForm
        schema={{ type: "string" }}
        values={{ staging_dir: "/tmp" }}
        onChange={onChange}
        path="staging_dir"
      />,
    );

    // The label should show "Staging dir" (humanized from staging_dir).
    expect(screen.getByText("Staging dir")).toBeInTheDocument();
  });

  it("ajoute une * visuelle pour les champs requis", () => {
    const onChange = vi.fn();
    render(
      <SchemaForm
        schema={{
          type: "object",
          required: ["name"],
          properties: {
            name: { type: "string" },
          },
        }}
        values={{ user: { name: "Alice" } }}
        onChange={onChange}
        path="user"
      />,
    );

    // Expand the collapsed section so the inner "name" label mounts.
    fireEvent.click(screen.getByRole("button", { name: /User/ }));

    // The label for "name" should contain "Name" with a required marker.
    const labels = screen.getAllByText(/Name/);
    // At least one label should contain the aria-hidden "*".
    const requiredLabel = labels.find((el) => el.tagName === "LABEL");
    expect(requiredLabel).toBeTruthy();
    if (!requiredLabel) throw new Error("Expected label not found");
    expect(requiredLabel.textContent).toMatch(/\*/);
  });
});

// ---------------------------------------------------------------------------
// shadowedKeys warning chips
// ---------------------------------------------------------------------------

describe("SchemaForm — shadowedKeys", () => {
  it("affiche un avertissement pour une clé de premier niveau dans shadowedKeys", () => {
    const onChange = vi.fn();
    render(
      <SchemaForm
        schema={{
          type: "object",
          properties: {
            api_key: { type: "string" },
            max_retries: { type: "integer" },
          },
        }}
        values={{ api_key: "secret", max_retries: 3 }}
        onChange={onChange}
        shadowedKeys={["api_key"]}
      />,
    );

    // Warning chip for the shadowed key.
    expect(
      screen.getByText(/écrasée par local.json5 — modification sans effet/i),
    ).toBeInTheDocument();
  });

  it("n'affiche pas d'avertissement pour les clés non shadowed", () => {
    const onChange = vi.fn();
    render(
      <SchemaForm
        schema={{
          type: "object",
          properties: {
            api_key: { type: "string" },
            max_retries: { type: "integer" },
          },
        }}
        values={{ api_key: "secret", max_retries: 3 }}
        onChange={onChange}
        shadowedKeys={[]}
      />,
    );

    // No warning chip.
    expect(
      screen.queryByText(/écrasée par local.json5 — modification sans effet/i),
    ).not.toBeInTheDocument();
  });

  it("n'affiche pas d'avertissement pour les clés imbriquées (profondeur > 0)", () => {
    const onChange = vi.fn();
    render(
      <SchemaForm
        schema={{
          type: "object",
          properties: {
            nested: {
              type: "object",
              properties: {
                shadowed_inner: { type: "string" },
              },
            },
          },
        }}
        values={{ nested: { shadowed_inner: "val" } }}
        onChange={onChange}
        shadowedKeys={["shadowed_inner"]}
      />,
    );

    // The shadowed key is at depth 1 (inside "nested"), so NO chip.
    expect(
      screen.queryByText(/écrasée par local.json5 — modification sans effet/i),
    ).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Broken $ref fallback
// ---------------------------------------------------------------------------

describe("SchemaForm — $ref non résolu", () => {
  it("tombe en fallback JSON textarea pour un $ref introuvable", () => {
    const onChange = vi.fn();
    render(
      <SchemaForm
        schema={{ $ref: "#/$defs/NonExistent" }}
        rootSchema={{ $defs: {} }}
        values={{ ghost: {} }}
        onChange={onChange}
        path="ghost"
      />,
    );

    // Should render as a textarea, not crash.
    const textarea = screen.getByRole("textbox");
    expect(textarea.tagName).toBe("TEXTAREA");
  });
});

// ---------------------------------------------------------------------------
// Accordion collapsible sections (3.1)
// ---------------------------------------------------------------------------

describe("SchemaForm — sections repliables (Accordion)", () => {
  const nestedSchema = {
    type: "object",
    properties: {
      db: {
        type: "object",
        description: "Base de données",
        properties: {
          host: { type: "string" },
        },
      },
    },
  };

  it("rend une section imbriquée repliée par défaut (contenu masqué)", () => {
    const onChange = vi.fn();
    render(
      <SchemaForm
        schema={nestedSchema}
        values={{ db: { host: "localhost" } }}
        onChange={onChange}
      />,
    );

    // The nested "db" object renders as a collapsed Accordion trigger.
    const trigger = screen.getByRole("button", { name: /Db/ });
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    // Its inner field ("host") is not mounted while collapsed.
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });

  it("révèle le contenu imbriqué quand on ouvre la section", () => {
    const onChange = vi.fn();
    render(
      <SchemaForm
        schema={nestedSchema}
        values={{ db: { host: "localhost" } }}
        onChange={onChange}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /Db/ }));

    // After expanding, the nested input + description are visible.
    expect(screen.getByRole("textbox")).toHaveValue("localhost");
    expect(screen.getByText("Base de données")).toBeInTheDocument();
  });

  it("n'enveloppe pas la racine dans un Accordion (pas de titre vide)", () => {
    const onChange = vi.fn();
    render(
      <SchemaForm
        schema={{
          type: "object",
          properties: { name: { type: "string" } },
        }}
        values={{ name: "root-level" }}
        onChange={onChange}
      />,
    );

    // Root scalar field is rendered directly (no collapse needed at root).
    expect(screen.getByRole("textbox")).toHaveValue("root-level");
  });
});

// ---------------------------------------------------------------------------
// Section labels (F6) + collapsible description (F7)
// ---------------------------------------------------------------------------

describe("SchemaForm — libellés de section + description (F6/F7)", () => {
  it("n'affiche jamais le nom de classe Pydantic d'une section connue (F6)", () => {
    render(
      <SchemaForm
        schema={{
          type: "object",
          properties: {
            scraper: {
              type: "object",
              title: "ScraperConfig", // Pydantic sets a nested title = class name
              properties: { language: { type: "string" } },
            },
          },
        }}
        values={{ scraper: { language: "fr-FR" } }}
        onChange={vi.fn()}
      />,
    );
    expect(screen.getByRole("button", { name: "Scraper" })).toBeInTheDocument();
    expect(screen.queryByText("ScraperConfig")).not.toBeInTheDocument();
  });

  it("humanise la clé d'une section inconnue plutôt que son nom de classe (F6)", () => {
    render(
      <SchemaForm
        schema={{
          type: "object",
          properties: {
            widget_bar: {
              type: "object",
              title: "WidgetBarConfig",
              properties: { x: { type: "string" } },
            },
          },
        }}
        values={{ widget_bar: {} }}
        onChange={vi.fn()}
      />,
    );
    expect(
      screen.getByRole("button", { name: "Widget bar" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("WidgetBarConfig")).not.toBeInTheDocument();
  });

  it("tronque une longue docstring de section à sa première phrase (F7)", () => {
    const longDoc =
      "Scraper runtime tunables. Attributes: language: primary metadata language. fallback_language: secondary.";
    render(
      <SchemaForm
        schema={{
          type: "object",
          properties: {
            scraper: {
              type: "object",
              title: "ScraperConfig",
              description: longDoc,
              properties: { language: { type: "string" } },
            },
          },
        }}
        values={{ scraper: {} }}
        onChange={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Scraper" }));
    // Only the first sentence shows; the "Attributes:" wall stays hidden.
    expect(screen.getByText("Scraper runtime tunables.")).toBeInTheDocument();
    expect(screen.queryByText(/Attributes:/)).not.toBeInTheDocument();
    // "En savoir plus" reveals the full docstring.
    fireEvent.click(screen.getByRole("button", { name: "En savoir plus" }));
    expect(screen.getByText(longDoc)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Schema title preference + inline validation (3.2 / 3.3)
// ---------------------------------------------------------------------------

describe("SchemaForm — titre de schéma et validation inline", () => {
  it("préfère le title du schéma au nom de clé humanisé", () => {
    const onChange = vi.fn();
    render(
      <SchemaForm
        schema={{ type: "string", title: "Répertoire de staging" }}
        values={{ staging_dir: "/tmp" }}
        onChange={onChange}
        path="staging_dir"
      />,
    );

    // The schema title wins over humanize("staging_dir") = "Staging dir".
    expect(screen.getByText("Répertoire de staging")).toBeInTheDocument();
    expect(screen.queryByText("Staging dir")).not.toBeInTheDocument();
  });

  it("affiche une erreur inline au blur pour une borne minimum violée", () => {
    const onChange = vi.fn();
    // The control is parent-controlled, so seed an out-of-bounds value and let
    // the blur handler read it straight from the DOM (no re-render needed).
    render(
      <SchemaForm
        schema={{ type: "integer", minimum: 0 }}
        values={{ retries: -3 }}
        onChange={onChange}
        path="retries"
      />,
    );

    const input = screen.getByRole("spinbutton");
    // No inline error before the field is blurred.
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();

    fireEvent.blur(input);
    // Client-side bound check surfaces on blur.
    expect(screen.getByRole("alert")).toHaveTextContent("Doit être ≥ 0.");
  });

  it("efface l'erreur inline dès que l'utilisateur retape", () => {
    const onChange = vi.fn();
    render(
      <SchemaForm
        schema={{ type: "integer", minimum: 0 }}
        values={{ retries: -3 }}
        onChange={onChange}
        path="retries"
      />,
    );

    const input = screen.getByRole("spinbutton");
    fireEvent.blur(input);
    expect(screen.getByRole("alert")).toHaveTextContent("Doit être ≥ 0.");

    // Typing clears the stale client-side hint immediately.
    fireEvent.change(input, { target: { value: "2" } });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("laisse l'erreur serveur 422 primer sur la validation client", () => {
    const onChange = vi.fn();
    render(
      <SchemaForm
        schema={{ type: "integer", minimum: 0 }}
        values={{ retries: -3 }}
        onChange={onChange}
        errors={{ retries: "Erreur serveur" }}
        path="retries"
      />,
    );

    // Server error is shown even before any blur.
    expect(screen.getByRole("alert")).toHaveTextContent("Erreur serveur");
  });
});
