import { useSearchParams } from 'react-router-dom';

const STORAGE_KEY = 'calorisee_my_datasets';

function getMyDatasetIds(): string[] {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
  } catch {
    return [];
  }
}

/**
 * Returns the active dataset ID: from ?ds= query param,
 * or the most recent one from this device's localStorage.
 */
export function useActiveDataset(): string | undefined {
  const [params] = useSearchParams();
  const fromUrl = params.get('ds');
  if (fromUrl) return fromUrl;
  const myIds = getMyDatasetIds();
  return myIds[0] || undefined;
}
