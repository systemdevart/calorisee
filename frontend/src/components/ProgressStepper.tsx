import type { JobStatus } from '../api/client';

const STEPS = ['download', 'extract', 'parse', 'classify', 'store', 'done'];

export default function ProgressStepper({ job }: { job: JobStatus }) {
  const currentIdx = STEPS.indexOf(job.current_step);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        {STEPS.map((step, i) => (
          <div key={step} className="flex items-center gap-2">
            <div
              className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-medium ${
                i < currentIdx
                  ? 'bg-emerald-500 text-white'
                  : i === currentIdx
                    ? 'bg-emerald-100 text-emerald-700 ring-2 ring-emerald-500'
                    : 'bg-gray-100 text-gray-400'
              }`}
            >
              {i < currentIdx ? '✓' : i + 1}
            </div>
            {i < STEPS.length - 1 && (
              <div className={`h-0.5 w-6 ${i < currentIdx ? 'bg-emerald-500' : 'bg-gray-200'}`} />
            )}
          </div>
        ))}
      </div>

      <div className="w-full bg-gray-200 rounded-full h-2">
        <div
          className="bg-emerald-500 h-2 rounded-full transition-all duration-500"
          style={{ width: `${job.percent}%` }}
        />
      </div>

      <p className="text-sm text-gray-600">{job.message}</p>

      {job.status === 'failed' && job.error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">
          {job.error}
        </div>
      )}
    </div>
  );
}
