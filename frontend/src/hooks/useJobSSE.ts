import { useEffect, useRef, useState } from 'react';
import type { JobStatus } from '../api/client';
import { getJobStatus } from '../api/client';

export function useJobSSE(jobId: string | null) {
  const [job, setJob] = useState<JobStatus | null>(null);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!jobId) return;

    const es = new EventSource(`/api/jobs/${jobId}/events`);
    esRef.current = es;

    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data) as JobStatus;
        if ('error' in data && !data.status) return; // ignore error-only frames
        setJob(data);
        if (data.status === 'completed' || data.status === 'failed') {
          es.close();
        }
      } catch { /* ignore parse errors */ }
    };

    es.onerror = () => {
      es.close();
      // Fallback: try REST endpoint to get final status
      getJobStatus(jobId)
        .then((data) => setJob(data))
        .catch(() => { /* job truly gone */ });
    };

    return () => {
      es.close();
    };
  }, [jobId]);

  return job;
}
