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
    const map = new Map<string, { reasons: string[]; direction: "up" | "down" }>();
  
    const addReason = (cik: string, reason: string, returnPct: number) => {
      const entry = map.get(cik) ?? { reasons: [], direction: returnPct >= 0 ? "up" : "down" };
      entry.reasons.push(reason);
      map.set(cik, entry);
    };
  
    for (const anomaly of latestAnomalies) {
      addReason(anomaly.cik, `Rolling anomaly on ${anomaly.date} (z=${anomaly.z_score.toFixed(2)})`, anomaly.return_pct);
    }
  
    for (const company of latestDigest?.companies ?? []) {
      if (company.is_cross_sectional_anomaly && company.return_pct != null) {
        addReason(company.cik, `Unusual vs. all tracked companies on ${latestDigest?.date}`, company.return_pct);
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
        const anomaly = anomalyByCik.get(company.cik);

        return (
          <div
            key={company.cik}
            className={["company-row", company.cik === selectedCik ? "selected" : "", anomaly ? `anomaly-${anomaly.direction}` : ""].filter(Boolean).join(" ")}
            onClick={() => onSelect(company)}
          >
            <img
              className="company-logo"
              src={`https://img.logo.dev/ticker/${company.ticker}?token=${import.meta.env.VITE_LOGODEV_TOKEN}`}
              onError={(e) => { e.currentTarget.style.display = "none"; }}
              alt=""
              title={company.name}
            />
            <div className="company-info">
              <div className="company-top-line">
                <span className="company-ticker">{company.ticker}</span>
                {returnPct != null && (
                  <span className={`return-pct ${returnPct >= 0 ? "positive" : "negative"}`}>
                    {(returnPct * 100).toFixed(1)}%
                  </span>
                )}
              </div>
              <span className="company-segment">{company.industry_segment}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
