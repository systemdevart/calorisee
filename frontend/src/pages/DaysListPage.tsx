import { useSearchParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { listDays, listDatasets } from '../api/client';

export default function DaysListPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();

  const { data: datasets } = useQuery({ queryKey: ['datasets'], queryFn: listDatasets });
  const dsId = params.get('ds') || datasets?.find(d => d.status === 'completed')?.id;

  const { data: days } = useQuery({
    queryKey: ['days', dsId],
    queryFn: () => listDays(dsId!),
    enabled: !!dsId,
  });

  if (!dsId) {
    return <div className="text-center py-20 text-gray-500">No dataset loaded. <button onClick={() => navigate('/')} className="text-emerald-600 underline">Import one</button></div>;
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Days</h1>
      {days && (
        <div className="space-y-2">
          {days.map(day => (
            <button
              key={day.date}
              onClick={() => navigate(`/days/${day.date}?ds=${dsId}`)}
              className="w-full bg-white rounded-lg border border-gray-200 px-4 py-3 flex items-center justify-between hover:border-emerald-300 transition-colors"
            >
              <div className="text-left">
                <p className="font-medium">{new Date(day.date + 'T12:00:00').toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })}</p>
                <p className="text-xs text-gray-400">{day.food_messages} food / {day.total_messages} msgs</p>
              </div>
              <div className="text-right">
                <p className="text-lg font-semibold">{Math.round(day.total_calories)}</p>
                <p className="text-xs text-gray-400">kcal</p>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
