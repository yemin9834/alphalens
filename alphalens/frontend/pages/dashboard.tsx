import Head from "next/head";
import Link from "next/link";
import { useRouter } from "next/router";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import AnalysisReport from "../components/AnalysisReport";
import CandidatePoolPanel from "../components/CandidatePoolPanel";
import PortfolioPanel from "../components/PortfolioPanel";
import RankedOpportunitiesTable from "../components/RankedOpportunitiesTable";
import ValidationReport from "../components/ValidationReport";
import AuthenticatedLayout from "../components/AuthenticatedLayout";
import ErrorBanner from "../components/ErrorBanner";
import JobPipelineProgress from "../components/JobPipelineProgress";
import WarningsList from "../components/WarningsList";
import WithAuthToken, { type GetTokenFn } from "../components/WithAuthToken";
import {
  enqueueAnalysisJob,
  getPortfolio,
  populateTestData,
  rankOpportunitiesStream,
  resolveToken,
  savePortfolio,
} from "../lib/api";
import { HAS_CLERK } from "../lib/config";
import { loadCandidatePool, saveCandidatePool } from "../lib/candidate-store";
import type {
  AnalysisJob,
  AnalysisReport as AnalysisReportType,
  ValidationReport as ValidationReportType,
  PortfolioHolding,
  SavedPortfolioResponse,
  RankCandidateInput,
  RankedCandidate,
} from "../lib/types";
import type { RankStreamEvent } from "../lib/rank-stream";
import { useSectionScroll, mergeRefs } from "../lib/use-section-scroll";

const DEFAULT_HOLDINGS: PortfolioHolding[] = [
  { ticker: "NVDA", weight: 40 },
  { ticker: "CASH", weight: 60 },
];

