import { useEffect, useState, useMemo } from "react";
import { type Company, type Anomaly, type Digest } from "../api/types";
import { api } from "../api/client";

interface CompanyListProps {
  companies: Company[];
  returns: Record<string, number | null>;
  latestAnomalies: Anomaly[];
  latestDigest: Digest | null;
  selectedCik: string | undefined;
  onSelect: (company: Company) => void;
}

export default function CompanyList({
  companies,
  returns,
  latestAnomalies,
  latestDigest,
  selectedCik,
  onSelect,
}: CompanyListProps) {
  const [query, setQuery] = useState("");
  const [filteredCiks, setFilteredCiks] = useState<Set<string> | null>(null);

  useEffect(() => {
    if (!query.trim()) {
      setFilteredCiks(null);
      return;
    }

    const handle = setTimeout(async () => {
      const matches = await api.resolveCompany(query);
      setFilteredCiks(new Set(matches.map((match) => match.cik)));
    }, 200);

    return () => clearTimeout(handle);
  }, [query]);

  const anomalyByCik = useMemo(() => {
    const map = new Map<string, string[]>();

    for (const anomaly of latestAnomalies) {
      map.set(anomaly.cik, [
        ...(map.get(anomaly.cik) ?? []),
        `Rolling anomaly (z=${anomaly.z_score.toFixed(2)})`,
      ]);
    }

    for (const company of latestDigest?.companies ?? []) {
      if (company.is_cross_sectional_anomaly) {
        map.set(company.cik, [
          ...(map.get(company.cik) ?? []),
          "Unusual vs. all tracked companies today",
        ]);
      }
    }

    return map;
  }, [latestAnomalies, latestDigest]);

  const visible = filteredCiks
    ? companies.filter((company) => filteredCiks.has(company.cik))
    : companies;

  return (
    <div className="company-list">
      <input
        className="search-input"
        placeholder="Search companies..."
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />

      {visible.map((company) => {
        const returnPct = returns[company.cik];
        const anomalyReasons = anomalyByCik.get(company.cik);

        return (
          <div
            key={company.cik}
            className={`company-row${
              company.cik === selectedCik ? " selected" : ""
            }`}
            onClick={() => onSelect(company)}
          >
            <img
              className="company-logo"
              src={`https://img.logo.dev/ticker/${company.ticker}?token=${
                import.meta.env.VITE_LOGODEV_TOKEN
              }`}
              onError={(e) => {
                e.currentTarget.style.display = "none";
              }}
              alt=""
            />

            <div style={{ flex: 1 }}>
              <div>{company.name}</div>
              <div
                style={{
                  fontSize: 12,
                  color: "var(--text-dim)",
                }}
              >
                {company.industry_segment}
              </div>
            </div>

            {returnPct != null && (
              <span
                className={`return-pct ${
                  returnPct >= 0 ? "positive" : "negative"
                }`}
              >
                {(returnPct * 100).toFixed(1)}%
              </span>
            )}

            {anomalyReasons && (
              <span
                className="anomaly-badge"
                title={anomalyReasons.join(" · ")}
              >
                !
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}
