export interface ProjectRecord {
  id: string;
  customer_phone?: string | null;
  vapi_call_id?: string | null;
  transcript: any[];
  website_brief: string | null;
  status: string;
  deployment_url?: string | null;
  created_at: string;
  completed_at?: string | null;
}

// Global in-memory fallback so projects work seamlessly even before Supabase SQL migration is run
declare global {
  var __call2code_projects: Map<string, ProjectRecord> | undefined;
}

export const localProjects: Map<string, ProjectRecord> =
  globalThis.__call2code_projects ?? (globalThis.__call2code_projects = new Map<string, ProjectRecord>());
