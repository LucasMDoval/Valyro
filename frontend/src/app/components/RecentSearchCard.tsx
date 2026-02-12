import type { ReactNode } from 'react';
import { TrendingDown, TrendingUp, Minus } from 'lucide-react';

interface RecentSearchCardProps {
  keyword: string;
  medianPrice: number;
  priceChange: number; // % (ej: -3.2, +4.1)
  icon: ReactNode;
  onClick: () => void;
}

export function RecentSearchCard({ keyword, medianPrice, priceChange, icon, onClick }: RecentSearchCardProps) {
  const isUp = priceChange > 0;
  const isDown = priceChange < 0;

  const badgeClass = isUp
    ? 'bg-green-500/20 text-green-300'
    : isDown
    ? 'bg-red-500/20 text-red-300'
    : 'bg-slate-500/20 text-slate-300';

  const ArrowIcon = isUp ? TrendingUp : isDown ? TrendingDown : Minus;

  return (
    <button
      onClick={onClick}
      className="bg-[#1e293b] rounded-xl p-6 border border-[#2d3548] hover:shadow-lg hover:shadow-[#13C1AC]/10 hover:border-[#13C1AC]/50 transition-all text-left w-full"
    >
      <div className="flex items-start justify-between mb-4">
        <div className="w-12 h-12 rounded-lg bg-[#13C1AC]/20 flex items-center justify-center text-[#13C1AC]">
          {icon}
        </div>

        <div className={`flex items-center gap-1 px-2 py-1 rounded-full text-xs ${badgeClass}`}>
          {isUp ? '+' : ''}
          {priceChange.toFixed(1)}%
          <ArrowIcon className="w-3 h-3" />
        </div>
      </div>

      <div>
        <p className="text-sm text-[#94a3b8] mb-1">{keyword}</p>
        <p className="text-3xl font-bold text-white">{medianPrice.toFixed(2)}€</p>
        <p className="text-xs text-[#94a3b8] mt-1">Precio mediano</p>
      </div>
    </button>
  );
}
