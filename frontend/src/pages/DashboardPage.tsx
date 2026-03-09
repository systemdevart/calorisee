import { useSearchParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { getDashboardSummary, getDailyTimeseries, getTopItems, listDatasets } from '../api/client';
import KpiCard from '../components/KpiCard';
import MacroBar from '../components/MacroBar';

export default function DashboardPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const dsId = params.get('ds');

  const { data: datasets } = useQuery({
    queryKey: ['datasets'],
    queryFn: listDatasets,
    enabled: !dsId,
  });

  // Auto-select first completed dataset
  const effectiveId = dsId || datasets?.find(d => d.status === 'completed')?.id;

  const { data: summary } = useQuery({
    queryKey: ['dashboard', 'summary', effectiveId],
    queryFn: () => getDashboardSummary(effectiveId!),
    enabled: !!effectiveId,
  });

  const { data: daily } = useQuery({
    queryKey: ['dashboard', 'daily', effectiveId],
    queryFn: () => getDailyTimeseries(effectiveId!),
    enabled: !!effectiveId,
  });

  const { data: top } = useQuery({
    queryKey: ['dashboard', 'top', effectiveId],
    queryFn: () => getTopItems(effectiveId!),
    enabled: !!effectiveId,
  });

  if (!effectiveId) {
    return (
      <div className="text-center py-20">
        <p className="text-gray-500">No dataset loaded.</p>
        <button onClick={() => navigate('/')} className="mt-3 text-emerald-600 underline">Import one</button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Dashboard</h1>
        {summary?.date_range_start && (
          <span className="text-sm text-gray-400">{summary.date_range_start} — {summary.date_range_end}</span>
        )}
      </div>

      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <KpiCard label="Avg kcal (7d)" value={Math.round(summary.avg_calories_7d)} />
          <KpiCard label="Avg kcal (30d)" value={Math.round(summary.avg_calories_30d)} />
          <KpiCard label="Days logged (30d)" value={summary.days_logged_30d} />
          <KpiCard label="Food messages" value={summary.total_food_messages} sub={`of ${summary.total_messages} total`} />
        </div>
      )}

      {summary && (
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <p className="text-sm font-medium text-gray-500 mb-2">Average Macros (30d)</p>
          <MacroBar protein={summary.avg_protein_g} carbs={summary.avg_carbs_g} fat={summary.avg_fat_g} />
        </div>
      )}

      {daily && daily.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <p className="text-sm font-medium text-gray-500 mb-3">Daily Calories</p>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={daily} onClick={(e: Record<string, unknown>) => {
              const payload = e?.activePayload as Array<{ payload: { date: string } }> | undefined;
              if (payload?.[0]) {
                navigate(`/days/${payload[0].payload.date}?ds=${effectiveId}`);
              }
            }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="date" tickFormatter={d => d.slice(5)} tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v: unknown) => [`${Math.round(Number(v))} kcal`, 'Calories']} />
              <Bar dataKey="calories" fill="#10b981" radius={[4, 4, 0, 0]} cursor="pointer" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="grid md:grid-cols-2 gap-6">
        {top && top.length > 0 && (
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <p className="text-sm font-medium text-gray-500 mb-3">Top Items</p>
            <div className="space-y-2">
              {top.slice(0, 10).map((item, i) => (
                <div key={i} className="flex items-center justify-between text-sm">
                  <span className="truncate">{item.name}</span>
                  <span className="text-gray-500 ml-2 flex-shrink-0">{item.count}x &middot; {Math.round(item.total_calories)} kcal</span>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <p className="text-sm font-medium text-gray-500 mb-3">Quick Links</p>
          <button onClick={() => navigate(`/days?ds=${effectiveId}`)}
            className="w-full text-left px-4 py-3 rounded-lg hover:bg-gray-50 text-sm font-medium border border-gray-100">
            Browse all days →
          </button>
        </div>
      </div>
    </div>
  );
}
