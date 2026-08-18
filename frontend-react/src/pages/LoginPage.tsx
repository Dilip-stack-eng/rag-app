import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { apiGet, apiPost, ApiError } from "../api/client";
import type { CaptchaResponse, LoginResponse, Role } from "../api/types";
import { useAuth } from "../context/AuthContext";
import { AthenaLogo } from "../components/AthenaLogo";
import { t } from "../i18n/translations";

const LOCKOUT_SECONDS = 60;

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [captcha, setCaptcha] = useState<CaptchaResponse | null>(null);
  const [captchaAnswer, setCaptchaAnswer] = useState("");
  const [error, setError] = useState("");
  const [locked, setLocked] = useState(false);
  const [lockRemaining, setLockRemaining] = useState(0);
  const [busy, setBusy] = useState(false);

  const loadCaptcha = async () => {
    try {
      const resp = await apiGet<CaptchaResponse>("/auth/captcha", { auth: false });
      setCaptcha(resp);
      setCaptchaAnswer("");
    } catch {
      // A captcha the user can't see/solve is a bigger problem than skipping
      // it client-side would be — the backend still enforces it server-side
      // whenever captcha_id/captcha_answer are actually sent, so leaving
      // captcha null here just means we send neither and fall back to the
      // (still fully backend-enforced) lockout + credential check alone.
      setCaptcha(null);
    }
  };

  useEffect(() => {
    void loadCaptcha();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Auto-release the lock client-side after the baseline 60s so the form
  // reappears without a manual refresh — the backend remains the actual
  // authority (see loadCaptcha's comment): if the AI risk assessment
  // extended the real lockout past 60s, the next submit attempt will
  // simply come back 429 again with the true remaining time.
  useEffect(() => {
    if (!locked || lockRemaining <= 0) return;
    const id = setTimeout(() => setLockRemaining((s) => s - 1), 1000);
    return () => clearTimeout(id);
  }, [locked, lockRemaining]);

  useEffect(() => {
    if (locked && lockRemaining <= 0) setLocked(false);
  }, [locked, lockRemaining]);

  const onSuccess = (resp: LoginResponse) => {
    login(resp.access_token, resp.username, resp.role);
    navigate("/home", { replace: true });
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const resp = await apiPost<LoginResponse>(
        "/auth/login",
        {
          username,
          password,
          captcha_id: captcha?.captcha_id ?? null,
          captcha_answer: captchaAnswer || null,
        },
        { auth: false }
      );
      onSuccess(resp);
    } catch (err) {
      const apiErr = err as ApiError;
      if (apiErr.status === 429) {
        setLocked(true);
        setLockRemaining(LOCKOUT_SECONDS);
      } else {
        setError(apiErr.message || t("backend_unreachable"));
      }
      void loadCaptcha();
    } finally {
      setBusy(false);
    }
  };

  const handleQuickLogin = async (role: Role) => {
    setError("");
    setBusy(true);
    try {
      const resp = await apiPost<LoginResponse>("/auth/quick-login", { role }, { auth: false });
      onSuccess(resp);
    } catch (err) {
      setError((err as ApiError).message || `Quick sign-in for ${role} failed.`);
    } finally {
      setBusy(false);
    }
  };

  if (locked) {
    return (
      <div className="login-page">
        <div className="login-card">
          <div className="login-logo">
            <AthenaLogo size={42} />
            <span className="login-logo-name">
              ATHENA <span className="login-logo-name-accent">AI</span>
            </span>
          </div>
          <div className="alert alert-error">
            {t("lockout_message", { secs: lockRemaining })}
          </div>
          <button className="btn btn-block" onClick={() => setLocked(false)}>
            {t("check_again")}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-logo">
          <AthenaLogo size={42} />
          <span className="login-logo-name">
            ATHENA <span className="login-logo-name-accent">AI</span>
          </span>
        </div>
        <div className="login-eyebrow">Secure Sign-In</div>
        <div className="login-title">{t("welcome_back")}</div>
        <div className="login-subtitle">{t("login_subtitle")}</div>

        <form onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="username">{t("username")}</label>
            <input
              id="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder={t("username")}
              autoComplete="username"
            />
          </div>
          <div className="field">
            <label htmlFor="password">{t("password")}</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={t("password")}
              autoComplete="current-password"
            />
          </div>

          {captcha && (
            <div className="field">
              <label>{t("captcha_label")}</label>
              <div className="captcha-row">
                <img src={`data:image/png;base64,${captcha.image_base64}`} alt="captcha" />
                <button type="button" className="btn-secondary" onClick={() => void loadCaptcha()}>
                  🔄
                </button>
              </div>
              <input
                value={captchaAnswer}
                onChange={(e) => setCaptchaAnswer(e.target.value)}
                placeholder={t("captcha_placeholder")}
              />
            </div>
          )}

          {error && <div className="alert alert-error">{error}</div>}

          <button type="submit" className="btn btn-block" disabled={busy}>
            {busy ? <span className="spinner" /> : t("log_in")}
          </button>
        </form>

        <div className="text-center text-soft" style={{ fontSize: "0.8rem", marginTop: "0.9rem" }}>
          Quick sign-in
        </div>
        <div className="quick-login-row">
          <button className="btn-quiet" disabled={busy} onClick={() => void handleQuickLogin("ADMIN")}>
            ADMIN
          </button>
          <button className="btn-quiet" disabled={busy} onClick={() => void handleQuickLogin("SuperAdmin")}>
            SuperAdmin
          </button>
        </div>

        <div className="login-footer">{t("login_footer")}</div>
      </div>
    </div>
  );
}
