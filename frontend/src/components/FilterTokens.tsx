import type { Filters } from "@/lib/chat";
import { COPY, dirOf, type Lang } from "@/lib/copy";
import { filterTokens } from "@/lib/format";

import { CloseIcon } from "./icons";

/**
 * What MarketLens understood, as removable tokens (search-fields.md: tokens for search terms;
 * generative-ai.md: keep people in control, make results easy to refine). Removing a token
 * re-runs the search with exactly the filters that are left, no AI involved.
 */
export function FilterTokens({
  filters,
  lang,
  editable,
  onRemove,
}: {
  filters: Filters | null;
  lang: Lang;
  editable: boolean;
  onRemove: (next: Filters, label: string) => void;
}) {
  const tokens = filterTokens(filters, lang);
  if (tokens.length === 0) return null;
  return (
    <div dir={dirOf(lang)} className="flex flex-wrap items-center gap-1.5">
      <span className="me-1 text-footnote text-secondary">{COPY[lang].understoodAs}</span>
      <ul className="contents">
        {tokens.map((token) => (
          <li
            key={token.key}
            className="flex h-8 items-center rounded-full bg-accent-surface ps-3 pe-0.5 text-footnote font-semibold text-accent"
          >
            <span dir="auto">{token.label}</span>
            <button
              type="button"
              disabled={!editable}
              onClick={() => onRemove(token.without(), token.label)}
              aria-label={COPY[lang].removeToken(token.label)}
              title={COPY[lang].removeToken(token.label)}
              className="ms-0.5 flex h-7 w-7 items-center justify-center rounded-full hover:bg-accent/15 disabled:cursor-not-allowed disabled:opacity-40"
            >
              <CloseIcon size={14} />
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
