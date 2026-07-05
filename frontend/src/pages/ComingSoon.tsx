import { Construction } from "lucide-react";
import type { ReactElement } from "react";

/** Props for {@link ComingSoon}. */
interface ComingSoonProps {
  /** Section title (French), e.g. "Pipeline". */
  readonly title: string;
  /** Delivery wave tag, e.g. "S2" — rendered in monospace tabular numerals. */
  readonly wave: string;
}

/**
 * ComingSoon — the shared "À venir" placeholder for the S2–S7 route slots.
 *
 * Every declared-but-unbuilt slot (`/pipeline`, `/maintenance`, `/config`,
 * `/scraping`, `/registry`, `/acquisition`) renders this page so navigation and
 * gating exist from day one (DESIGN §5.2). The wave tag makes it obvious which
 * wave will replace the stub.
 *
 * @returns The placeholder element.
 */
export default function ComingSoon({
  title,
  wave,
}: ComingSoonProps): ReactElement {
  return (
    <section className="mx-auto flex max-w-xl flex-col items-center gap-4 py-16 text-center">
      <Construction
        className="size-10 text-muted-foreground"
        aria-hidden="true"
      />
      <div className="flex flex-col items-center gap-2">
        <div className="flex items-center gap-2">
          <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
          <span className="rounded-md border border-border px-2 py-0.5 font-mono text-xs tabular-nums text-muted-foreground">
            {wave}
          </span>
        </div>
        <p className="text-sm text-muted-foreground">
          À venir — cette section sera livrée dans une prochaine vague.
        </p>
      </div>
    </section>
  );
}
