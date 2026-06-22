import type { EcosystemDiscoverResponse } from "../lib/types";

/** Mock NVIDIA ecosystem discovery — design-doc.md §14 */
export const mockDiscovery: EcosystemDiscoverResponse = {
  coreCompany: "NVIDIA",
  coreTicker: "NVDA",
  candidates: [
    {
      companyName: "Taiwan Semiconductor Manufacturing Company",
      ticker: "TSM",
      relationshipType: "supplier",
      relationshipSummary: "TSMC provides semiconductor manufacturing services for NVIDIA chips.",
      confidence: "High",
      evidenceUrl: "Data unavailable for mock demo",
      tickerValidation: "validated",
    },
    {
      companyName: "Microsoft",
      ticker: "MSFT",
      relationshipType: "partner",
      relationshipSummary: "Microsoft Azure offers NVIDIA GPU instances for AI workloads.",
      confidence: "High",
      evidenceUrl: "Data unavailable for mock demo",
      tickerValidation: "validated",
    },
  ],
  warnings: [],
  discoveryRunId: "mock-run-00000000-0000-4000-8000-000000000001",
};
