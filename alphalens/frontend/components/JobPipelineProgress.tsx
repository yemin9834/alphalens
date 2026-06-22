import { getPipelineSteps, type PipelineStep } from "../lib/job-progress";
import type { AnalysisJob } from "../lib/types";

interface JobPipelineProgressProps {
  job: AnalysisJob | null;
}

function stepIcon(step: PipelineStep): string {
  switch (step.state) {
    case "done":
      return "✓";
    case "running":
      return "…";
    case "failed":
      return "✕";
    case "skipped":
      return "—";
    default:
      return "○";
  }
}

export default function JobPipelineProgress({ job }: JobPipelineProgressProps) {
  const steps = getPipelineSteps(job);
  const active = job?.status === "running" || job?.status === "pending";

  return (
    <section className="card job-pipeline-card">
      <div className="report-header">
        <div className="report-title-block">
          <span className="report-icon" aria-hidden>
            ↻
          </span>
          <div>
            <h2>Pipeline progress</h2>
            <p className="muted report-subtitle">
              {active
                ? "Results appear below as each step finishes."
                : "All pipeline steps finished."}
            </p>
          </div>
        </div>
        {job && (
          <span className={`status-pill status-${job.status}`}>{job.status}</span>
        )}
      </div>

      <ol className="job-pipeline-steps">
        {steps.map((step, index) => (
          <li
            key={step.id}
            className={`job-pipeline-step job-pipeline-step-${step.state}`}
          >
            <span className="job-pipeline-marker" aria-hidden>
              {stepIcon(step)}
            </span>
            <div className="job-pipeline-step-body">
              <span className="job-pipeline-step-label">{step.label}</span>
              {step.state === "running" && (
                <span className="job-pipeline-step-hint">In progress…</span>
              )}
              {step.state === "skipped" && (
                <span className="job-pipeline-step-hint muted">Skipped — candidates provided</span>
              )}
              {step.state === "done" && step.id !== "complete" && (
                <span className="job-pipeline-step-hint job-pipeline-step-done">Done</span>
              )}
            </div>
            {index < steps.length - 1 && (
              <span className="job-pipeline-connector" aria-hidden />
            )}
          </li>
        ))}
      </ol>

      {active && (
        <p className="muted job-pipeline-live-hint">
          <span className="job-pipeline-pulse" aria-hidden />
          Live updates — refreshing about every second
        </p>
      )}
    </section>
  );
}
