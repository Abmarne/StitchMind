import React, { useState, useEffect } from "react";
import styles from "./Dashboard.module.css";
import { 
  Search, 
  RotateCw, 
  Layers, 
  GitBranch, 
  MessageSquare, 
  Ticket, 
  FileText, 
  Mail,
  GitPullRequest,
  Clock,
  AlertCircle,
  HelpCircle,
  Activity,
  Zap
} from "lucide-react";
import { api } from "../../services/api";
import type { Document, DailyBrief } from "../../services/api";
import { Card } from "../Card/Card";

interface DashboardProps {
  refreshTrigger: number;
}

export const Dashboard: React.FC<DashboardProps> = ({ refreshTrigger }) => {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [activePlatform, setActivePlatform] = useState<string | undefined>(undefined);
  
  // LLM toggle config
  const [useLocalLlm, setUseLocalLlm] = useState(false);
  const [localModel, setLocalModel] = useState("llama3");

  // Daily Brief state
  const [briefDays, setBriefDays] = useState<number>(7);
  const [isGeneratingBrief, setIsGeneratingBrief] = useState(false);
  const [dailyBrief, setDailyBrief] = useState<DailyBrief | null>(null);

  const loadDocuments = async () => {
    setIsLoading(true);
    try {
      const data = await api.getDocuments(activePlatform, search);
      setDocuments(data);
    } catch (err) {
      console.error("Failed to load documents", err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadDocuments();
  }, [activePlatform, search, refreshTrigger]);

  const handleRefresh = (e: React.MouseEvent) => {
    e.preventDefault();
    loadDocuments();
  };

  const handleGenerateBrief = async () => {
    setIsGeneratingBrief(true);
    try {
      const result = await api.getDailyBrief(briefDays, useLocalLlm, localModel);
      setDailyBrief(result);
    } catch (err) {
      console.error("Failed to generate brief", err);
    } finally {
      setIsGeneratingBrief(false);
    }
  };

  return (
    <div className={styles.container}>
      {/* Top Search & LLM config Bar */}
      <div className={styles.topBar}>
        <div className={styles.searchBar}>
          <Search size={18} className={styles.searchIcon} />
          <input 
            type="text" 
            className={styles.searchInput}
            placeholder="Search storable context, titles, code keywords..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

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
              style={{ width: 'auto', padding: '0 1rem' }}
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

        {dailyBrief && (
          <div className="fade-in">
            <p className={styles.briefSummary}>{dailyBrief.summary}</p>
            <div className={styles.briefGrid}>
              <div className={styles.briefSection}>
                <h4 className={styles.briefSectionTitle}>
                  <Clock size={16} /> Stale Tickets
                </h4>
                <div className={styles.briefList}>
                  {dailyBrief.stale_tickets.length === 0 ? <span className={styles.briefItemReason}>None found</span> : null}
                  {dailyBrief.stale_tickets.map((item, idx) => (
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
                  {dailyBrief.unresolved_prs.length === 0 ? <span className={styles.briefItemReason}>None found</span> : null}
                  {dailyBrief.unresolved_prs.map((item, idx) => (
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
                  {dailyBrief.unanswered_questions.length === 0 ? <span className={styles.briefItemReason}>None found</span> : null}
                  {dailyBrief.unanswered_questions.map((item, idx) => (
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
                  {dailyBrief.status_mismatches.length === 0 ? <span className={styles.briefItemReason}>None found</span> : null}
                  {dailyBrief.status_mismatches.map((item, idx) => (
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

      {/* Filter Row */}
      <div className={styles.filterRow}>
        <div className={styles.platformPills}>
          <button 
            className={`${styles.pill} ${activePlatform === undefined ? styles.activePill : ""}`}
            onClick={() => setActivePlatform(undefined)}
          >
            <Layers size={14} /> All Feed
          </button>
          <button 
            className={`${styles.pill} ${activePlatform === "github" ? styles.activePill : ""}`}
            onClick={() => setActivePlatform("github")}
          >
            <GitBranch size={14} /> GitHub
          </button>
          <button 
            className={`${styles.pill} ${activePlatform === "slack" ? styles.activePill : ""}`}
            onClick={() => setActivePlatform("slack")}
          >
            <MessageSquare size={14} /> Slack
          </button>
          <button 
            className={`${styles.pill} ${activePlatform === "jira" ? styles.activePill : ""}`}
            onClick={() => setActivePlatform("jira")}
          >
            <Ticket size={14} /> Jira
          </button>
          <button 
            className={`${styles.pill} ${activePlatform === "google_workspace" ? styles.activePill : ""}`}
            onClick={() => setActivePlatform("google_workspace")}
          >
            <FileText size={14} /> Google Docs
          </button>
          <button 
            className={`${styles.pill} ${activePlatform === "gmail" ? styles.activePill : ""}`}
            onClick={() => setActivePlatform("gmail")}
          >
            <Mail size={14} /> Gmail
          </button>
        </div>

        <button 
          className={styles.refreshBtn} 
          onClick={handleRefresh} 
          title="Sync Feed"
          disabled={isLoading}
        >
          <RotateCw size={16} className={isLoading ? "spin" : ""} />
        </button>
      </div>

      {/* Main feed list */}
      <div className={styles.feedList}>
        {isLoading ? (
          <div style={{ textAlign: "center", padding: "3rem" }}>
            <RotateCw size={24} className="spin" style={{ color: "var(--accent-color)" }} />
            <p style={{ marginTop: "1rem", color: "var(--text-secondary)" }}>Searching databases...</p>
          </div>
        ) : documents.length === 0 ? (
          <div className={styles.emptyState}>
            <GitPullRequest size={36} style={{ color: "var(--text-muted)" }} />
            <h3 className={styles.emptyTitle}>Your feed is empty</h3>
            <p className={styles.emptyText}>
              StitchMind hasn't ingested any platform logs yet. Go to the **Connectors** page, add credentials, or 
              click "Seed Sandbox Data" to test the tool immediately.
            </p>
          </div>
        ) : (
          documents.map((doc) => (
            <Card 
              key={doc.id} 
              doc={doc} 
              useLocalLlm={useLocalLlm} 
              localModel={localModel}
            />
          ))
        )}
      </div>
    </div>
  );
};
export default Dashboard;
