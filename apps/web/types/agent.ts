export type AgentStatus = "DRAFT" | "ACTIVE" | "ARCHIVED";

export interface Agent {
  id: string;
  user_id: string;
  name: string;
  description?: string | null;
  system_prompt: string;
  language: string;
  voice?: string | null;
  greeting?: string | null;
  objectives: unknown[];
  max_call_duration: number;
  temperature: number;
  status: AgentStatus;
  created_at: string;
  updated_at: string;
}

export interface AgentCreate {
  name: string;
  description?: string | null;
  system_prompt?: string;
  language?: string;
  voice?: string | null;
  greeting?: string | null;
  objectives?: unknown[];
  max_call_duration?: number;
  temperature?: number;
  status?: AgentStatus;
}

export interface AgentVoice {
  id: string;
  provider: string;
  voice_name: string;
  language: string;
  voice_metadata: Record<string, unknown>;
}