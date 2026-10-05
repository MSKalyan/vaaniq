/**
 * Shared domain constants and types between the Next.js web app and any
 * client-side API contract. Kept decoupled from the Python backend schemas;
 * mirrors the values in apps/api/app/models.
 */

/** Lead lifecycle statuses. */
export const LEAD_STATUS = {
  NEW: "NEW",
  QUEUED: "QUEUED",
  CALLING: "CALLING",
  COMPLETED: "COMPLETED",
  FAILED: "FAILED",
  INTERESTED: "INTERESTED",
  NOT_INTERESTED: "NOT_INTERESTED",
  CALLBACK_REQUESTED: "CALLBACK_REQUESTED",
  DO_NOT_CALL: "DO_NOT_CALL",
} as const;
export type LeadStatus = (typeof LEAD_STATUS)[keyof typeof LEAD_STATUS];

/** Campaign lifecycle statuses. */
export const CAMPAIGN_STATUS = {
  DRAFT: "DRAFT",
  SCHEDULED: "SCHEDULED",
  RUNNING: "RUNNING",
  PAUSED: "PAUSED",
  COMPLETED: "COMPLETED",
  CANCELLED: "CANCELLED",
} as const;
export type CampaignStatus =
  (typeof CAMPAIGN_STATUS)[keyof typeof CAMPAIGN_STATUS];

/** Voice call state machine states. */
export const CALL_STATE = {
  INITIALIZING: "INITIALIZING",
  RINGING: "RINGING",
  CONNECTED: "CONNECTED",
  GREETING: "GREETING",
  LISTENING: "LISTENING",
  PROCESSING: "PROCESSING",
  SPEAKING: "SPEAKING",
  INTERRUPTED: "INTERRUPTED",
  ENDING: "ENDING",
  COMPLETED: "COMPLETED",
  FAILED: "FAILED",
} as const;
export type CallState = (typeof CALL_STATE)[keyof typeof CALL_STATE];

/** Transcript speaker roles. */
export const SPEAKER = {
  AI: "AI",
  CUSTOMER: "CUSTOMER",
  SYSTEM: "SYSTEM",
} as const;
export type Speaker = (typeof SPEAKER)[keyof typeof SPEAKER];

/** Indian languages supported by agents (Sarvam-supported set). */
export const SUPPORTED_LANGUAGES = [
  "auto",
  "en-IN",
  "hi-IN",
  "te-IN",
  "ta-IN",
  "kn-IN",
  "ml-IN",
  "mr-IN",
  "bn-IN",
  "gu-IN",
  "or-IN",
  "pa-IN",
  "ur-IN",
] as const;
export type SupportedLanguage = (typeof SUPPORTED_LANGUAGES)[number];

/** Agent personality presets. */
export const AGENT_PERSONALITIES = [
  "Professional",
  "Friendly",
  "Consultative",
  "Concise",
] as const;

/** Lead statuses that represent a successful, non-retryable outcome. */
export const TERMINAL_LEAD_STATUSES: readonly LeadStatus[] = [
  LEAD_STATUS.COMPLETED,
  LEAD_STATUS.INTERESTED,
  LEAD_STATUS.NOT_INTERESTED,
  LEAD_STATUS.CALLBACK_REQUESTED,
  LEAD_STATUS.DO_NOT_CALL,
];