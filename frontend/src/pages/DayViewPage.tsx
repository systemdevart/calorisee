import { useState } from 'react';
import { useParams, useSearchParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { ChevronLeft } from 'lucide-react';
import { getDayDetail } from '../api/client';
import MealCard from '../components/MealCard';
import MacroBar from '../components/MacroBar';
import MessageDetailModal from '../components/MessageDetailModal';

export default function DayViewPage() {
  const { day } = useParams<{ day: string }>();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const dsId = params.get('ds') || '';
  const [selectedMsg, setSelectedMsg] = useState<string | null>(null);

  const { data } = useQuery({
    queryKey: ['day', dsId, day],
    queryFn: () => getDayDetail(dsId, day!),
    enabled: !!dsId && !!day,
  });

  if (!data) return <div className="text-center py-20 text-gray-400">Loading...</div>;

  const dateStr = new Date(data.date + 'T12:00:00').toLocaleDateString(undefined, {
    weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
  });

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <button onClick={() => navigate(-1)} className="p-1.5 hover:bg-gray-100 rounded-lg">
          <ChevronLeft size={20} />
        </button>
        <div>
          <h1 className="text-xl font-bold">{dateStr}</h1>
          <p className="text-sm text-gray-500">
            {Math.round(data.total_calories)} kcal &middot; {data.meal_count} meals
          </p>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <MacroBar protein={data.total_protein_g} carbs={data.total_carbs_g} fat={data.total_fat_g} />
      </div>

      <div className="space-y-3">
        {data.messages
          .filter(m => m.is_food && !m.excluded)
          .map(msg => (
            <MealCard key={msg.id} msg={msg} onClick={() => setSelectedMsg(msg.id)} />
          ))}
      </div>

      {data.messages.some(m => !m.is_food || m.excluded) && (
        <details className="bg-white rounded-xl border border-gray-200 p-4">
          <summary className="text-sm font-medium text-gray-500 cursor-pointer">
            Other messages ({data.messages.filter(m => !m.is_food || m.excluded).length})
          </summary>
          <div className="mt-3 space-y-2">
            {data.messages
              .filter(m => !m.is_food || m.excluded)
              .map(msg => (
                <MealCard key={msg.id} msg={msg} onClick={() => setSelectedMsg(msg.id)} />
              ))}
          </div>
        </details>
      )}

      {selectedMsg && (
        <MessageDetailModal datasetId={dsId} messageId={selectedMsg} onClose={() => setSelectedMsg(null)} />
      )}
    </div>
  );
}
