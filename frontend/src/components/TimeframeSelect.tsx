import { TIMEFRAMES, type Timeframe } from "../lib/timeframes";

interface Props {
  value: Timeframe;
  onChange: (value: Timeframe) => void;
}

export default function TimeframeSelect({ value, onChange }: Props) {
  return (
    <select className="timeframe-select"
      value={value}
      onChange={(e) => onChange(e.target.value as Timeframe)}
    >
      {Object.keys(TIMEFRAMES).map((tf) => (
        <option key={tf} value={tf}>
          {tf}
        </option>
      ))}
      <option value="YTD">YTD</option>
    </select>
  );
}

export function chartRangeFor(timeframe: Timeframe) {
  if (timeframe === "1D") return dateRangeFor("1W");
  return dateRangeFor(timeframe);
}
