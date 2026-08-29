import { useEffect, useState } from "react";
import { api } from "./api/client";
import { dateRangeFor, chartRangeFor, type Timeframe } from "./lib/timeframes";

import CompanyList from "./components/CompanyList";
import TimeframeSelect from "./components/TimeframeSelect";
import PriceChart from "./components/PriceChart";
import AnomalyPanel from "./components/AnomalyPanel";
import AgentChat from "./components/AgentChat";

export default function App() {
  const [companies, setCompanies] = useState<
    NonNullable<Awaited<ReturnType<typeof api.listCompanies>>>
  >([]);

  const [latestAnomalies, setLatestAnomalies] = useState<
    NonNullable<Awaited<ReturnType<typeof api.latestAnomalies>>>
  >([]);

  const [latestDigest, setLatestDigest] = useState<
    Awaited<ReturnType<typeof api.latestDigest>> | null
  >(null);

  const [timeframe, setTimeframe] =
    useState<Timeframe>("1D");

  const [returns, setReturns] = useState<
    Record<string, number | null>
  >({});

  const [selected, setSelected] =
    useState<(typeof companies)[number] | null>(null);

  const [prices, setPrices] = useState<
    NonNullable<Awaited<ReturnType<typeof api.prices>>>
  >([]);

  useEffect(() => {
    api.listCompanies().then(setCompanies);
    api.latestAnomalies().then(setLatestAnomalies);

    api.latestDigest()
      .then(setLatestDigest)
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (timeframe === "1D") {
      if (!latestDigest) return;
      const digestReturns = Object.fromEntries(
        latestDigest.companies.map((c) => [c.cik, c.return_pct])
      );
      setReturns(digestReturns);
      return;
    }
  
    const { start, end } = dateRangeFor(timeframe);
    api.periodReturns(start, end).then((data) => {
      console.log("periodReturns response:", data);
      setReturns(data.returns);
    });
  }, [timeframe, companies.length, latestDigest]);

  useEffect(() => {
    if (!selected) return;
    const { start, end } = chartRangeFor(timeframe);
    api.prices(selected.cik, start, end).then(setPrices);
  }, [selected, timeframe]);

  const { start, end } = dateRangeFor(timeframe);

  return (
    <div className="layout">
      <CompanyList
        companies={companies}
        returns={returns}
        latestAnomalies={latestAnomalies}
        latestDigest={latestDigest}
        selectedCik={selected?.cik}
        onSelect={setSelected}
      />

      <div className="main">
        <TimeframeSelect
          value={timeframe}
          onChange={setTimeframe}
        />

        {selected ? (
          <>
            <h2>
              {selected.name} ({selected.ticker})
            </h2>

            <PriceChart prices={prices} />

            <AnomalyPanel
              cik={selected.cik}
              start={start}
              end={end}
            />
          </>
        ) : (
          <p style={{ color: "var(--text-dim)" }}>
            Select a company to see its chart and anomalies.
          </p>
        )}

        <AgentChat selectedCompany={selected} />
      </div>
    </div>
  );
}
