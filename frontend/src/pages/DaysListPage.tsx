import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { listDays } from '../api/client';
import { useActiveDataset } from '../hooks/useActiveDataset';

export default function DaysListPage() {
  const navigate = useNavigate();
  const dsId = useActiveDataset();

  const { data: days } = useQuery({
    queryKey: ['days', dsId],
    queryFn: () => listDays(dsId!),
    enabled: !!dsId,
  });

  if (!dsId) {
    return (
      <div className="text-center py-20 space-y-4">
        <p className="text-gray-500 text-lg">No dataset selected</p>
        <p className="text-gray-400 text-sm">Import a new chat or select from your previous imports.</p>
        <button
          onClick={() => navigate('/')}
          className="inline-flex items-center gap-2 px-4 py-2 bg-emerald-600 text-white font-medium rounded-lg hover:bg-emerald-700 transition-colors"
        >
          Go to Import
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Days</h1>
      {days && (
        <div className="space-y-2">
          {days.filter(day => day.total_calories > 0).map(day => (
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
