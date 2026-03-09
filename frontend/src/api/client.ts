const BASE = '/api';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init);
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status}: ${text}`);
  }
  return res.json();
}

// Datasets
export interface DatasetListItem {
  id: string;
  name: string;
  status: string;
  source_type: string;
  created_at: string | null;
  date_range_start: string | null;
  date_range_end: string | null;
}

export interface ImportResponse {
  dataset_id: string;
  job_id: string;
}

export const listDatasets = () => request<DatasetListItem[]>('/datasets');

export const importDrive = (gdrive_url: string, timezone: string, threshold: number, force_redo: boolean) =>
  request<ImportResponse>('/datasets/import/drive', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ gdrive_url, timezone, threshold, force_redo }),
  });

export const importUpload = (file: File, timezone: string, threshold: number, force_redo: boolean) => {
  const form = new FormData();
  form.append('file', file);
  form.append('timezone', timezone);
  form.append('threshold', String(threshold));
  form.append('force_redo', String(force_redo));
  return request<ImportResponse>('/datasets/import/upload', { method: 'POST', body: form });
};

export const deleteDataset = (id: string) =>
  request<{ ok: boolean }>(`/datasets/${id}`, { method: 'DELETE' });

// Jobs
export interface JobStatus {
  id: string;
  dataset_id: string;
  status: string;
  current_step: string;
  percent: number;
  message: string;
  error: string | null;
}

export const getJobStatus = (id: string) => request<JobStatus>(`/jobs/${id}`);

// Dashboard
export interface KpiSummary {
  avg_calories_7d: number;
  avg_calories_30d: number;
  days_logged_30d: number;
  avg_protein_g: number;
  avg_carbs_g: number;
  avg_fat_g: number;
  total_messages: number;
  total_food_messages: number;
  date_range_start: string | null;
  date_range_end: string | null;
}

export interface DailyPoint {
  date: string;
  calories: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  meal_count: number;
  uncertainty_pct: number;
}

export interface TopItem {
  name: string;
  count: number;
  total_calories: number;
}

export const getDashboardSummary = (dsId: string) =>
  request<KpiSummary>(`/datasets/${dsId}/dashboard/summary`);

export const getDailyTimeseries = (dsId: string) =>
  request<DailyPoint[]>(`/datasets/${dsId}/dashboard/daily`);

export const getTopItems = (dsId: string) =>
  request<TopItem[]>(`/datasets/${dsId}/dashboard/top_items`);

// Messages
export interface DaySummary {
  date: string;
  total_messages: number;
  food_messages: number;
  total_calories: number;
}

export interface MessageSummary {
  id: string;
  msg_hash: string;
  timestamp: string;
  sender: string;
  text: string;
  has_media: boolean;
  media_urls: string[];
  is_food: boolean;
  food_confidence: number;
  food_context: string;
  meal_name: string | null;
  visual_description: string | null;
  total_calories: number | null;
  protein_g: number | null;
  carbs_g: number | null;
  fat_g: number | null;
  uncertainty_level: string | null;
  excluded: boolean;
  has_override: boolean;
}

export interface DayDetail {
  date: string;
  total_calories: number;
  total_protein_g: number;
  total_carbs_g: number;
  total_fat_g: number;
  meal_count: number;
  messages: MessageSummary[];
}

export interface MessageDetail extends MessageSummary {
  raw_line: string;
  classification: Record<string, unknown> | null;
  estimation: Record<string, unknown> | null;
  overrides: Record<string, unknown> | null;
}

export interface MessageOverride {
  excluded?: boolean;
  is_food_override?: boolean;
  corrected_total_calories?: number;
  corrected_total_protein_g?: number;
  corrected_total_carbs_g?: number;
  corrected_total_fat_g?: number;
  notes?: string;
}

export const listDays = (dsId: string) =>
  request<DaySummary[]>(`/datasets/${dsId}/messages/days`);

export const getDayDetail = (dsId: string, day: string) =>
  request<DayDetail>(`/datasets/${dsId}/messages/day/${day}`);

export const getMessageDetail = (dsId: string, msgId: string) =>
  request<MessageDetail>(`/datasets/${dsId}/messages/${msgId}`);

export const overrideMessage = (dsId: string, msgId: string, body: MessageOverride) =>
  request<{ ok: boolean }>(`/datasets/${dsId}/messages/${msgId}/override`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
