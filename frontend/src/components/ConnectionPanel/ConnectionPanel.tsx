import React, { useState, useEffect } from "react";
import styles from "./ConnectionPanel.module.css";
import { Settings, Cable, Plus, Trash2, HelpCircle, Sparkles, Check, RefreshCw } from "lucide-react";
import { api, Connector, AppConfig } from "../../services/api";

interface ConnectionPanelProps {
  onSeedSuccess: () => void;
}

export const ConnectionPanel: React.FC<ConnectionPanelProps> = ({ onSeedSuccess }) => {
  // Global settings state
  const [appConfig, setAppConfig] = useState<AppConfig | null>(null);
  const [geminiKey, setGeminiKey] = useState("");
  const [ollamaHost, setOllamaHost] = useState("");
  const [isSavingConfig, setIsSavingConfig] = useState(false);
  const [configSaved, setConfigSaved] = useState(false);

  // Connectors list state
  const [connectors, setConnectors] = useState<Connector[]>([]);
  const [isLoadingConnectors, setIsLoadingConnectors] = useState(true);

  // New Connector form state
  const [platform, setPlatform] = useState("github");
  const [connectorName, setConnectorName] = useState("");
  const [syncInterval, setSyncInterval] = useState(15);
  const [authFields, setAuthFields] = useState<Record<string, string>>({});
  const [isSubmittingConnector, setIsSubmittingConnector] = useState(false);

  // Seeding sandbox state
  const [isSeeding, setIsSeeding] = useState(false);
  const [seedCompleted, setSeedCompleted] = useState(false);

  useEffect(() => {
    fetchConfig();
    fetchConnectors();
  }, []);

  const fetchConfig = async () => {
    try {
      const config = await api.getConfig();
      setAppConfig(config);
      setOllamaHost(config.ollama_host);
    } catch (err) {
      console.error("Failed to fetch config", err);
    }
  };

  const fetchConnectors = async () => {
    setIsLoadingConnectors(true);
    try {
      const data = await api.getConnectors();
      setConnectors(data);
    } catch (err) {
      console.error("Failed to fetch connectors", err);
    } finally {
      setIsLoadingConnectors(false);
    }
  };

  const handleSaveConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSavingConfig(true);
    try {
      const payload: { gemini_api_key?: string; ollama_host?: string } = {};
      if (geminiKey) payload.gemini_api_key = geminiKey;
      if (ollamaHost) payload.ollama_host = ollamaHost;
      
      const res = await api.updateConfig(payload);
      setAppConfig(res.config);
      setGeminiKey("");
      setConfigSaved(true);
      setTimeout(() => setConfigSaved(false), 3000);
    } catch (err) {
      console.error("Failed to save config", err);
    } finally {
      setIsSavingConfig(false);
    }
  };

  const handleCreateConnector = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmittingConnector(true);
    try {
      await api.createConnector({
        platform,
        name: connectorName || `${platform.toUpperCase()} Connector`,
        auth_config: authFields,
        sync_interval_mins: syncInterval
      });
      // Reset form
      setConnectorName("");
      setAuthFields({});
      fetchConnectors();
    } catch (err) {
      alert("Failed to create connection. Check configurations.");
      console.error(err);
    } finally {
      setIsSubmittingConnector(false);
    }
  };

  const handleDeleteConnector = async (id: number) => {
    if (!confirm("Are you sure you want to delete this connection?")) return;
    try {
      await api.deleteConnector(id);
      fetchConnectors();
    } catch (err) {
      console.error(err);
    }
  };

  const handleSeedSandbox = async () => {
    setIsSeeding(true);
    try {
      await api.seedMockData();
      setSeedCompleted(true);
      onSeedSuccess();
      setTimeout(() => setSeedCompleted(false), 3000);
    } catch (err: any) {
      alert(err.message || "Failed to seed demo database.");
    } finally {
      setIsSeeding(false);
    }
  };

  const handleAuthFieldChange = (key: string, value: string) => {
    setAuthFields(prev => ({ ...prev, [key]: value }));
  };

  return (
    <div className={styles.container}>
      {/* Seed Sandbox Card */}
      <div className={styles.sandboxCard}>
        <div className={styles.sandboxInfo}>
          <h3 className={styles.sandboxTitle}>
            <Sparkles size={20} /> Seed Demo Sandbox
          </h3>
          <p className={styles.sandboxText}>
            Want to test immediately? This will seed SQLite and LanceDB with mock, cross-referenced data 
            (GitHub PRs, Jira tasks, Slack messages, and Google specs) relating to a real JWT Auth Clock-Skew bug. 
            No credentials needed.
          </p>
        </div>
        <button 
          className={styles.button} 
          onClick={handleSeedSandbox}
          disabled={isSeeding}
        >
          {isSeeding ? (
            <>
              <RefreshCw size={16} className="spin" /> Seeding...
            </>
          ) : seedCompleted ? (
            <>
              <Check size={16} /> Sandbox Seeded!
            </>
          ) : (
            <>
              <Sparkles size={16} /> Seed Sandbox Data
            </>
          )}
        </button>
      </div>

      {/* Settings Panel */}
      <div className={styles.sectionCard}>
        <h3 className={styles.sectionTitle}>
          <Settings size={20} /> LLM Core Settings
        </h3>
        <form onSubmit={handleSaveConfig}>
          <div className={styles.formGroup}>
            <label className={styles.label}>Google Gemini API Key</label>
            <input 
              type="password" 
              className={styles.input} 
              placeholder={appConfig?.gemini_api_key_configured ? "•••••••••••••••• (Configured)" : "Enter Gemini Free Tier Key"}
              value={geminiKey}
              onChange={(e) => setGeminiKey(e.target.value)}
            />
            <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "4px", display: "block" }}>
              Leave blank to keep current key. Default Gemini 1.5 Flash provides high-speed context unifications.
            </span>
          </div>

          <div className={styles.formGroup}>
            <label className={styles.label}>Ollama Host Endpoint</label>
            <input 
              type="text" 
              className={styles.input} 
              value={ollamaHost}
              onChange={(e) => setOllamaHost(e.target.value)}
            />
          </div>

          <button type="submit" className={styles.button} disabled={isSavingConfig}>
            {isSavingConfig ? "Saving..." : configSaved ? "Settings Saved!" : "Save Configuration"}
          </button>
        </form>
      </div>

      {/* Active Connectors Panel */}
      <div className={styles.sectionCard}>
        <h3 className={styles.sectionTitle}>
          <Cable size={20} /> Active Connections
        </h3>
        {isLoadingConnectors ? (
          <div>Loading connections...</div>
        ) : connectors.length === 0 ? (
          <div style={{ color: "var(--text-muted)", fontSize: "0.9rem" }}>
            No connections established yet. Seed the sandbox or create one below.
          </div>
        ) : (
          <div className={styles.connectorList}>
            {connectors.map((c) => (
              <div key={c.id} className={styles.connectorItem}>
                <div className={styles.connectorInfo}>
                  <div className={styles.connectorMeta}>
                    <span className={styles.connectorName}>{c.name}</span>
                    <span className={styles.connectorSync}>
                      Platform: {c.platform.toUpperCase()} | Sync: {c.sync_interval_mins}m
                    </span>
                  </div>
                </div>
                <button 
                  className={styles.deleteBtn} 
                  onClick={() => handleDeleteConnector(c.id)}
                  title="Remove Connection"
                >
                  <Trash2 size={16} />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Add Connection Panel */}
      <div className={`${styles.sectionCard} ${styles.sandboxCard}`} style={{ gridColumn: "1 / -1", borderStyle: "solid", borderWidth: "1px", borderColor: "var(--border-color)", background: "var(--bg-secondary)" }}>
        <div style={{ width: "100%" }}>
          <h3 className={styles.sectionTitle}>
            <Plus size={20} /> Setup New Platform Connection
          </h3>
          <form onSubmit={handleCreateConnector} style={{ display: "grid", gridTemplateColumns: "1fr 1.5fr", gap: "2rem" }}>
            <div>
              <div className={styles.formGroup}>
                <label className={styles.label}>Select Target Platform</label>
                <select 
                  className={styles.input} 
                  value={platform} 
                  onChange={(e) => {
                    setPlatform(e.target.value);
                    setAuthFields({});
                  }}
                >
                  <option value="github">GitHub REST API</option>
                  <option value="slack">Slack Channels API</option>
                  <option value="jira">Jira Cloud REST API</option>
                  <option value="google">Google Workspace (Gmail / Docs)</option>
                </select>
              </div>

              <div className={styles.formGroup}>
                <label className={styles.label}>Connection Label (Alias)</label>
                <input 
                  type="text" 
                  className={styles.input} 
                  placeholder="e.g. Work GitHub" 
                  value={connectorName}
                  onChange={(e) => setConnectorName(e.target.value)}
                  required
                />
              </div>

              <div className={styles.formGroup}>
                <label className={styles.label}>Polling Period (Minutes)</label>
                <input 
                  type="number" 
                  className={styles.input} 
                  value={syncInterval}
                  onChange={(e) => setSyncInterval(Number(e.target.value))}
                  required
                />
              </div>

              <button type="submit" className={styles.button} disabled={isSubmittingConnector}>
                {isSubmittingConnector ? "Connecting..." : "Add Integration"}
              </button>
            </div>

            {/* Dynamic Credentials Inputs */}
            <div>
              <h4 style={{ fontSize: "0.9rem", fontWeight: 600, marginBottom: "1rem", color: "var(--text-secondary)" }}>
                Integration Credentials
              </h4>

              {platform === "github" && (
                <>
                  <div className={styles.formGroup}>
                    <label className={styles.label}>Repository Target (owner/repo)</label>
                    <input 
                      type="text" 
                      className={styles.input} 
                      placeholder="e.g. google/jax"
                      value={authFields.repo || ""}
                      onChange={(e) => handleAuthFieldChange("repo", e.target.value)}
                      required
                    />
                  </div>
                  <div className={styles.formGroup}>
                    <label className={styles.label}>Personal Access Token (PAT)</label>
                    <input 
                      type="password" 
                      className={styles.input} 
                      placeholder="ghp_••••••••••••"
                      value={authFields.token || ""}
                      onChange={(e) => handleAuthFieldChange("token", e.target.value)}
                      required
                    />
                  </div>
                </>
              )}

              {platform === "slack" && (
                <>
                  <div className={styles.formGroup}>
                    <label className={styles.label}>Bot User OAuth Token</label>
                    <input 
                      type="password" 
                      className={styles.input} 
                      placeholder="xoxb-••••••••••••"
                      value={authFields.token || ""}
                      onChange={(e) => handleAuthFieldChange("token", e.target.value)}
                      required
                    />
                  </div>
                  <div className={styles.formGroup}>
                    <label className={styles.label}>Channel ID Targets (comma-separated)</label>
                    <input 
                      type="text" 
                      className={styles.input} 
                      placeholder="e.g. C123456,C789012"
                      value={authFields.channels || ""}
                      onChange={(e) => handleAuthFieldChange("channels", e.target.value)}
                      required
                    />
                  </div>
                </>
              )}

              {platform === "jira" && (
                <>
                  <div className={styles.formGroup}>
                    <label className={styles.label}>Jira Cloud Domain</label>
                    <input 
                      type="text" 
                      className={styles.input} 
                      placeholder="e.g. orgname.atlassian.net"
                      value={authFields.domain || ""}
                      onChange={(e) => handleAuthFieldChange("domain", e.target.value)}
                      required
                    />
                  </div>
                  <div className={styles.formGroup}>
                    <label className={styles.label}>User Login Email</label>
                    <input 
                      type="email" 
                      className={styles.input} 
                      placeholder="e.g. admin@company.com"
                      value={authFields.email || ""}
                      onChange={(e) => handleAuthFieldChange("email", e.target.value)}
                      required
                    />
                  </div>
                  <div className={styles.formGroup}>
                    <label className={styles.label}>API Token (Jira User Token)</label>
                    <input 
                      type="password" 
                      className={styles.input} 
                      placeholder="Enter API token"
                      value={authFields.api_token || ""}
                      onChange={(e) => handleAuthFieldChange("api_token", e.target.value)}
                      required
                    />
                  </div>
                </>
              )}

              {platform === "google" && (
                <div className={styles.googleInstructions}>
                  <p><strong>Google OAuth Loopback Setup:</strong></p>
                  <ol>
                    <li>Go to the Google Cloud Console and create a project.</li>
                    <li>Configure the OAuth consent screen with <strong>Gmail readonly</strong> and <strong>Drive readonly</strong> scopes.</li>
                    <li>Create OAuth 2.0 Client Credentials (type: <i>Desktop App</i>).</li>
                    <li>Download the secret configuration JSON, rename it to <strong>credentials.json</strong>, and place it inside the backend's data directory: <br/> <code>backend/data/credentials.json</code></li>
                  </ol>
                  <p style={{ marginTop: "1rem" }}>
                    Once credentials.json is placed on disk, the system will automatically prompt you to log in via your browser when performing the first Google API sync.
                  </p>
                </div>
              )}
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};
export default ConnectionPanel;
