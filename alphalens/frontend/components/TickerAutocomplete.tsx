import { useCallback, useEffect, useId, useRef, useState } from "react";
import { searchInstruments, type GetToken } from "../lib/api";
import { HAS_CLERK } from "../lib/config";
import type { InstrumentSearchResult } from "../lib/types";

interface TickerAutocompleteProps {
  value: string;
  onChange: (value: string) => void;
  onSelectResult?: (result: InstrumentSearchResult) => void;
  getToken?: GetToken;
  placeholder?: string;
  disabled?: boolean;
}

export default function TickerAutocomplete({
  value,
  onChange,
  onSelectResult,
  getToken,
  placeholder = "NVDA or NVIDIA",
  disabled = false,
}: TickerAutocompleteProps) {
  const listId = useId();
  const rootRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const userEngagedRef = useRef(false);
  const suppressOpenRef = useRef(false);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<InstrumentSearchResult[]>([]);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [searchError, setSearchError] = useState<string | null>(null);

  const runSearch = useCallback(
    async (query: string, allowOpen: boolean) => {
      const trimmed = query.trim();
      if (trimmed.length < 1) {
        setResults([]);
        setOpen(false);
        setSearchError(null);
        return;
      }

      setLoading(true);
      setSearchError(null);
      try {
        const token = HAS_CLERK && getToken ? await getToken() : null;
        const response = await searchInstruments(trimmed, token, 8);
        setResults(response.results);

        const shouldOpen =
          allowOpen &&
          !suppressOpenRef.current &&
          inputRef.current === document.activeElement &&
          response.results.length > 0;
        suppressOpenRef.current = false;
        setOpen(shouldOpen);
        setActiveIndex(shouldOpen ? 0 : -1);
      } catch (err) {
        setResults([]);
        setOpen(false);
        setSearchError(err instanceof Error ? err.message : "Search failed");
      } finally {
        setLoading(false);
      }
    },
    [getToken]
  );

  useEffect(() => {
    if (disabled || !userEngagedRef.current) return;

    const handle = window.setTimeout(() => {
      void runSearch(value, true);
    }, 280);
    return () => window.clearTimeout(handle);
  }, [value, disabled, runSearch]);

  useEffect(() => {
    const onPointerDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, []);

  const selectResult = (result: InstrumentSearchResult) => {
    suppressOpenRef.current = true;
    userEngagedRef.current = false;
    onChange(result.ticker);
    onSelectResult?.(result);
    setOpen(false);
    setResults([]);
    setActiveIndex(-1);
  };

  const onKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (!open || results.length === 0) return;

    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((prev) => (prev + 1) % results.length);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((prev) => (prev <= 0 ? results.length - 1 : prev - 1));
    } else if (event.key === "Enter" && activeIndex >= 0) {
      event.preventDefault();
      selectResult(results[activeIndex]);
    } else if (event.key === "Escape") {
      setOpen(false);
    }
  };

  return (
    <div className="ticker-autocomplete" ref={rootRef}>
      <input
        ref={inputRef}
        value={value}
        onChange={(e) => {
          userEngagedRef.current = true;
          onChange(e.target.value);
        }}
        onFocus={() => {
          userEngagedRef.current = true;
          if (value.trim()) {
            void runSearch(value, true);
          }
        }}
        onKeyDown={onKeyDown}
        placeholder={placeholder}
        disabled={disabled}
        autoComplete="off"
        aria-autocomplete="list"
        aria-expanded={open}
        aria-controls={open ? listId : undefined}
        role="combobox"
      />
      {loading && <span className="ticker-autocomplete-status">Searching…</span>}
      {searchError && !loading && (
        <span className="ticker-autocomplete-error">{searchError}</span>
      )}
      {open && results.length > 0 && (
        <ul className="ticker-autocomplete-list" id={listId} role="listbox">
          {results.map((result, index) => (
            <li key={result.ticker} role="presentation">
              <button
                type="button"
                role="option"
                aria-selected={index === activeIndex}
                className={`ticker-autocomplete-option${
                  index === activeIndex ? " is-active" : ""
                }`}
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => selectResult(result)}
              >
                <span className="ticker-autocomplete-symbol">{result.ticker}</span>
                <span className="ticker-autocomplete-name">
                  {result.companyName || "Listed symbol"}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
