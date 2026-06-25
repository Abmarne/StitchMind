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
  Activity
} from "lucide-react";
import { api } from "../../services/api";
import type { Document } from "../../services/api";
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
