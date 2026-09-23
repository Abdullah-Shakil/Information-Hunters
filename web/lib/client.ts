export type Lead = {
  id: string;
  company_number: string;
  name: string;
  location: string;
  address: string;
  postcode: string;
  category: string;
  sic_codes: string[];
  sic_labels: string[];
  phone: string | null;
  mobile: string | null;
  email: string | null;
  website: string | null;
  has_website: boolean;
  incorporation_date: string | null;
  company_status: string;
  trading_status: string;
  priority_score: number;
  priority_band: string;
  priority_reasons: string[];
  sources: { provider: string; reference?: string }[];
  verification_notes: string;
  do_not_contact: boolean;
  synthetic: boolean;
  job_id: string | null;
};

export type Job = {
  id: string;
  name: string;
  categories: string[];
  regions: string[];
  status: string;
  stage: string;
  progress: number;
  limit_per_search: number;
  discovery_provider: string;
  verification_provider: string;
  contact_fetcher: string;
  discovered_count: number;
  qualified_count: number;
  rejected_count: number;
  error: string | null;
  worker_id: string | null;
  created_at: string | null;
};

export type Catalogue = {
  categories: { id: string; label: string; sic: string; sic_label: string }[];
  regions: { id: string; label: string; nation: string; dial: string }[];
};

async function parseError(response: Response) {
  try {
    const body = await response.json();
    if (typeof body.detail === "string") return body.detail;
    return JSON.stringify(body.detail || body);
  } catch {
    return response.statusText;
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/backend/${path}`, {
    ...init,
    headers: {
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...(init?.headers || {}),
    },
  });
  if (response.status === 401) {
    window.location.href = "/login";
    throw new Error("Sign in required");
  }
  if (!response.ok) throw new Error(await parseError(response));
  return response.json() as Promise<T>;
}

export async function downloadLeads(query: string) {
  const response = await fetch(`/api/backend/leads/export${query}`);
  if (!response.ok) throw new Error(await parseError(response));
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "information-hunters-leads.csv";
  link.click();
  URL.revokeObjectURL(url);
}

export function titleCase(value: string) {
  return value.replace(/[_-]/g, " ");
}
