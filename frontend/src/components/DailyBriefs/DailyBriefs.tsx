import React, { useState } from "react";
import styles from "./DailyBriefs.module.css";
import { 
  RotateCw, 
  Clock,
  AlertCircle,
  HelpCircle,
  Activity,
  Zap,
  ClipboardList
} from "lucide-react";
import { api } from "../../services/api";
import type { DailyBrief } from "../../services/api";

export const DailyBriefs: React.FC = () => {
  // LLM toggle config
  const [useLocalLlm, setUseLocalLlm] = useState(false);
  const [localModel, setLocalModel] = useState("llama3");

  // Daily Brief state
  const [briefDays, setBriefDays] = useState<number>(7);
  const [isGeneratingBrief, setIsGeneratingBrief] = useState(false);
  const [dailyBrief, setDailyBrief] = useState<DailyBrief | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleGenerateBrief = async () => {
    setIsGeneratingBrief(true);
    setError(null);
    try {
      const result = await api.getDailyBrief(briefDays, useLocalLlm, localModel);
      setDailyBrief(result);
    } catch (err) {
      console.error("Failed to generate brief", err);
      setError("Failed to generate brief. Please try again.");
    } finally {
      setIsGeneratingBrief(false);
    }
  };

  return (
    <div className={styles.container}>
      {/* Top LLM config Bar */}
      <div className={styles.topBar}>
        <div className={styles.llmControl}>
          <label className={styles.toggleLabel}>
            <input 
              type="checkbox" 
              checked={useLocalLlm}
              onChange={(e) => setUseLocalLlm(e.target.checked)}
            />
            <span>Use Local LLM (Ollama)</span>
          </label>

          {useLocalLlm && (
            <select 
              className={styles.modelSelect}
              value={localModel}
              onChange={(e) => setLocalModel(e.target.value)}
            >
              <option value="llama3">Llama 3</option>
              <option value="mistral">Mistral</option>
              <option value="phi3">Phi-3</option>
              <option value="qwen2">Qwen 2</option>
            </select>
          )}
        </div>
      </div>

      {/* Daily Brief Panel */}
      <div className={styles.briefContainer}>
        <div className={styles.briefHeader}>
          <h3 className={styles.briefTitle}>
            <Zap size={20} style={{ color: "var(--accent-color)" }} />
            Proactive Daily Brief
          </h3>
          <div className={styles.briefControls}>
            <select 
              className={styles.briefSelect}
              value={briefDays}
              onChange={(e) => setBriefDays(Number(e.target.value))}
            >
              <option value={1}>Last 24 Hours</option>
              <option value={7}>Last 7 Days</option>
              <option value={30}>Last 30 Days</option>
            </select>
            <button 
              className={styles.refreshBtn}
              onClick={handleGenerateBrief}
              disabled={isGeneratingBrief}
            >
              {isGeneratingBrief ? (
                <><RotateCw size={14} className="spin" style={{ marginRight: '0.4rem' }}/> Generating...</>
              ) : (
                "Generate Brief"
              )}
            </button>
          </div>
        </div>

        {error && (
          <div style={{ color: "var(--error-color)", padding: "1rem 0" }}>
            <AlertCircle size={16} style={{ verticalAlign: "middle", marginRight: "0.5rem" }} />
            {error}
          </div>
        )}

        {!dailyBrief && !isGeneratingBrief && !error && (
          <div className={styles.emptyState}>
            <ClipboardList size={36} style={{ color: "var(--text-muted)" }} />
            <h3 className={styles.emptyTitle}>Ready to Generate</h3>
            <p className={styles.emptyText}>
              Click "Generate Brief" to analyze your recent context and identify stale items, unresolved tasks, and status mismatches.
            </p>
          </div>
        )}

        {isGeneratingBrief && !dailyBrief && (
          <div className={styles.emptyState}>
            <RotateCw size={36} className="spin" style={{ color: "var(--accent-color)" }} />
            <h3 className={styles.emptyTitle}>Analyzing Context...</h3>
            <p className={styles.emptyText}>
              Reviewing recent items across platforms to build your proactive brief. This may take a few seconds.
            </p>
          </div>
        )}

        {dailyBrief && (
          <div className="fade-in">
            <p className={styles.briefSummary}>{dailyBrief.summary}</p>
            <div className={styles.briefGrid}>
              <div className={styles.briefSection}>
                <h4 className={styles.briefSectionTitle}>
                  <Clock size={16} /> Stale Tickets
                </h4>
                <div className={styles.briefList}>
                  {dailyBrief.stale_tickets?.length === 0 ? <span className={styles.briefItemReason}>None found</span> : null}
                  {dailyBrief.stale_tickets?.map((item, idx) => (
                    <div key={idx} className={styles.briefItem}>
                      <span className={styles.briefBadge}>{item.platform.replaceAll("_", " ")}</span>
                      <a href={item.url || "#"} target="_blank" rel="noopener noreferrer" className={styles.briefItemTitle}>{item.title}</a>
                      <span className={styles.briefItemReason}>{item.reason}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className={styles.briefSection}>
                <h4 className={styles.briefSectionTitle}>
                  <AlertCircle size={16} /> Unresolved PRs
                </h4>
                <div className={styles.briefList}>
                  {dailyBrief.unresolved_prs?.length === 0 ? <span className={styles.briefItemReason}>None found</span> : null}
                  {dailyBrief.unresolved_prs?.map((item, idx) => (
                    <div key={idx} className={styles.briefItem}>
                      <span className={styles.briefBadge}>{item.platform.replaceAll("_", " ")}</span>
                      <a href={item.url || "#"} target="_blank" rel="noopener noreferrer" className={styles.briefItemTitle}>{item.title}</a>
                      <span className={styles.briefItemReason}>{item.reason}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className={styles.briefSection}>
                <h4 className={styles.briefSectionTitle}>
                  <HelpCircle size={16} /> Unanswered Questions
                </h4>
                <div className={styles.briefList}>
                  {dailyBrief.unanswered_questions?.length === 0 ? <span className={styles.briefItemReason}>None found</span> : null}
                  {dailyBrief.unanswered_questions?.map((item, idx) => (
                    <div key={idx} className={styles.briefItem}>
                      <span className={styles.briefBadge}>{item.platform.replaceAll("_", " ")}</span>
                      <a href={item.url || "#"} target="_blank" rel="noopener noreferrer" className={styles.briefItemTitle}>{item.title}</a>
                      <span className={styles.briefItemReason}>{item.reason}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className={styles.briefSection}>
                <h4 className={styles.briefSectionTitle}>
                  <Activity size={16} /> Status Mismatches
                </h4>
                <div className={styles.briefList}>
                  {dailyBrief.status_mismatches?.length === 0 ? <span className={styles.briefItemReason}>None found</span> : null}
                  {dailyBrief.status_mismatches?.map((item, idx) => (
                    <div key={idx} className={styles.briefItem}>
                      <span className={styles.briefBadge}>{item.platform.replaceAll("_", " ")}</span>
                      <a href={item.url || "#"} target="_blank" rel="noopener noreferrer" className={styles.briefItemTitle}>{item.title}</a>
                      <span className={styles.briefItemReason}>{item.reason}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
export default DailyBriefs;
