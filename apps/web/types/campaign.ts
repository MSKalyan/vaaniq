export type CampaignStatus =
  | "DRAFT"
  | "SCHEDULED"
  | "RUNNING"
  | "PAUSED"
  | "COMPLETED"
  | "CANCELLED";

export interface Campaign {
  id: string;
  user_id: string;
  name: string;
  agent_id: string;
  status: CampaignStatus | string;
  start_time?: string | null;
  end_time?: string | null;
  max_concurrent_calls: number;
  retry_attempts: number;
  retry_delay_minutes: number;
  lead_count: number;
  created_at: string;
  updated_at?: string;
}

export interface CampaignCreate {
  name: string;
  agent_id: string;
  lead_ids: string[];
  max_concurrent_calls?: number;
  retry_attempts?: number;
  retry_delay_minutes?: number;
  start_time?: string | null;
  end_time?: string | null;
}
