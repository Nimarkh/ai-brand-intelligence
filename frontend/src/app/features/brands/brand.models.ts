import { formatDisplayDate } from '../../shared/format';

export interface Brand {
  id: string;
  name: string;
  website_url: string | null;
  industry: string | null;
  country: string | null;
  target_market: string | null;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface BrandListResponse {
  items: Brand[];
  total: number;
}

export interface BrandWritePayload {
  name: string;
  website_url: string;
  industry: string;
  country: string;
  target_market: string;
  description: string | null;
}

export function formatBrandDate(value: string): string {
  return formatDisplayDate(value) ?? '';
}

export function safeWebsiteHref(url: string | null): string | null {
  if (!url) {
    return null;
  }
  try {
    const parsed = new URL(url);
    if (parsed.protocol === 'http:' || parsed.protocol === 'https:') {
      return parsed.href;
    }
  } catch {
    return null;
  }
  return null;
}
