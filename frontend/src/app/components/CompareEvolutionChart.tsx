import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts";

type Props = {
  title: string;
  data: Array<Record<string, any>>; // { date: '...', [keyword]: number }
  keywords: string[];
};

const COLORS = ["#13C1AC", "#60a5fa", "#f59e0b", "#ef4444", "#a78bfa", "#22c55e", "#f97316"];

export function CompareEvolutionChart({ title, data, keywords }: Props) {
  return (
    <div className="bg-[#1e293b] rounded-xl p-6 border border-[#2d3548]">
      <div className="mb-6">
        <h3 className="text-lg font-semibold text-white">{title}</h3>
        <p className="text-sm text-[#94a3b8] mt-1">Mediana por run (histórico)</p>
      </div>

      <ResponsiveContainer width="100%" height={340}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#2d3548" />
          <XAxis dataKey="date" tick={{ fontSize: 12, fill: "#94a3b8" }} stroke="#2d3548" />
          <YAxis tick={{ fontSize: 12, fill: "#94a3b8" }} stroke="#2d3548" tickFormatter={(v) => `${v}€`} />
          <Tooltip
            contentStyle={{
              backgroundColor: "#1a1f2e",
              border: "1px solid #2d3548",
              borderRadius: "8px",
              fontSize: "12px",
              color: "#fff",
            }}
            formatter={(value: number, name: string) => [`${Number(value).toFixed(2)}€`, name]}
          />
          <Legend wrapperStyle={{ fontSize: "12px", color: "#94a3b8" }} iconType="line" />

          {keywords.map((kw, i) => (
            <Line
              key={kw}
              type="monotone"
              dataKey={kw}
              stroke={COLORS[i % COLORS.length]}
              strokeWidth={2}
              dot={false}
              name={kw}
              connectNulls
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
