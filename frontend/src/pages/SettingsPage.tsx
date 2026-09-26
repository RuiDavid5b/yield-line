// pages/SettingsPage.tsx
import { useState } from "react";
import { api } from "../api/client";
import type { LLMProvider } from "../api/client";
import { useAuth } from "../auth/AuthContext";

const PROVIDERS: { value: LLMProvider; label: string }[] = [
  { value: "anthropic", label: "Anthropic (Claude)" },
  { value: "openai", label: "OpenAI" },
  { value: "gemini", label: "Google (Gemini)" },
];

const DEFAULT_MODELS: Record<LLMProvider, string> = {
  anthropic: "claude-sonnet-4-6",
  openai: "gpt-5",
  gemini: "gemini-3.5-flash-lite",
};

const PROVIDER_LABELS: Record<LLMProvider, string> = Object.fromEntries(
  PROVIDERS.map((p) => [p.value, p.label]),
) as Record<LLMProvider, string>;

export default function SettingsPage() {
  const { apiKeyStatus, refreshApiKeyStatus } = useAuth();

  const [provider, setProvider] = useState<LLMProvider>(
    (apiKeyStatus?.provider as LLMProvider) || "anthropic",
  );
  const [model, setModel] = useState(
    apiKeyStatus?.model || DEFAULT_MODELS["anthropic"],
  );
  const [apiKey, setApiKey] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  function handleProviderChange(newProvider: LLMProvider) {
    setProvider(newProvider);
    setModel(DEFAULT_MODELS[newProvider]);
  }

  async function handleSave() {
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      await api.setApiKey(provider, model, apiKey);
      await refreshApiKeyStatus();
      setApiKey("");
      setMessage("API key saved.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save key.");
    } finally {
      setSaving(false);
    }
  }

  async function handleRemove() {
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      await api.deleteApiKey();
      await refreshApiKeyStatus();
      setMessage("API key removed.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to remove key.");
    } finally {
      setSaving(false);
    }
  }

  if (apiKeyStatus === null) {
    return (
      <div className="settings-page">
        <p className="settings-loading">Loading...</p>
      </div>
    );
  }

  return (
    <div className="settings-page">
      <h1>Settings</h1>

      <section className="settings-section">
        <div className="settings-section-heading">
          <h2>Chat API key</h2>
          <p className="settings-section-desc">
            Set your own API key to use the chat assistant
          </p>
        </div>

        {apiKeyStatus.has_key && apiKeyStatus.provider && (
          <p className="settings-current">
            Currently using <strong>{PROVIDER_LABELS[apiKeyStatus.provider as LLMProvider]}</strong>
            {apiKeyStatus.model && <> · {apiKeyStatus.model}</>}
          </p>
        )}

        <div className="settings-row">
          <label className="settings-field">
            <span className="settings-label">Provider</span>
            <select value={provider} onChange={(e) => handleProviderChange(e.target.value as LLMProvider)}>
              {PROVIDERS.map((p) => (
                <option key={p.value} value={p.value}>
                  {p.label}
                </option>
              ))}
            </select>
          </label>

          <label className="settings-field">
            <span className="settings-label">Model</span>
            <input
              type="text"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder={DEFAULT_MODELS[provider]}
            />
          </label>

          <label className="settings-field settings-field-wide">
            <span className="settings-label">API key</span>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder={apiKeyStatus.has_key ? "Enter a new key to replace the current one" : "sk-..."}
            />
          </label>
        </div>

        {error && <p className="auth-error">{error}</p>}
        {message && <p className="auth-success">{message}</p>}

        <div className="settings-actions">
          <button className="auth-submit settings-save" onClick={handleSave} disabled={saving || !apiKey.trim() || !model.trim()}>
            Save
          </button>
          {apiKeyStatus.has_key && (
            <button className="settings-remove" onClick={handleRemove} disabled={saving}>
              Remove key
            </button>
          )}
        </div>
      </section>
    </div>
  );
}
