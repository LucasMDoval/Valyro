interface ProductComparisonTableProps {
  products: {
    keyword: string;
    lastAnalysis: string;
    median: number;
    q1: number;
    q2: number;
    q3: number;
    normalRange: string;
  }[];
  onProductClick?: (keyword: string, median: number) => void;
}

export function ProductComparisonTable({ products, onProductClick }: ProductComparisonTableProps) {
  return (
    <div className="bg-[#1e293b] rounded-xl p-6 border border-[#2d3548]">
      <div className="mb-6">
        <h3 className="text-lg font-semibold text-white">Comparación de Productos</h3>
        <p className="text-sm text-[#94a3b8] mt-1">Análisis estadístico de las búsquedas</p>
      </div>
      
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-[#2d3548]">
              <th className="text-left py-3 px-4 text-sm font-semibold text-white">Keyword</th>
              <th className="text-left py-3 px-4 text-sm font-semibold text-white">Último Análisis</th>
              <th className="text-right py-3 px-4 text-sm font-semibold text-white">Mediana</th>
              <th className="text-right py-3 px-4 text-sm font-semibold text-white">Q1</th>
              <th className="text-right py-3 px-4 text-sm font-semibold text-white">Q2</th>
              <th className="text-right py-3 px-4 text-sm font-semibold text-white">Q3</th>
              <th className="text-left py-3 px-4 text-sm font-semibold text-white">Rango Normal</th>
            </tr>
          </thead>
          <tbody>
            {products.map((product, index) => (
              <tr 
                key={index}
                className="border-b border-[#2d3548]/50 hover:bg-[#252b3d] transition-colors cursor-pointer"
                onClick={() => onProductClick && onProductClick(product.keyword, product.median)}
              >
                <td className="py-4 px-4">
                  <span className="text-sm font-medium text-white">{product.keyword}</span>
                </td>
                <td className="py-4 px-4">
                  <span className="text-sm text-[#94a3b8]">{product.lastAnalysis}</span>
                </td>
                <td className="py-4 px-4 text-right">
                  <span className="text-sm font-semibold text-[#13C1AC]">{product.median.toFixed(2)}€</span>
                </td>
                <td className="py-4 px-4 text-right">
                  <span className="text-sm text-[#94a3b8]">{product.q1.toFixed(2)}€</span>
                </td>
                <td className="py-4 px-4 text-right">
                  <span className="text-sm text-[#94a3b8]">{product.q2.toFixed(2)}€</span>
                </td>
                <td className="py-4 px-4 text-right">
                  <span className="text-sm text-[#94a3b8]">{product.q3.toFixed(2)}€</span>
                </td>
                <td className="py-4 px-4">
                  <span className="text-sm text-[#94a3b8]">{product.normalRange}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}