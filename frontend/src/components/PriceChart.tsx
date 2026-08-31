import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

import type { StockPrice } from "../api/types";

interface PriceChartProps {
  prices: StockPrice[];
}

export default function PriceChart({ prices }: PriceChartProps) {
  return (
    <div>
      <div className="section-heading">Stock price</div>
      {prices.length ? (
        <div className="panel" style={{ height: 260 }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={prices}>
              <XAxis dataKey="date" tick={{ fontSize: 11 }} />
              <YAxis domain={["auto", "auto"]} tick={{ fontSize: 11 }} />
              <Tooltip />
              <Line
                type="linear"
                dataKey="close"
                stroke="var(--accent)"
                dot={false}
                strokeWidth={2}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div className="panel">No price data for this range.</div>
      )}
    </div>
  );
}
