import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Upload, Link as LinkIcon, Trash2 } from 'lucide-react';
import { importDrive, importUpload, listDatasets, deleteDataset } from '../api/client';
import { useJobSSE } from '../hooks/useJobSSE';
import ProgressStepper from '../components/ProgressStepper';

export default function ImportPage() {
  const navigate = useNavigate();
  const [tab, setTab] = useState<'drive' | 'upload'>('upload');
  const [url, setUrl] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [timezone, setTimezone] = useState('America/Chicago');
  const [threshold, setThreshold] = useState(0.6);
  const [forceRedo, setForceRedo] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [datasetId, setDatasetId] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const job = useJobSSE(jobId);

  const { data: datasets, refetch: refetchDatasets } = useQuery({
    queryKey: ['datasets'],
    queryFn: listDatasets,
  });

  const handleSubmit = async () => {
    setError('');
    setSubmitting(true);
    try {
      let res;
      if (tab === 'drive') {
        if (!url) { setError('Enter a Google Drive URL'); setSubmitting(false); return; }
        res = await importDrive(url, timezone, threshold, forceRedo);
      } else {
        if (!file) { setError('Select a file'); setSubmitting(false); return; }
        res = await importUpload(file, timezone, threshold, forceRedo);
      }
      setDatasetId(res.dataset_id);
      setJobId(res.job_id);
    } catch (e) {
      setError(String(e));
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: string) => {
    await deleteDataset(id);
    refetchDatasets();
  };

  // Navigate to dashboard when job completes
  if (job?.status === 'completed' && datasetId) {
    setTimeout(() => navigate(`/dashboard?ds=${datasetId}`), 1500);
  }

  return (
    <div className="max-w-2xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-bold">Import WhatsApp Chat</h1>
        <p className="text-gray-500 mt-1">Upload your exported WhatsApp chat archive to analyze food and calories.</p>
      </div>

      {!jobId && (
        <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-5">
          <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
            <button onClick={() => setTab('upload')}
              className={`flex-1 flex items-center justify-center gap-1.5 py-2 rounded-md text-sm font-medium transition-colors ${tab === 'upload' ? 'bg-white shadow-sm' : 'text-gray-500'}`}>
              <Upload size={16} /> File Upload
            </button>
            <button onClick={() => setTab('drive')}
              className={`flex-1 flex items-center justify-center gap-1.5 py-2 rounded-md text-sm font-medium transition-colors ${tab === 'drive' ? 'bg-white shadow-sm' : 'text-gray-500'}`}>
              <LinkIcon size={16} /> Google Drive
            </button>
          </div>

          {tab === 'upload' ? (
            <div>
              <label className="block text-sm font-medium mb-1">Archive file (.zip, .rar, .7z)</label>
              <input type="file" accept=".zip,.rar,.7z"
                onChange={e => setFile(e.target.files?.[0] || null)}
                className="w-full text-sm border rounded-lg px-3 py-2" />
            </div>
          ) : (
            <div>
              <label className="block text-sm font-medium mb-1">Google Drive share link</label>
              <input type="url" value={url} onChange={e => setUrl(e.target.value)}
                placeholder="https://drive.google.com/file/d/..."
                className="w-full border rounded-lg px-3 py-2 text-sm" />
            </div>
          )}

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-1">Timezone</label>
              <input type="text" value={timezone} onChange={e => setTimezone(e.target.value)}
                className="w-full border rounded-lg px-3 py-2 text-sm" />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Food confidence threshold</label>
              <input type="number" step="0.1" min="0" max="1" value={threshold}
                onChange={e => setThreshold(parseFloat(e.target.value))}
                className="w-full border rounded-lg px-3 py-2 text-sm" />
            </div>
          </div>

          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={forceRedo} onChange={e => setForceRedo(e.target.checked)} />
            Force re-process (ignore cache)
          </label>

          {error && <p className="text-sm text-red-600">{error}</p>}

          <button onClick={handleSubmit} disabled={submitting}
            className="w-full py-2.5 bg-emerald-600 text-white font-medium rounded-lg hover:bg-emerald-700 disabled:opacity-50 transition-colors">
            {submitting ? 'Submitting...' : 'Start Import'}
          </button>
        </div>
      )}

      {job && (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="font-semibold mb-4">Processing</h2>
          <ProgressStepper job={job} />
          {job.status === 'completed' && (
            <p className="mt-3 text-sm text-emerald-600 font-medium">Redirecting to dashboard...</p>
          )}
        </div>
      )}

      {datasets && datasets.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold mb-3">Previous Imports</h2>
          <div className="space-y-2">
            {datasets.map(ds => (
              <div key={ds.id} className="bg-white rounded-lg border border-gray-200 px-4 py-3 flex items-center justify-between">
                <button onClick={() => navigate(`/dashboard?ds=${ds.id}`)} className="text-left flex-1">
                  <p className="text-sm font-medium">{ds.name}</p>
                  <p className="text-xs text-gray-400">
                    {ds.status} &middot; {ds.date_range_start} to {ds.date_range_end}
                  </p>
                </button>
                <button onClick={() => handleDelete(ds.id)} className="p-1.5 text-gray-400 hover:text-red-500">
                  <Trash2 size={16} />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
