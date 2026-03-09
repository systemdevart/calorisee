import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { X } from 'lucide-react';
import { getMessageDetail, overrideMessage, type MessageOverride } from '../api/client';
import MacroBar from './MacroBar';

interface Props {
  datasetId: string;
  messageId: string;
  onClose: () => void;
}

export default function MessageDetailModal({ datasetId, messageId, onClose }: Props) {
  const qc = useQueryClient();
  const { data: msg, isLoading } = useQuery({
    queryKey: ['message', datasetId, messageId],
    queryFn: () => getMessageDetail(datasetId, messageId),
  });

  const [editCals, setEditCals] = useState('');
  const [editProtein, setEditProtein] = useState('');
  const [editCarbs, setEditCarbs] = useState('');
  const [editFat, setEditFat] = useState('');

  const mutation = useMutation({
    mutationFn: (body: MessageOverride) => overrideMessage(datasetId, messageId, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['message', datasetId, messageId] });
      qc.invalidateQueries({ queryKey: ['day'] });
      qc.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });

  const handleSave = () => {
    const body: MessageOverride = {};
    if (editCals) body.corrected_total_calories = parseFloat(editCals);
    if (editProtein) body.corrected_total_protein_g = parseFloat(editProtein);
    if (editCarbs) body.corrected_total_carbs_g = parseFloat(editCarbs);
    if (editFat) body.corrected_total_fat_g = parseFloat(editFat);
    if (Object.keys(body).length > 0) mutation.mutate(body);
  };

  const handleToggleExclude = () => {
    mutation.mutate({ excluded: !msg?.excluded });
  };

  const est = msg?.estimation as Record<string, unknown> | null;
  const items = est && Array.isArray(est.items) ? est.items as Array<Record<string, unknown>> : [];
  const visualDesc = est?.visual_description as string | undefined;
  const mealName = est?.meal_name as string | undefined;

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between p-4 border-b">
          <h2 className="font-semibold">Message Detail</h2>
          <button onClick={onClose} className="p-1 hover:bg-gray-100 rounded"><X size={20} /></button>
        </div>

        {isLoading && <div className="p-8 text-center text-gray-400">Loading...</div>}

        {msg && (
          <div className="p-4 space-y-4">
            <div className="text-sm text-gray-500">
              {new Date(msg.timestamp).toLocaleString()} &middot; {msg.sender}
            </div>

            <p className="text-sm whitespace-pre-wrap">{msg.text}</p>

            {msg.has_media && msg.media_urls.length > 0 && (
              <div className="flex gap-2">
                {msg.media_urls.map((url, i) => (
                  <img key={i} src={`${url}?msg_id=${msg.id}`} alt="" className="rounded-lg max-h-64 object-contain" />
                ))}
              </div>
            )}

            {msg.is_food && msg.total_calories != null && (
              <div className="bg-gray-50 rounded-lg p-4 space-y-3">
                {mealName && (
                  <p className="font-semibold text-gray-800">{mealName}</p>
                )}

                {visualDesc && (
                  <p className="text-sm text-gray-600 italic">{visualDesc}</p>
                )}

                <div className="flex items-baseline gap-2">
                  <span className="text-2xl font-bold">{Math.round(msg.total_calories)}</span>
                  <span className="text-gray-500">kcal</span>
                  {msg.uncertainty_level && (
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      msg.uncertainty_level === 'high' ? 'bg-red-100 text-red-600' :
                      msg.uncertainty_level === 'medium' ? 'bg-amber-100 text-amber-700' :
                      'bg-green-100 text-green-700'
                    }`}>{msg.uncertainty_level} uncertainty</span>
                  )}
                </div>
                <MacroBar protein={msg.protein_g ?? 0} carbs={msg.carbs_g ?? 0} fat={msg.fat_g ?? 0} />

                {items.length > 0 && (
                  <div className="mt-2 space-y-2">
                    <p className="text-xs font-medium text-gray-500">Items breakdown</p>
                    {items.map((item, i) => (
                      <div key={i} className="border border-gray-100 rounded-lg p-2.5 space-y-1">
                        <div className="flex items-baseline justify-between">
                          <span className="text-sm font-medium">{String(item.name)}</span>
                          <span className="text-sm font-semibold">{String(item.calories)} kcal</span>
                        </div>
                        {item.portion_description ? (
                          <p className="text-xs text-gray-500">{String(item.portion_description)}</p>
                        ) : null}
                        <div className="flex gap-3 text-xs text-gray-400">
                          <span>{String(item.estimated_grams ?? '?')}g</span>
                          <span>P {String(item.protein_g)}g</span>
                          <span>C {String(item.carbs_g)}g</span>
                          <span>F {String(item.fat_g)}g</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {msg.has_override && msg.overrides && (
              <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm">
                <p className="font-medium text-amber-800 mb-1">User overrides applied</p>
                <pre className="text-xs text-amber-700 overflow-x-auto">{JSON.stringify(msg.overrides, null, 2)}</pre>
              </div>
            )}

            <div className="border-t pt-4 space-y-3">
              <p className="text-sm font-medium">Corrections</p>
              <div className="grid grid-cols-4 gap-2">
                <div>
                  <label className="text-xs text-gray-500">Calories</label>
                  <input type="number" value={editCals} onChange={e => setEditCals(e.target.value)}
                    placeholder={String(msg.total_calories ?? '')}
                    className="w-full border rounded px-2 py-1 text-sm" />
                </div>
                <div>
                  <label className="text-xs text-gray-500">Protein (g)</label>
                  <input type="number" value={editProtein} onChange={e => setEditProtein(e.target.value)}
                    placeholder={String(msg.protein_g ?? '')}
                    className="w-full border rounded px-2 py-1 text-sm" />
                </div>
                <div>
                  <label className="text-xs text-gray-500">Carbs (g)</label>
                  <input type="number" value={editCarbs} onChange={e => setEditCarbs(e.target.value)}
                    placeholder={String(msg.carbs_g ?? '')}
                    className="w-full border rounded px-2 py-1 text-sm" />
                </div>
                <div>
                  <label className="text-xs text-gray-500">Fat (g)</label>
                  <input type="number" value={editFat} onChange={e => setEditFat(e.target.value)}
                    placeholder={String(msg.fat_g ?? '')}
                    className="w-full border rounded px-2 py-1 text-sm" />
                </div>
              </div>
              <div className="flex gap-2">
                <button onClick={handleSave} disabled={mutation.isPending}
                  className="px-4 py-1.5 bg-emerald-600 text-white text-sm rounded-lg hover:bg-emerald-700 disabled:opacity-50">
                  Save corrections
                </button>
                <button onClick={handleToggleExclude} disabled={mutation.isPending}
                  className="px-4 py-1.5 border border-gray-300 text-sm rounded-lg hover:bg-gray-50 disabled:opacity-50">
                  {msg.excluded ? 'Include' : 'Exclude'} this entry
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
