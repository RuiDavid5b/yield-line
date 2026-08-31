export const TIMEFRAMES = {
  "1D": 1,
  "1W": 7,
  "1M": 30,
  "3M": 90,
  "1Y": 365,
  "5Y": 365 * 5,
} as const;

export type Timeframe = keyof typeof TIMEFRAMES | "YTD";

export function dateRangeFor(timeframe: Timeframe) {
  const end = new Date();
  const start = new Date();

  if (timeframe === "YTD") {
    start.setMonth(0, 1);
  } else {
    start.setDate(start.getDate() - TIMEFRAMES[timeframe]);
  }

  const iso = (d: Date) => d.toISOString().slice(0, 10);

  return {
    start: iso(start),
    end: iso(end),
  };
}

export function chartRangeFor(timeframe: Timeframe) {
  if (timeframe === "1D") return dateRangeFor("1W");
  return dateRangeFor(timeframe);
}
