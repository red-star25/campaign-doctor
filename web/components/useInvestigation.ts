"use client";

import { useEffect, useRef, useState } from "react";
import { compareScenario, fetchReport, fetchScenarios } from "@/lib/api";
import { asApiError, type ApiError } from "@/lib/errors";
import type { CompareResponse, ProviderCondition, ReportResponse, ScenarioSummary } from "@/lib/types";

export function useInvestigation() {
  const [scenarios, setScenarios] = useState<ScenarioSummary[] | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [report, setReport] = useState<ReportResponse | null>(null);
  const [comparison, setComparison] = useState<CompareResponse | null>(null);
  const [condition, setCondition] = useState<ProviderCondition>("reply_visible");
  const [listError, setListError] = useState<ApiError | null>(null);
  const [reportError, setReportError] = useState<ApiError | null>(null);
  const [compareError, setCompareError] = useState<ApiError | null>(null);
  const [loadingList, setLoadingList] = useState(true);
  const [loadingReport, setLoadingReport] = useState(false);
  const [loadingCompare, setLoadingCompare] = useState(false);
  const [listAttempt, setListAttempt] = useState(0);

  const listGen = useRef(0);
  const reportGen = useRef(0);
  const compareGen = useRef(0);

  useEffect(() => {
    const token = ++listGen.current;
    setLoadingList(true);
    setListError(null);
    fetchScenarios()
      .then((list) => {
        if (token !== listGen.current) return;
        setScenarios(list.scenarios);
        setSelectedId((current) => {
          if (current && list.scenarios.some((item) => item.scenario_id === current)) return current;
          return list.scenarios[0]?.scenario_id ?? null;
        });
      })
      .catch((error: unknown) => {
        if (token !== listGen.current) return;
        setScenarios([]);
        setListError(asApiError(error));
      })
      .finally(() => {
        if (token === listGen.current) setLoadingList(false);
      });
  }, [listAttempt]);

  useEffect(() => {
    if (!selectedId) {
      setReport(null);
      setLoadingReport(false);
      return;
    }
    const token = ++reportGen.current;
    setLoadingReport(true);
    setReportError(null);
    fetchReport(selectedId)
      .then((next) => {
        if (token !== reportGen.current) return;
        setReport(next);
      })
      .catch((error: unknown) => {
        if (token !== reportGen.current) return;
        setReport(null);
        setReportError(asApiError(error));
      })
      .finally(() => {
        if (token === reportGen.current) setLoadingReport(false);
      });
  }, [selectedId]);

  useEffect(() => {
    if (!selectedId) {
      setComparison(null);
      setLoadingCompare(false);
      return;
    }
    const token = ++compareGen.current;
    setLoadingCompare(true);
    setCompareError(null);
    compareScenario(selectedId, condition)
      .then((next) => {
        if (token !== compareGen.current) return;
        setComparison(next);
      })
      .catch((error: unknown) => {
        if (token !== compareGen.current) return;
        setCompareError(asApiError(error));
      })
      .finally(() => {
        if (token === compareGen.current) setLoadingCompare(false);
      });
  }, [selectedId, condition]);

  const activeReport = report && report.scenario_id === selectedId ? report : null;
  const activeComparison =
    comparison && comparison.scenario_id === selectedId && comparison.provider_condition === condition
      ? comparison
      : null;

  return {
    scenarios,
    selectedId,
    setSelectedId,
    condition,
    setCondition,
    report: activeReport,
    comparison: activeComparison,
    listError,
    reportError,
    compareError,
    loadingList,
    loadingReport,
    loadingCompare,
    retryList: () => setListAttempt((attempt) => attempt + 1),
  };
}
