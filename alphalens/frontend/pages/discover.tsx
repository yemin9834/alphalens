import Head from "next/head";
import Link from "next/link";
import { useRouter } from "next/router";
import { useCallback, useEffect, useRef, useState } from "react";
import AuthenticatedLayout from "../components/AuthenticatedLayout";
import WithAuthToken, { type GetTokenFn } from "../components/WithAuthToken";
import DiscoveryTable from "../components/DiscoveryTable";
import ErrorBanner from "../components/ErrorBanner";
import WarningsList from "../components/WarningsList";
import {
  discoverEcosystemStream,
  getDiscoveryRunCandidates,
  resolveToken,
} from "../lib/api";
import { HAS_CLERK } from "../lib/config";
import {
  fromDiscoveryCandidates,
  saveCandidatePool,
} from "../lib/candidate-store";
import { mockDiscovery } from "../mock/discovery";
import type { DiscoveryCandidate, EcosystemDiscoverResponse } from "../lib/types";

const RESEARCH_POLL_MS = 800;

function DiscoverPageInner({ getToken }: { getToken: GetTokenFn }) {
  const router = useRouter();
  const [coreCompany, setCoreCompany] = useState("NVIDIA");
  const [coreTicker, setCoreTicker] = useState("NVDA");
  const [scope, setScope] = useState("level-1");
  const [loading, setLoading] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [usedMock, setUsedMock] = useState(false);
  const [result, setResult] = useState<EcosystemDiscoverResponse | null>(null);
  const [candidates, setCandidates] = useState<DiscoveryCandidate[]>([]);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [latestTicker, setLatestTicker] = useState<string | null>(null);
  const [researchingTicker, setResearchingTicker] = useState<string | null>(null);
  const [researchLog, setResearchLog] = useState("");
  const [pollingResearch, setPollingResearch] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const toggleTicker = (ticker: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(ticker)) next.delete(ticker);
      else next.add(ticker);
      return next;
    });
  };

  const selectAll = () => {
    setSelected(
      new Set(
        candidates
          .filter((c) => c.tickerValidation !== "invalid")
          .map((c) => c.ticker)
      )
    );
  };

  const streamedCandidatesRef = useRef<DiscoveryCandidate[]>([]);
  const discoveryRunIdRef = useRef<string | null>(null);

  const pollResearch = useCallback(async () => {
    const runId = discoveryRunIdRef.current;
    if (!runId) return;

    try {
      const token = await resolveToken(HAS_CLERK ? getToken : undefined);
      const data = await getDiscoveryRunCandidates(runId, token);
      setCandidates(data.candidates);
      streamedCandidatesRef.current = data.candidates;

      const ready = data.candidates.filter((c) => c.deepResearch).length;
      const total = data.candidates.filter((c) => c.tickerValidation !== "invalid").length;

      if (data.researchStatus === "completed" || data.researchStatus === "failed") {
        setPollingResearch(false);
        setResearchingTicker(null);
        setStatusMessage(null);
        setResult((prev) =>
          prev
            ? {
                ...prev,
                candidates: data.candidates,
                researchStatus: data.researchStatus,
              }
            : prev
        );
        return;
      }

      setStatusMessage(
        `Deep research in progress… ${ready} of ${Math.min(total, 5)} reports ready`
      );
    } catch (err) {
      setWarnings((prev) => [
        ...prev,
        err instanceof Error ? err.message : "Failed to poll research status",
      ]);
      setPollingResearch(false);
      setStatusMessage(null);
    }
  }, [getToken]);

  useEffect(() => {
    if (!pollingResearch || !discoveryRunIdRef.current) return;

    void pollResearch();
    const id = setInterval(() => {
      void pollResearch();
    }, RESEARCH_POLL_MS);

    return () => clearInterval(id);
  }, [pollingResearch, pollResearch]);

  const runDiscovery = async () => {
    setLoading(true);
    setStreaming(true);
    setError(null);
    setUsedMock(false);
    setStatusMessage("Starting discovery…");
    setResult(null);
    setCandidates([]);
    setWarnings([]);
    setResearchLog("");
    setResearchingTicker(null);
    setPollingResearch(false);
    discoveryRunIdRef.current = null;
    streamedCandidatesRef.current = [];

    let keepResearchPolling = false;

    try {
      const token = await resolveToken(HAS_CLERK ? getToken : undefined);

      await discoverEcosystemStream(
        {
          coreCompany,
          coreTicker: coreTicker.toUpperCase(),
          scope,
        },
        token,
        (event) => {
          if (event.event === "start") {
            setResult({
              coreCompany: event.coreCompany,
              coreTicker: event.coreTicker,
              candidates: [],
              warnings: [],
            });
            setCandidates([]);
            setWarnings([]);
            setSelected(new Set());
            setLatestTicker(null);
            setResearchingTicker(null);
            streamedCandidatesRef.current = [];
            setResearchLog("");
            return;
          }

          if (event.event === "token") {
            setResearchLog((prev) => {
              const next = prev + event.token;
              return next.length > 4000 ? next.slice(-4000) : next;
            });
            return;
          }

          if (event.event === "status") {
            setStatusMessage(event.message);
            return;
          }

          if (event.event === "warning") {
            setWarnings((prev) => [...prev, event.message]);
            return;
          }

          if (event.event === "candidate") {
            const { candidate } = event;
            if (
              !streamedCandidatesRef.current.some((c) => c.ticker === candidate.ticker)
            ) {
              streamedCandidatesRef.current.push(candidate);
              setCandidates([...streamedCandidatesRef.current]);
            }
            setLatestTicker(candidate.ticker);
            if (candidate.tickerValidation !== "invalid") {
              setSelected((prev) => new Set(prev).add(candidate.ticker));
            }
            setStatusMessage(`Loading candidates… ${event.index} of ${event.total}`);
            return;
          }

          if (event.event === "research_phase") {
            setStatusMessage(event.message);
            return;
          }

          if (event.event === "research_start") {
            setResearchingTicker(event.ticker);
            setStatusMessage(event.message);
            return;
          }

          if (event.event === "research_report") {
            const { ticker, report } = event;
            streamedCandidatesRef.current = streamedCandidatesRef.current.map((c) =>
              c.ticker === ticker ? { ...c, deepResearch: report } : c
            );
            setCandidates([...streamedCandidatesRef.current]);
            setResearchingTicker(null);
            setStatusMessage(
              `Deep research ${event.index} of ${event.total} — ${ticker}`
            );
            return;
          }

          if (event.event === "research_error") {
            setWarnings((prev) => [
              ...prev,
              `Deep research failed for ${event.ticker}: ${event.error}`,
            ]);
            setResearchingTicker(null);
            return;
          }

          if (event.event === "done") {
            const finalCandidates = [...streamedCandidatesRef.current];
            const runId = event.discoveryRunId ?? null;
            discoveryRunIdRef.current = runId;
            const asyncResearch =
              event.researchStatus === "pending" ||
              event.researchStatus === "researching";

            setResult({
              coreCompany: event.coreCompany,
              coreTicker: event.coreTicker,
              candidates: finalCandidates,
              warnings: event.warnings,
              discoveryRunId: runId,
              researchStatus: event.researchStatus ?? null,
            });
            setCandidates(finalCandidates);
            setWarnings(event.warnings);

            if (runId && asyncResearch) {
              keepResearchPolling = true;
              setPollingResearch(true);
              setStatusMessage("Deep research running in background…");
            } else {
              setStatusMessage(null);
            }

            setLatestTicker(null);
            setResearchingTicker(null);
            setResearchLog("");
          }
        }
      );
    } catch (err) {
      const message = err instanceof Error ? err.message : "Discovery failed";
      if (HAS_CLERK && (message.includes("Sign in") || message.includes("session"))) {
        setError(message);
        setResult(null);
        setCandidates([]);
        return;
      }
      const isGatewayTimeout =
        /504|gateway timeout|could not be satisfied/i.test(message);
      const isNetworkInterrupt =
        /failed to fetch|networkerror|network error|load failed|aborted|err_incomplete/i.test(
          message
        );
      const partialCandidates = [...streamedCandidatesRef.current];

      if (isGatewayTimeout || isNetworkInterrupt) {
        if (partialCandidates.length > 0) {
          setCandidates(partialCandidates);
          setResult((prev) => ({
            coreCompany: prev?.coreCompany ?? coreCompany,
            coreTicker: prev?.coreTicker ?? coreTicker.toUpperCase(),
            candidates: partialCandidates,
            warnings: [
              ...warnings,
              "Stream interrupted before deep research finished (CloudFront connection limit). Candidates above were received; research reports may be missing.",
            ],
            discoveryRunId: prev?.discoveryRunId,
          }));
          setError(
            "Discovery stream was interrupted while deep research was running (usually a ~60s CloudFront limit). Your candidates are kept below — redeploy frontend infra with the updated CloudFront timeout, then run again for full research reports."
          );
          return;
        }
        setError(
          "Discovery timed out before results arrived. Live discovery + deep research can take 1–2 minutes. After the CloudFront timeout fix is applied, try again."
        );
        setResult(null);
        setCandidates([]);
        return;
      }
      setError(`${message} — showing mock data.`);
      setResult(mockDiscovery);
      setCandidates(mockDiscovery.candidates);
      setWarnings(mockDiscovery.warnings);
      setUsedMock(true);
      setSelected(new Set(mockDiscovery.candidates.map((c) => c.ticker)));
    } finally {
      setStreaming(false);
      setLoading(false);
      setLatestTicker(null);
      if (!keepResearchPolling) {
        setStatusMessage(null);
        setResearchingTicker(null);
        setPollingResearch(false);
        setResearchLog("");
      } else {
        setResearchLog("");
      }
    }
  };

  const useForAnalysis = () => {
    const pool = fromDiscoveryCandidates(
      candidates.filter((c) => selected.has(c.ticker))
    );
    if (pool.length === 0) {
      setError("Select at least one candidate.");
      return;
    }
    saveCandidatePool(pool);
    router.push("/dashboard");
  };

  const showResults = result !== null || streaming;

  return (
    <AuthenticatedLayout>
      <Head>
        <title>Discover — AlphaLens</title>
      </Head>
      <h1 className="page-title">Stock pool discovery</h1>
      <p className="page-lead">
        Research ecosystem candidates around a core company. Results feed the
        portfolio analyzer.
      </p>

      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}
      {usedMock && (
        <div className="banner banner-warn">
          Using mock data — start the API for live or curated backend discovery.
        </div>
      )}

      <section className="card">
        <div className="form-grid">
          <label>
            Core company
            <input
              value={coreCompany}
              onChange={(e) => setCoreCompany(e.target.value)}
              disabled={loading}
            />
          </label>
          <label>
            Ticker
            <input
              value={coreTicker}
              onChange={(e) => setCoreTicker(e.target.value.toUpperCase())}
              disabled={loading}
            />
          </label>
          <label>
            Scope
            <select
              value={scope}
              onChange={(e) => setScope(e.target.value)}
              disabled={loading}
            >
              <option value="level-1">Level 1 (direct ecosystem)</option>
            </select>
          </label>
        </div>
        <div className="btn-row">
          <button
            type="button"
            className="btn btn-primary"
            disabled={loading}
            onClick={runDiscovery}
          >
            {loading ? "Discovering…" : "Run discovery"}
          </button>
        </div>
      </section>

      {showResults && (
        <section className="card discovery-results-card">
          <div className="discovery-results-header">
            <h2>
              {result?.coreCompany ?? coreCompany} ({result?.coreTicker ?? coreTicker})
              {candidates.length > 0 && (
                <>
                  {" "}
                  — {candidates.length}
                  {streaming ? "+" : ""} candidates
                </>
              )}
            </h2>
            {streaming && statusMessage && (
              <p className="discovery-stream-status" aria-live="polite">
                <span className="discovery-stream-pulse" aria-hidden />
                {statusMessage}
              </p>
            )}
            {pollingResearch && !streaming && statusMessage && (
              <p className="discovery-stream-status" aria-live="polite">
                <span className="discovery-stream-pulse" aria-hidden />
                {statusMessage}
              </p>
            )}
          </div>

          {result?.discoveryRunId && !streaming && (
            <p className="muted">
              Saved to database — run{" "}
              <code>{result.discoveryRunId.slice(0, 8)}…</code>
            </p>
          )}

          <WarningsList warnings={warnings} />

          {streaming && researchLog.trim() && (
            <pre className="discovery-research-log" aria-live="polite">
              {researchLog}
            </pre>
          )}

          {candidates.length > 0 ? (
            <DiscoveryTable
              candidates={candidates}
              selected={selected}
              onToggle={toggleTicker}
              highlightTicker={latestTicker}
              researchingTicker={researchingTicker}
            />
          ) : streaming ? (
            <p className="muted discovery-stream-empty">
              Candidates will appear here as they are found…
            </p>
          ) : (
            <p className="muted">No candidates returned.</p>
          )}

          <div className="btn-row">
            <button
              type="button"
              className="btn"
              onClick={selectAll}
              disabled={streaming || pollingResearch || candidates.length === 0}
            >
              Select all valid
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={useForAnalysis}
              disabled={streaming || pollingResearch || selected.size === 0}
            >
              Analyze portfolio with selected ({selected.size})
            </button>
            <Link href="/dashboard" className="btn">
              Skip to analyze
            </Link>
          </div>
        </section>
      )}
    </AuthenticatedLayout>
  );
}

export default function DiscoverPage() {
  return (
    <WithAuthToken>
      {(getToken) => <DiscoverPageInner getToken={getToken} />}
    </WithAuthToken>
  );
}
