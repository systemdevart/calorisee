import { useState, useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Upload, Link as LinkIcon, Trash2, ChevronDown, ChevronUp } from 'lucide-react';
import { importDrive, importUpload, listDatasets, deleteDataset } from '../api/client';
import { useJobSSE } from '../hooks/useJobSSE';
import ProgressStepper from '../components/ProgressStepper';

const STORAGE_KEY = 'calorisee_my_datasets';
const ACTIVE_JOB_KEY = 'calorisee_active_job';

// --- localStorage helpers for dataset IDs ---

function getMyDatasetIds(): string[] {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
  } catch {
    return [];
  }
}

function addMyDatasetId(id: string) {
  const ids = getMyDatasetIds();
  if (!ids.includes(id)) {
    ids.unshift(id);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(ids));
  }
}

function removeMyDatasetId(id: string) {
  const ids = getMyDatasetIds().filter(x => x !== id);
  localStorage.setItem(STORAGE_KEY, JSON.stringify(ids));
}

// --- localStorage helpers for active job ---

interface ActiveJob {
  jobId: string;
  datasetId: string;
}

function getActiveJob(): ActiveJob | null {
  try {
    const raw = localStorage.getItem(ACTIVE_JOB_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function setActiveJob(jobId: string, datasetId: string) {
  localStorage.setItem(ACTIVE_JOB_KEY, JSON.stringify({ jobId, datasetId }));
}

function clearActiveJob() {
  localStorage.removeItem(ACTIVE_JOB_KEY);
}

// --- Collapsible sections ---

function ExportGuide() {
  const [open, setOpen] = useState(false);

  return (
    <div className="bg-white rounded-xl border border-gray-200">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between p-4 text-left"
      >
        <span className="font-semibold text-sm">How to export your WhatsApp chat</span>
        {open ? <ChevronUp size={18} className="text-gray-400" /> : <ChevronDown size={18} className="text-gray-400" />}
      </button>

      {open && (
        <div className="px-4 pb-4 space-y-4">
          <div className="space-y-2.5 text-sm text-gray-700">
            <p className="font-medium text-gray-900">In WhatsApp:</p>
            <ol className="list-decimal list-inside space-y-1.5 ml-1">
              <li>Open the chat you want to analyze</li>
              <li>Tap the <span className="font-medium">three dots</span> (top-right corner)</li>
              <li>Select <span className="font-medium">More</span></li>
              <li>Select <span className="font-medium">Export chat</span></li>
              <li>Choose <span className="font-medium">Include media</span> (important for photo analysis)</li>
              <li>Select <span className="font-medium">Google Drive</span> as the destination and save</li>
            </ol>

            <p className="font-medium text-gray-900 pt-2">In Google Drive:</p>
            <ol className="list-decimal list-inside space-y-1.5 ml-1" start={7}>
              <li>Open the <span className="font-medium">Google Drive</span> app</li>
              <li>Find the exported archive file</li>
              <li>Tap the <span className="font-medium">three dots</span> next to the file</li>
              <li>Tap <span className="font-medium">Share</span></li>
              <li>Under "General access", change to <span className="font-medium">Anyone with the link</span></li>
              <li>Tap <span className="font-medium">Copy link</span></li>
              <li>Paste the link below and hit <span className="font-medium">Start Import</span></li>
            </ol>
          </div>
        </div>
      )}
    </div>
  );
}

function HowItWorks() {
  const [open, setOpen] = useState(false);

  return (
    <div className="bg-white rounded-xl border border-gray-200">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between p-4 text-left"
      >
        <span className="font-semibold text-sm">How the analysis works</span>
        {open ? <ChevronUp size={18} className="text-gray-400" /> : <ChevronDown size={18} className="text-gray-400" />}
      </button>

      {open && (
        <div className="px-4 pb-4 text-sm text-gray-700 space-y-3">
          <p>
            CaloriSee uses a two-stage AI pipeline to analyze your WhatsApp food messages:
          </p>
          <div className="space-y-2">
            <div className="flex gap-2">
              <span className="font-semibold text-emerald-600 shrink-0">Stage 1 &mdash;</span>
              <span><span className="font-medium">Classification</span> (GPT-4.1 mini): Each message is classified as food or non-food. Photo messages are sent directly to the vision model.</span>
            </div>
            <div className="flex gap-2">
              <span className="font-semibold text-emerald-600 shrink-0">Stage 2 &mdash;</span>
              <span><span className="font-medium">Estimation</span> (GPT-4.1 with vision): For food messages, the model identifies the dish, estimates portion sizes using visual cues (plate size, utensils), and calculates calories and macronutrients (protein, carbs, fat).</span>
            </div>
          </div>
          <p>
            Results are cached so re-imports skip already processed messages. You can manually correct any estimate from the dashboard.
          </p>
          <div className="bg-gray-50 rounded-lg p-3 text-xs text-gray-500 space-y-1">
            <p><span className="font-medium text-gray-600">Models:</span> GPT-4.1 mini (text classification), GPT-4.1 (vision &amp; calorie estimation)</p>
            <p><span className="font-medium text-gray-600">Processing:</span> ~10 messages/sec (parallel), ~2-3 min for 1,500 messages</p>
            <p><span className="font-medium text-gray-600">Accuracy:</span> Estimates use realistic portion sizes with visual reference calibration. Designed to slightly overestimate rather than underestimate.</p>
          </div>
        </div>
      )}
    </div>
  );
}

export default function ImportPage() {
  const navigate = useNavigate();
  const [tab, setTab] = useState<'drive' | 'upload'>('drive');
  const [url, setUrl] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [timezone, setTimezone] = useState('Europe/Belgrade');
  const [threshold] = useState(0.6);
  const [forceRedo, setForceRedo] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [datasetId, setDatasetId] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  // Restore active job from localStorage on mount
  useEffect(() => {
    const saved = getActiveJob();
    if (saved) {
      setJobId(saved.jobId);
      setDatasetId(saved.datasetId);
    }
  }, []);

  const job = useJobSSE(jobId);

  // Clear active job from localStorage when completed/failed
  useEffect(() => {
    if (job?.status === 'completed' || job?.status === 'failed') {
      clearActiveJob();
    }
  }, [job?.status]);

  const myIds = getMyDatasetIds();

  const { data: allDatasets, refetch: refetchDatasets } = useQuery({
    queryKey: ['datasets'],
    queryFn: listDatasets,
  });

  const datasets = allDatasets?.filter(ds => myIds.includes(ds.id));

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
      addMyDatasetId(res.dataset_id);
      setDatasetId(res.dataset_id);
      setJobId(res.job_id);
      setActiveJob(res.job_id, res.dataset_id);
    } catch (e) {
      setError(String(e));
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = useCallback(async (id: string) => {
    await deleteDataset(id);
    removeMyDatasetId(id);
    // If deleting the dataset with the active job, clear it
    if (datasetId === id) {
      setJobId(null);
      setDatasetId(null);
      clearActiveJob();
    }
    refetchDatasets();
  }, [refetchDatasets, datasetId]);

  const handleResumeProgress = (dsId: string, jId: string) => {
    setDatasetId(dsId);
    setJobId(jId);
    setActiveJob(jId, dsId);
  };

  // Navigate to dashboard when job completes
  if (job?.status === 'completed' && datasetId) {
    setTimeout(() => navigate(`/dashboard?ds=${datasetId}`), 1500);
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold">CaloriSee</h1>
        <p className="text-gray-500 mt-1">AI-powered calorie tracking from your WhatsApp food chat. Export your chat, paste the link, and get a full nutrition dashboard.</p>
      </div>

      <ExportGuide />
      <HowItWorks />

      {!jobId && (
        <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-5">
          <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
            <button onClick={() => setTab('drive')}
              className={`flex-1 flex items-center justify-center gap-1.5 py-2 rounded-md text-sm font-medium transition-colors ${tab === 'drive' ? 'bg-white shadow-sm' : 'text-gray-500'}`}>
              <LinkIcon size={16} /> Google Drive Link
            </button>
            <button onClick={() => setTab('upload')}
              className={`flex-1 flex items-center justify-center gap-1.5 py-2 rounded-md text-sm font-medium transition-colors ${tab === 'upload' ? 'bg-white shadow-sm' : 'text-gray-500'}`}>
              <Upload size={16} /> File Upload
            </button>
          </div>

          {tab === 'drive' ? (
            <div>
              <label className="block text-sm font-medium mb-1">Google Drive share link</label>
              <input type="url" value={url} onChange={e => setUrl(e.target.value)}
                placeholder="https://drive.google.com/file/d/..."
                className="w-full border rounded-lg px-3 py-2 text-sm" />
            </div>
          ) : (
            <div>
              <label className="block text-sm font-medium mb-1">Archive file (.zip, .rar, .7z)</label>
              <input type="file" accept=".zip,.rar,.7z"
                onChange={e => setFile(e.target.files?.[0] || null)}
                className="w-full text-sm border rounded-lg px-3 py-2" />
            </div>
          )}

          <div>
            <label className="block text-sm font-medium mb-1">Timezone</label>
            <input type="text" value={timezone} onChange={e => setTimezone(e.target.value)}
              className="w-full border rounded-lg px-3 py-2 text-sm" />
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
          {job.status === 'failed' && (
            <button
              onClick={() => { setJobId(null); setDatasetId(null); clearActiveJob(); }}
              className="mt-3 text-sm text-emerald-600 underline"
            >
              Try again
            </button>
          )}
        </div>
      )}

      {datasets && datasets.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold mb-3">Previous Imports</h2>
          <div className="space-y-2">
            {datasets.map(ds => {
              const isProcessing = ds.status === 'processing' || ds.status === 'pending';
              const isCurrentJob = datasetId === ds.id && jobId;
              return (
                <div key={ds.id} className="bg-white rounded-lg border border-gray-200 px-4 py-3 flex items-center justify-between">
                  <button
                    onClick={() => {
                      if (isProcessing && ds.latest_job_id && !isCurrentJob) {
                        handleResumeProgress(ds.id, ds.latest_job_id);
                      } else if (!isProcessing) {
                        navigate(`/dashboard?ds=${ds.id}`);
                      }
                    }}
                    className="text-left flex-1"
                  >
                    <p className="text-sm font-medium">{ds.name}</p>
                    <p className="text-xs text-gray-400">
                      {isProcessing ? (
                        <span className="text-amber-600 font-medium">Processing...</span>
                      ) : (
                        <>{ds.status} &middot; {ds.date_range_start} to {ds.date_range_end}</>
                      )}
                    </p>
                  </button>
                  <button onClick={() => handleDelete(ds.id)} className="p-1.5 text-gray-400 hover:text-red-500">
                    <Trash2 size={16} />
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
