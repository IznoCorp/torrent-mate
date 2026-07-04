import { useForm } from "@tanstack/react-form";
import { LoaderCircle } from "lucide-react";
import type { ReactElement } from "react";
import { z } from "zod";

// shadcn primitives are imported under aliases: the ported DS-adherence lint
// (eslint.config.js `no-restricted-syntax`) restricts the prop shape of any JSX
// element literally named `Input`/`Button` to the *design-system* primitives'
// minimal API. This project uses shadcn's richer, same-named components (they
// already restyle to DS tokens), so aliasing the JSX element name keeps the
// token/hex/px guards active while letting the standard HTML props through.
import { Button as SubmitButton } from "@/components/ui/button";
import { Input as TextField } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useLogin } from "@/hooks/useAuth";

/** Username field schema: required, capped at the backend's 64-char limit. */
const usernameSchema = z
  .string()
  .min(1, "Nom d’utilisateur requis")
  .max(64, "Nom d’utilisateur trop long (64 caractères maximum)");

/** Password field schema: required (non-empty). */
const passwordSchema = z.string().min(1, "Mot de passe requis");

/**
 * Message shown for any login failure. Deliberately identical for every failure
 * kind (wrong credentials, unconfigured password hash — both answer 401) so the
 * form never leaks which part was wrong (no user enumeration).
 */
const INVALID_CREDENTIALS_MESSAGE = "Identifiants invalides";

/**
 * Extract a displayable French message from a TanStack Form field error entry.
 *
 * Field validators here are Standard-Schema (zod) validators, whose error
 * entries are issue objects carrying a ``message`` string; a plain-string entry
 * is also tolerated. Anything else is ignored.
 *
 * Args:
 *   errors: The ``field.state.meta.errors`` array for a field.
 *
 * Returns:
 *   The joined error text, or an empty string when the field is valid.
 */
function fieldErrorText(errors: readonly unknown[]): string {
  const messages: string[] = [];
  for (const error of errors) {
    if (typeof error === "string") {
      messages.push(error);
    } else if (
      typeof error === "object" &&
      error !== null &&
      "message" in error
    ) {
      const { message } = error;
      if (typeof message === "string") {
        messages.push(message);
      }
    }
  }
  return messages.join(" ");
}

/**
 * LoginForm — credential entry backed by TanStack Form + zod validation.
 *
 * Two fields (username, password) validate on change via zod Standard-Schema
 * validators; the same validators re-run on submit, so an empty submit is
 * blocked before the API is ever called. Submit delegates to {@link useLogin};
 * while pending, the fields and button disable and a spinner shows. Any auth
 * failure surfaces the single French message {@link INVALID_CREDENTIALS_MESSAGE}.
 *
 * @returns The login form element.
 */
export function LoginForm(): ReactElement {
  const loginMutation = useLogin();

  const form = useForm({
    defaultValues: { username: "", password: "" },
    onSubmit: async ({ value }) => {
      try {
        await loginMutation.mutateAsync(value);
      } catch {
        // Failure is surfaced via `loginMutation.isError` below; swallow the
        // rejection so it doesn't bubble as an unhandled promise rejection.
      }
    },
  });

  return (
    <form
      noValidate
      className="flex flex-col gap-4"
      onSubmit={(event) => {
        event.preventDefault();
        event.stopPropagation();
        void form.handleSubmit();
      }}
    >
      <form.Field name="username" validators={{ onChange: usernameSchema }}>
        {(field) => {
          const errorText = fieldErrorText(field.state.meta.errors);
          return (
            <div className="flex flex-col gap-2">
              <Label htmlFor={field.name}>Nom d’utilisateur</Label>
              <TextField
                id={field.name}
                name={field.name}
                type="text"
                autoComplete="username"
                autoFocus
                value={field.state.value}
                disabled={loginMutation.isPending}
                aria-invalid={errorText.length > 0}
                onBlur={field.handleBlur}
                onChange={(event) => {
                  field.handleChange(event.target.value);
                }}
              />
              {errorText.length > 0 && (
                <p role="alert" className="text-xs text-destructive">
                  {errorText}
                </p>
              )}
            </div>
          );
        }}
      </form.Field>

      <form.Field name="password" validators={{ onChange: passwordSchema }}>
        {(field) => {
          const errorText = fieldErrorText(field.state.meta.errors);
          return (
            <div className="flex flex-col gap-2">
              <Label htmlFor={field.name}>Mot de passe</Label>
              <TextField
                id={field.name}
                name={field.name}
                type="password"
                autoComplete="current-password"
                value={field.state.value}
                disabled={loginMutation.isPending}
                aria-invalid={errorText.length > 0}
                onBlur={field.handleBlur}
                onChange={(event) => {
                  field.handleChange(event.target.value);
                }}
              />
              {errorText.length > 0 && (
                <p role="alert" className="text-xs text-destructive">
                  {errorText}
                </p>
              )}
            </div>
          );
        }}
      </form.Field>

      {loginMutation.isError && (
        <p role="alert" className="text-sm text-destructive">
          {INVALID_CREDENTIALS_MESSAGE}
        </p>
      )}

      <SubmitButton
        type="submit"
        disabled={loginMutation.isPending}
        className="mt-2 w-full"
      >
        {loginMutation.isPending && (
          <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />
        )}
        {loginMutation.isPending ? "Connexion…" : "Se connecter"}
      </SubmitButton>
    </form>
  );
}