function DashboardPageInner({ getToken }: { getToken: GetTokenFn }) {
  const router = useRouter();
  const [riskProfile, setRiskProfile] = useState("balanced");
  const [holdings, setHoldings] = useState<PortfolioHolding[]>(DEFAULT_HOLDINGS);
  const [candidatePool, setCandidatePool] = useState<RankCandidateInput[]>([]);
  const [manualTicker, setManualTicker] = useState("");
  const [manualRel, setManualRel] = useState("supplier");
  const [loading, setLoading] = useState(false);
  const [populating, setPopulating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ranked, setRanked] = useState<RankedCandidate[] | null>(null);
  const [validationReport, setValidationReport] = useState<ValidationReportType | null>(null);
  const [rankReport, setRankReport] = useState<AnalysisReportType | null>(null);
  const [rankWarnings, setRankWarnings] = useState<string[]>([]);
  const [rankStreamActive, setRankStreamActive] = useState(false);
  const [rankStatusMessage, setRankStatusMessage] = useState<string | null>(null);
  const [latestRankedTicker, setLatestRankedTicker] = useState<string | null>(null);
  const [pipelineStage, setPipelineStage] = useState<string | undefined>();
  const [analysisRun, setAnalysisRun] = useState(0);
  const [portfolioHydrated, setPortfolioHydrated] = useState(false);
  const streamedRankedRef = useRef<RankedCandidate[]>([]);

  const scrollKey = analysisRun;
  const validationScrollRef = useSectionScroll(
    scrollKey,
    Boolean(validationReport),
    "validation"
  );
  const rankedVisible = Boolean(ranked && ranked.length > 0);
  const rankedScrollRef = useSectionScroll(scrollKey, rankedVisible, "ranked");
  const rankedCompleteScrollRef = useSectionScroll(
    scrollKey,
    rankedVisible && !rankStreamActive,
    "ranked-complete"
  );
  const rankReportScrollRef = useSectionScroll(
    scrollKey,
    Boolean(rankReport),
    "rank-report"
  );

  const syncProgressJob = useMemo((): AnalysisJob | null => {
    if (!rankStreamActive && !pipelineStage) return null;
    return {
      id: "sync",
      status: rankStreamActive ? "running" : "completed",
      request_payload: { candidates: candidatePool },
      ranked_payload: {
        pipelineStage,
        discoverySkipped: candidatePool.length > 0,
        validationReport: validationReport ?? undefined,
        analysisReport: rankReport ?? undefined,
        rankedCandidates: ranked ?? undefined,
      },
    };
  }, [
    rankStreamActive,
    pipelineStage,
    candidatePool,
    validationReport,
    rankReport,
    ranked,
  ]);

  const applySavedPortfolio = (data: SavedPortfolioResponse) => {
    if (data.holdings.length > 0) {
      setHoldings(data.holdings);
    }
    if (data.candidatePool.length > 0) {
      setCandidatePool(data.candidatePool);
      saveCandidatePool(data.candidatePool);
    }
  };

  useEffect(() => {
    const stored = loadCandidatePool();
    if (stored.length > 0) setCandidatePool(stored);

    let cancelled = false;
    setPortfolioHydrated(false);
    (async () => {
      try {
        const token = await resolveToken(HAS_CLERK ? getToken : undefined);
        const data = await getPortfolio(token);
        if (!cancelled) applySavedPortfolio(data);
      } catch {
        // No saved portfolio yet — keep UI defaults
      } finally {
        if (!cancelled) setPortfolioHydrated(true);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [getToken]);

  const saveHoldingsToServer = useCallback(
    async (rows: PortfolioHolding[]) => {
      const token = await resolveToken(HAS_CLERK ? getToken : undefined);
      await savePortfolio(
        rows.filter((h) => h.ticker.trim()),
        token
      );
    },
    [getToken]
  );

  useEffect(() => {
    if (!portfolioHydrated) return;

    const timer = window.setTimeout(() => {
      void saveHoldingsToServer(holdings).catch((err) => {
        setError(err instanceof Error ? err.message : "Failed to save portfolio");
      });
    }, 600);

    return () => window.clearTimeout(timer);
  }, [holdings, portfolioHydrated, saveHoldingsToServer]);

  const runPopulateTestData = async () => {
    setPopulating(true);
    setError(null);
    try {
      const token = await resolveToken(HAS_CLERK ? getToken : undefined);
      const data = await populateTestData(token);
      applySavedPortfolio(data.portfolio);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to populate test data");
    } finally {
      setPopulating(false);
    }
  };

  const weightTotal = useMemo(
    () => holdings.reduce((sum, h) => sum + Number(h.weight || 0), 0),
    [holdings]
  );

  const updateHolding = (index: number, field: keyof PortfolioHolding, value: string) => {
    setHoldings((rows) =>
      rows.map((row, i) =>
        i === index
          ? {
              ...row,
              [field]: field === "weight" ? Number(value) : value.toUpperCase(),
            }
          : row
      )
    );
  };

  const addHolding = () => {
    setHoldings((rows) => [...rows, { ticker: "", weight: 0 }]);
  };

  const removeHolding = (index: number) => {
    setHoldings((rows) => rows.filter((_, i) => i !== index));
  };

  const addCandidate = () => {
    const ticker = manualTicker.trim().toUpperCase();
    if (!ticker) return;
    setCandidatePool((pool) => {
      if (pool.some((c) => c.ticker === ticker)) return pool;
      const next = [...pool, { ticker, relationshipType: manualRel }];
      saveCandidatePool(next);
      return next;
    });
    setManualTicker("");
  };

  const removeCandidate = (ticker: string) => {
    setCandidatePool((pool) => {
      const next = pool.filter((c) => c.ticker !== ticker);
      saveCandidatePool(next);
      return next;
    });
  };

  const clearCandidatePool = () => {
    setCandidatePool([]);
    saveCandidatePool([]);
  };

  const buildPayload = () => ({
    riskProfile,
    investmentHorizon: "medium-term",
    portfolio: holdings.filter((h) => h.ticker.trim()),
    candidatePool,
    strategyProfile: "default-risk-based",
  });

  const runRank = async () => {
    if (candidatePool.length === 0) {
      setError("Add at least one candidate to the pool.");
      return;
    }
    setLoading(true);
    setRankStreamActive(true);
    setAnalysisRun((n) => n + 1);
    setError(null);
    setRanked([]);
    setValidationReport(null);
    setRankReport(null);
    setRankWarnings([]);
    setRankStatusMessage("Starting rank analysis…");
    setLatestRankedTicker(null);
    setPipelineStage("validation");
    streamedRankedRef.current = [];

    try {
      const token = await resolveToken(HAS_CLERK ? getToken : undefined);
      await rankOpportunitiesStream(
        {
          riskProfile,
          marketCondition: "Neutral",
          candidates: candidatePool,
        },
        token,
        (event: RankStreamEvent) => {
          if (event.warnings?.length) {
            setRankWarnings(event.warnings);
          }

          if (event.stage === "status" && event.message) {
            setRankStatusMessage(event.message);
            return;
          }

          if (event.stage === "validation") {
            if (event.validationReport) {
              setValidationReport(event.validationReport);
            }
            setPipelineStage("analysis");
            return;
          }

          if (event.stage === "ranked" && event.rankedCandidate) {
            const row = event.rankedCandidate;
            if (!streamedRankedRef.current.some((r) => r.ticker === row.ticker)) {
              streamedRankedRef.current.push(row);
              setRanked([...streamedRankedRef.current]);
            }
            setLatestRankedTicker(row.ticker);
            if (event.index != null && event.total != null) {
              setRankStatusMessage(`Loading rankings… ${event.index} of ${event.total}`);
            }
            return;
          }

          if (event.stage === "analysis" && event.analysisReport) {
            setRankReport(event.analysisReport);
            return;
          }

          if (event.stage === "complete") {
            const finalRanked = event.rankedCandidates ?? streamedRankedRef.current;
            streamedRankedRef.current = [...finalRanked];
            setRanked(finalRanked);
            if (event.validationReport) {
              setValidationReport(event.validationReport);
            }
            if (event.analysisReport) {
              setRankReport(event.analysisReport);
            }
            if (event.warnings?.length) {
              setRankWarnings(event.warnings);
            }
            setPipelineStage("completed");
            setRankStatusMessage(null);
            setLatestRankedTicker(null);
          }
        }
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ranking failed");
      setPipelineStage(undefined);
    } finally {
      setRankStreamActive(false);
      setLoading(false);
      setRankStatusMessage(null);
      setLatestRankedTicker(null);
    }
  };

  const persistHoldings = async (token: string | null) => {
    await savePortfolio(
      holdings.filter((h) => h.ticker.trim()),
      token
    );
  };

  const runAnalyze = async () => {
    if (candidatePool.length === 0) {
      setError("Add at least one candidate — run Discover first or add manually.");
      return;
    }
    if (Math.abs(weightTotal - 100) > 0.5) {
      setError(`Portfolio weights should sum to 100% (currently ${weightTotal.toFixed(1)}%).`);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const token = await resolveToken(HAS_CLERK ? getToken : undefined);
      await persistHoldings(token);
      const { jobId } = await enqueueAnalysisJob(buildPayload(), token);
      router.push(`/job?id=${jobId}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start analysis");
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthenticatedLayout>
      <Head>
        <title>Portfolio analysis — AlphaLens</title>
      </Head>
      <h1 className="page-title">Portfolio analysis</h1>
      <p className="page-lead">
        Rank ecosystem candidates and get portfolio-aware recommendations.{" "}
        <Link href="/discover">Discover candidates</Link> first for best results.
      </p>

      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

      <CandidatePoolPanel
        candidates={candidatePool}
        manualTicker={manualTicker}
        manualRel={manualRel}
        onManualTickerChange={setManualTicker}
        onManualRelChange={setManualRel}
        onAdd={addCandidate}
        onRemove={removeCandidate}
        onClearAll={clearCandidatePool}
      />

      <PortfolioPanel
        holdings={holdings}
        riskProfile={riskProfile}
        weightTotal={weightTotal}
        populating={populating}
        loading={loading}
        onRiskProfileChange={setRiskProfile}
        onUpdateHolding={updateHolding}
        onAddHolding={addHolding}
        onRemoveHolding={removeHolding}
        onPopulateTestData={runPopulateTestData}
        getToken={getToken}
      />

      <section className="card">
        <h2>Run analysis</h2>
        <div className="btn-row">
          <button
            type="button"
            className="btn"
            disabled={loading}
            onClick={runRank}
          >
            {loading && rankStreamActive ? "Ranking…" : "Rank only"}
          </button>
          <button
            type="button"
            className="btn btn-primary"
            disabled={loading}
            onClick={runAnalyze}
          >
            {loading && !rankStreamActive ? "Starting analysis…" : "Analyze portfolio"}
          </button>
        </div>
      </section>

      {syncProgressJob && <JobPipelineProgress job={syncProgressJob} />}

      {rankStatusMessage && (
        <p className="discovery-stream-status" aria-live="polite">
          <span className="discovery-stream-pulse" aria-hidden />
          {rankStatusMessage}
        </p>
      )}

      {rankWarnings.length > 0 && <WarningsList warnings={rankWarnings} />}

      {validationReport && (
        <div
          ref={validationScrollRef}
          className="job-result-section job-result-fade-in"
        >
          <ValidationReport report={validationReport} />
        </div>
      )}

      {ranked && ranked.length > 0 && (
        <div
          ref={mergeRefs(rankedScrollRef, rankedCompleteScrollRef)}
          className="job-result-section job-result-fade-in"
        >
          <RankedOpportunitiesTable
            ranked={ranked}
            streaming={rankStreamActive}
            highlightTicker={latestRankedTicker}
            subtitle="Scores from deterministic metrics — rows appear as ranking completes."
          />
        </div>
      )}

      {rankReport && (
        <div
          ref={rankReportScrollRef}
          className="job-result-section job-result-fade-in"
        >
          <AnalysisReport report={rankReport} />
        </div>
      )}
    </AuthenticatedLayout>
  );
}

export default function DashboardPage() {
  return (
    <WithAuthToken>
      {(getToken) => <DashboardPageInner getToken={getToken} />}
    </WithAuthToken>
  );
}
