// Ported from the Streamlit frontend's TRANSLATIONS dict. English is fully
// populated here; the other 11 languages that dict supported (es, fr, de,
// hi, ta, te, kn, ml, zh, ja, ar) are a known follow-up — not ported yet,
// so the language switcher isn't wired up in this React version until
// they are. t() falls back to the key itself if ever missing, so nothing
// breaks in the meantime.

export const translations = {
  welcome_back: "Welcome back.",
  login_subtitle: "Sign in to Athena to chat with your documents.",
  username: "Username",
  password: "Password",
  log_in: "Log in",
  invalid_login: "Invalid username or password. {remaining} attempt(s) remaining.",
  lockout_message:
    "🔒 Locked after 3 failed attempts. Auto-releases in ~{secs}s, or SuperAdmin can release it now below.",
  check_again: "Check again",
  superadmin_release: "SuperAdmin release",
  superadmin_username: "SuperAdmin username",
  superadmin_password: "SuperAdmin password",
  release_lock_signin: "Release lock & sign in",
  invalid_superadmin: "Invalid SuperAdmin credentials.",
  captcha_label: "Enter the code above",
  captcha_placeholder: "Code",
  captcha_mismatch: "Code didn't match. Please try again.",
  login_footer:
    "By continuing, you agree to Athena's Consumer Terms and acknowledge their Privacy Policy.",
  greeting: "How can I help you today?",
  subgreeting: "Ask a question about your uploaded documents.",
  suggestion_1: "Summarize the key points",
  suggestion_2: "What are the main risks mentioned?",
  suggestion_3: "List any deadlines or dates",
  new_chat: "＋  New chat",
  tab_home: "Home",
  tab_query_trace: "Query Trace",
  documents_label: "Documents",
  no_documents: "No documents ingested yet.",
  backend_unreachable: "Backend not reachable. Is it running?",
  clear_all_docs: "🗑️  Clear all documents",
  role_local: "Local",
  log_out: "Log out",
  sources_label: "Sources:",
  context_retrieved: 'Context retrieved for: "{q}"',
  chunk_label: "chunk {n}",
  code_tab_hint: "Ask a question on the Home tab first — retrieved chunks show up here.",
  upload_label: "Upload a .txt, .pdf, or .docx file",
  ingest_btn: "Ingest",
  ingesting: "Ingesting...",
  added_chunks: "Added {n} chunks from {filename}",
  ingested_files_label: "Ingested files",
} as const;

export type TranslationKey = keyof typeof translations;

export function t(key: TranslationKey, vars?: Record<string, string | number>): string {
  const template = translations[key] ?? key;
  if (!vars) return template;
  return Object.entries(vars).reduce(
    (acc, [k, v]) => acc.replaceAll(`{${k}}`, String(v)),
    template as string
  );
}
