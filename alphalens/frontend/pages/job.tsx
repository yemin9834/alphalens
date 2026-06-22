import Head from "next/head";
import Link from "next/link";
import { useRouter } from "next/router";
import { useCallback, useEffect, useState } from "react";
import AnalysisReport from "../components/AnalysisReport";
import AnalysisResults from "../components/AnalysisResults";
import AuthenticatedLayout from "../components/AuthenticatedLayout";
import ErrorBanner from "../components/ErrorBanner";
import JobPipelineProgress from "../components/JobPipelineProgress";
import JobQAChat from "../components/JobQAChat";
import PortfolioReport from "../components/PortfolioReport";
import RankedOpportunitiesTable from "../components/RankedOpportunitiesTable";
import ValidationReport from "../components/ValidationReport";
import WarningsList from "../components/WarningsList";
import {
  extractAnalysisReport,
  extractPortfolioReport,
  extractValidationReport,
} from "../lib/analysis-report";
import WithAuthToken, { type GetTokenFn } from "../components/WithAuthToken";
import { getAnalysisJob, resolveToken } from "../lib/api";
import { HAS_CLERK } from "../lib/config";
import { extractRankedCandidates, isJobActive } from "../lib/job-progress";
import { mergeRefs, useSectionScroll } from "../lib/use-section-scroll";
import type { AnalysisJob, PortfolioAnalyzeResponse } from "../lib/types";

const POLL_MS_ACTIVE = 600;

function JobPageInner({ getToken }: { getToken: GetTokenFn }) {
  const router = useRouter();
  const jobId = typeof router.query.id === "string" ? router.query.id : "";
  const [job, setJob] = useState<AnalysisJob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const loadJob = useCallback(async () => {
    if (!jobId) return null;
    try {
      const token = await resolveToken(HAS_CLERK ? getToken : undefined);
      const data = await getAnalysisJob(jobId, token);
      setJob(data);
      setError(null);
      return data;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load job");
      return null;
    }
  }, [jobId, getToken]);

  useEffect(() => {
    if (!jobId) return;

    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const poll = async () => {
      if (cancelled) return;
      const data = await loadJob();
      if (cancelled || !data) return;

      if (data.status === "pending" || data.status === "running") {
        timer = setTimeout(poll, POLL_MS_ACTIVE);
      }
    };

    poll();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [jobId, loadJob]);

  const recommendation = job?.recommendation_payload as
    | PortfolioAnalyzeResponse
    | undefined;
  const rankReport = extractAnalysisReport(job?.ranked_payload);
  const validationReport = extractValidationReport(job?.ranked_payload);
  const portfolioReport = extractPortfolioReport(recommendation);
  const ranked = extractRankedCandidates(job);
  const jobWarnings = Array.isArray(
    (job?.ranked_payload as { warnings?: unknown } | undefined)?.warnings
  )
    ? ((job?.ranked_payload as { warnings: string[] }).warnings ?? [])
    : [];

  const scrollEnabled = isJobActive(job);
  const scrollKey = scrollEnabled ? jobId : `${jobId}-done`;

  const validationScrollRef = useSectionScroll(
    scrollKey,
    scrollEnabled && Boolean(validationReport),
    "validation"
  );
  const rankReportScrollRef = useSectionScroll(
    scrollKey,
    scrollEnabled && Boolean(rankReport),
    "rank-report"
  );
  const rankedScrollRef = useSectionScroll(
    scrollKey,
    scrollEnabled && ranked.length > 0,
    "ranked"
  );
  const portfolioReportScrollRef = useSectionScroll(
    scrollKey,
    scrollEnabled && Boolean(portfolioReport),
    "portfolio-report"
  );
  const analysisScrollRef = useSectionScroll(
    scrollKey,
    scrollEnabled && Boolean(recommendation),
    "analysis-results"
  );

  if (!jobId) {
    return (
      <AuthenticatedLayout>
        <p className="muted">
          Missing job id. <Link href="/dashboard">Return to analyze</Link>
        </p>
      </AuthenticatedLayout>
    );
  }

  return (
    <AuthenticatedLayout>
      <Head>
        <title>Job {jobId.slice(0, 8)}… — AlphaLens</title>
      </Head>
      <h1 className="page-title">Analysis job</h1>
      <p className="page-lead">
        Job <code>{jobId}</code>
        {isJobActive(job) && (
          <>
            {" "}
            — results stream in as each agent completes.
          </>
        )}
      </p>

      {error && <ErrorBanner message={error} onDismiss={() => setError(null)} />}

      <JobPipelineProgress job={job} />

      {job?.error_message && (
        <div className="banner banner-error">{job.error_message}</div>
      )}

      {job?.discovery_run_id && (
        <p className="muted job-discovery-link">
          Linked discovery run <code>{job.discovery_run_id.slice(0, 8)}…</code>
        </p>
      )}

      {jobWarnings.length > 0 && <WarningsList warnings={jobWarnings} />}

      {validationReport && (
        <div
          ref={validationScrollRef}
          className="job-result-section job-result-fade-in"
        >
          <ValidationReport report={validationReport} />
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

      {ranked.length > 0 && (
        <div
          ref={rankedScrollRef}
          className="job-result-section job-result-fade-in"
        >
          <RankedOpportunitiesTable ranked={ranked} />
        </div>
      )}

      {portfolioReport && (
        <div
          ref={portfolioReportScrollRef}
          className="job-result-section job-result-fade-in"
        >
          <PortfolioReport report={portfolioReport} />
        </div>
      )}

      {recommendation && (
        <div
          ref={analysisScrollRef}
          className="job-result-section job-result-fade-in"
        >
          <AnalysisResults result={recommendation} />
        </div>
      )}

      {job?.status === "completed" && (
        <JobQAChat jobId={jobId} getToken={getToken} />
      )}

      <Link href="/dashboard" className="btn">
        Back to analyze
      </Link>
    </AuthenticatedLayout>
  );
}

export default function JobPage() {
  return (
    <WithAuthToken>
      {(getToken) => <JobPageInner getToken={getToken} />}
    </WithAuthToken>
  );
}
