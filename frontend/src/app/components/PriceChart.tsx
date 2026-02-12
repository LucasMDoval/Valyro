import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

export interface PriceDataPoint {
  date: string;
  price: number;
}

interface PriceChartProps {
  data: PriceDataPoint[];
  productName: string;
  loading?: boolean;
  emptyHint?: string;
}

export function PriceChart({ data, productName, loading, emptyHint }: PriceChartProps) {
  const isEmpty = !data || data.length === 0;

  return (
    <div className="bg-[#1e293b] rounded-xl p-6 border border-[#2d3548]">
      <div className="mb-6">
        <h3 className="text-lg font-semibold text-white">Evolución del Precio</h3>
        <p className="text-sm text-[#94a3b8] mt-1">{productName || '—'}</p>
      </div>

      {loading && <div className="text-sm text-[#94a3b8] mb-3">Cargando histórico…</div>}

      {isEmpty ? (
        <div className="text-sm text-[#94a3b8]">
          {emptyHint ?? 'No hay histórico suficiente para dibujar la evolución.'}
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={320}>
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#2d3548" />
            <XAxis dataKey="date" tick={{ fontSize: 12, fill: '#94a3b8' }} stroke="#2d3548" />
            <YAxis
              tick={{ fontSize: 12, fill: '#94a3b8' }}
              stroke="#2d3548"
              tickFormatter={(value) => `${value}€`}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#1a1f2e',
                border: '1px solid #2d3548',
                borderRadius: '8px',
                fontSize: '12px',
                color: '#fff',
              }}
              formatter={(value: number) => [`${Number(value).toFixed(2)}€`, 'Mediana']}
            />
            <Legend wrapperStyle={{ fontSize: '12px', color: '#94a3b8' }} iconType="line" />
            <Line
              type="monotone"
              dataKey="price"
              stroke="#13C1AC"
              strokeWidth={2}
              dot={false}
              name="Mediana"
              connectNulls
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
