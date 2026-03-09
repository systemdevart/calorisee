import type { MessageSummary } from '../api/client';
import MacroBar from './MacroBar';

export default function MealCard({ msg, onClick }: { msg: MessageSummary; onClick: () => void }) {
  const time = msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '';

  return (
    <button
      onClick={onClick}
      className="w-full text-left bg-white rounded-xl border border-gray-200 p-4 hover:border-emerald-300 transition-colors"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <span>{time}</span>
            <span>{msg.sender}</span>
            {msg.excluded && <span className="text-xs bg-gray-100 text-gray-500 px-1.5 rounded">excluded</span>}
            {msg.has_override && <span className="text-xs bg-amber-100 text-amber-700 px-1.5 rounded">edited</span>}
            {msg.uncertainty_level === 'high' && <span className="text-xs bg-red-100 text-red-600 px-1.5 rounded">uncertain</span>}
          </div>
          <p className="mt-1 text-sm truncate">{msg.text}</p>
          {msg.is_food && msg.total_calories != null && !msg.excluded && (
            <div className="mt-2 space-y-1">
              <p className="text-lg font-semibold">{Math.round(msg.total_calories)} kcal</p>
              <MacroBar protein={msg.protein_g ?? 0} carbs={msg.carbs_g ?? 0} fat={msg.fat_g ?? 0} />
            </div>
          )}
          {!msg.is_food && (
            <p className="text-xs text-gray-400 mt-1">{msg.food_context}</p>
          )}
        </div>
        {msg.has_media && msg.media_urls.length > 0 && (
          <img
            src={`${msg.media_urls[0]}?msg_id=${msg.id}`}
            alt=""
            className="w-16 h-16 rounded-lg object-cover flex-shrink-0"
          />
        )}
      </div>
    </button>
  );
}
