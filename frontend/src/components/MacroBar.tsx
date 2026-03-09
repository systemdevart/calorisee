export default function MacroBar({ protein, carbs, fat }: { protein: number; carbs: number; fat: number }) {
  const total = protein + carbs + fat;
  if (total === 0) return null;

  const pPct = (protein / total) * 100;
  const cPct = (carbs / total) * 100;
  const fPct = (fat / total) * 100;

  return (
    <div className="space-y-1">
      <div className="flex h-3 rounded-full overflow-hidden">
        <div className="bg-blue-500" style={{ width: `${pPct}%` }} title={`Protein ${protein.toFixed(0)}g`} />
        <div className="bg-amber-400" style={{ width: `${cPct}%` }} title={`Carbs ${carbs.toFixed(0)}g`} />
        <div className="bg-rose-400" style={{ width: `${fPct}%` }} title={`Fat ${fat.toFixed(0)}g`} />
      </div>
      <div className="flex gap-3 text-xs text-gray-500">
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-blue-500 inline-block" />P {protein.toFixed(0)}g</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-amber-400 inline-block" />C {carbs.toFixed(0)}g</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-rose-400 inline-block" />F {fat.toFixed(0)}g</span>
      </div>
    </div>
  );
}
