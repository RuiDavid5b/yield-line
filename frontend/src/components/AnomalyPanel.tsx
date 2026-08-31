import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { Digest } from "../api/types";

import ReactMarkdown from "react-markdown";

interface AnomalyPanelProps {
  cik: string;
  start: string;
  end: string;
  latestDigest: Digest | null;
}

export default function AnomalyPanel({ cik, start, end, latestDigest }: AnomalyPanelProps) {
  const [anomalies, setAnomalies] = useState<Awaited<ReturnType<typeof api.anomalies>>>([]);
  const [index, setIndex] = useState(-1);

  useEffect(() => {
    api.anomalies(cik, start, end).then(setAnomalies);
    setIndex(-1);
  }, [cik, start, end]);

  const today = new Date().toISOString().slice(0, 10);
  const todaysAnomaly = anomalies.find((a) => a.date === today);
  const current = index === -1 ? todaysAnomaly : anomalies[index];
  const isShowingToday = index === -1;

  const canGoOlder = index < anomalies.length - 1;
  const canGoNewer = index > -1;

  const digestCompany = latestDigest?.companies.find((c) => c.cik === cik);
  const isCrossSectionalToday = isShowingToday && digestCompany?.is_cross_sectional_anomaly;

  const signalLabels: string[] = [];
  if (current) signalLabels.push("Unusual for this company's own history");
  if (isCrossSectionalToday) signalLabels.push("Unusual vs. all tracked companies today");

  return (
    <div>
      <div className="section-heading">Anomaly Explanation</div>
      <div className="panel">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <button disabled={!canGoOlder} onClick={() => setIndex((i) => (i === -1 ? 0 : i + 1))}>← older</button>
          <strong>{isShowingToday ? "Today" : current?.date}</strong>
          <button disabled={!canGoNewer} onClick={() => setIndex((i) => Math.max(i - 1, -1))}>newer →</button>
        </div>
        {current ? (
          <div style={{ marginTop: 10 }}>
            <div className="signal-tags">
              {signalLabels.map((label) => (
                <span key={label} className="signal-tag">{label}</span>
              ))}
            </div>
            <div style={{ marginTop: 6 }}>
              Return: {(current.return_pct * 100).toFixed(2)}% (z={current.z_score.toFixed(2)})
            </div>
            {current.explanation ? (
              <div className="explanation-text">
                <ReactMarkdown>{current.explanation}</ReactMarkdown>
              </div>
            ) : (
              <p>Explanation pending.</p>
            )}
          </div>
        ) : (
          <p style={{ color: "var(--text-dim)", marginTop: 8 }}>
            {isShowingToday ? "No anomalies today." : "No anomaly at this point."}
          </p>
        )}
      </div>
    </div>
  );
}
