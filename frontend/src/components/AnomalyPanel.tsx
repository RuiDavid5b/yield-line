import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { Anomaly } from "../api/types";

interface AnomalyPanelProps {
  cik: string;
  start: string;
  end: string;
}

export default function AnomalyPanel({
  cik,
  start,
  end,
}: AnomalyPanelProps) {
  const [anomalies, setAnomalies] =
    useState<Anomaly[]>([]);
  const [index, setIndex] = useState(-1);

  useEffect(() => {
    api.anomalies(cik, start, end).then(setAnomalies);
    setIndex(-1);
  }, [cik, start, end]);

  const today = new Date().toISOString().slice(0, 10);
  const todaysAnomaly = anomalies.find(
    (anomaly) => anomaly.date === today,
  );

  const current =
    index === -1 ? todaysAnomaly : anomalies[index];

  const isShowingToday = index === -1;

  const canGoOlder = index < anomalies.length - 1;
  const canGoNewer = index > -1;

  return (
    <div className="panel">
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <button
          disabled={!canGoNewer}
          onClick={() =>
            setIndex((i) => Math.max(i - 1, -1))
          }
        >
          ← newer
        </button>

        <strong>
          {isShowingToday ? "Today" : current?.date}
        </strong>

        <button
          disabled={!canGoOlder}
          onClick={() =>
            setIndex((i) => (i === -1 ? 0 : i + 1))
          }
        >
          older →
        </button>
      </div>

      {current ? (
        <div style={{ marginTop: 8 }}>
          <div>
            Return: {(current.return_pct * 100).toFixed(2)}%
            {" "}
            (z={current.z_score.toFixed(2)})
          </div>

          <p>
            {current.explanation || "Explanation pending."}
          </p>
        </div>
      ) : (
        <p
          style={{
            color: "var(--text-dim)",
            marginTop: 8,
          }}
        >
          {isShowingToday
            ? "No anomalies today."
            : "No anomaly at this point."}
        </p>
      )}
    </div>
  );
}
