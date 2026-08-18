// Mirrors backend/app/main.py's Pydantic response models.

export type Role = "ADMIN" | "SuperAdmin";

export interface LoginResponse {
  access_token: string;
  token_type: string;
  username: string;
  role: Role;
}

export interface CaptchaResponse {
  captcha_id: string;
  image_base64: string;
}

export interface RetrievedChunk {
  source: string;
  chunk: number;
  text: string;
}

export interface QueryResponse {
  answer: string;
  sources: string[];
  chunks: RetrievedChunk[];
}

export interface TokenUsageStatus {
  used: number;
  limit: number;
  remaining: number;
}

export interface PromptVersion {
  key: string;
  label: string;
  mode: string;
  description: string;
}

export interface SystemInfo {
  llm_model: string;
  embed_model: string;
  llm_num_predict: number;
  chunk_size: number;
  chunk_overlap: number;
  top_k: number;
  default_prompt_version: string;
  yara_enabled: boolean;
  jwt_expiry_minutes: number;
  login_max_attempts: number;
  login_lockout_seconds: number;
  document_count: number;
  max_upload_size_mb: number;
  quarantined_count: number;
  daily_token_limit: number;
}

export interface LoginAttempt {
  username: string;
  failures: number;
  locked: boolean;
  remaining_seconds: number;
}

export interface QuarantineFile {
  id: string;
  original_filename: string;
  reason: string;
  uploader: string;
  size_bytes: number;
  sha256: string;
  timestamp: string;
}

export interface QuarantineExplanation {
  confidence: "high" | "medium" | "low";
  explanation: string;
}

export interface UserAccount {
  username: string;
  role: Role;
}

export interface UploadResponse {
  filename: string;
  chunks_added: number;
}

export interface SecurityDigestResponse {
  digest: string;
}
