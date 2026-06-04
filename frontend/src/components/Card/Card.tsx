import React, { useState } from "react";
import styles from "./Card.module.css";
import { 
  Github, 
  MessageSquare, 
  Ticket, 
  FileText, 
  Mail, 
  Cpu, 
  ExternalLink, 
  AlertTriangle, 
  Sparkles,
  RefreshCw,
  User,
  Calendar
} from "lucide-react";
import { Document, StitchResult, api } from "../../services/api";

interface CardProps {
  doc: Document;
  useLocalLlm: boolean;
  localModel: string;
}

export const Card: React.FC<CardProps> = ({ doc, useLocalLlm, localModel }) => {
  const [isStitching, setIsStitching] = useState(false);
  const [stitchResult, setStitchResult] = useState<StitchResult | null>(null);
  const [hasStitched, setHasStitched] = useState(false);

  const handleStitch = async () => {
    setIsStitching(true);
    try {
      const result = await api.getStitchCard(doc.id, useLocalLlm, localModel);
      setStitchResult(result);
      setHasStitched(true);
    } catch (err) {
      console.error(err);
      setStitchResult({
        summary: "An error occurred while connecting to the LLM stitcher. Ensure your backend is running.",
        suggested_actions: []
      });
      setHasStitched(true);
    } finally {
      setIsStitching(false);
    }
  };

  const getPlatformBadge = (platform: string) => {
    switch (platform.toLowerCase()) {
      case "github":
        return (
          <span className={`${styles.badge} ${styles.badgeGithub}`}>
            <Github size={12} /> GitHub
          </span>
        );
      case "slack":
        return (
          <span className={`${styles.badge} ${styles.badgeSlack}`}>
            <MessageSquare size={12} /> Slack
          </span>
        );
      case "jira":
        return (
          <span className={`${styles.badge} ${styles.badgeJira}`}>
            <Ticket size={12} /> Jira
          </span>
        );
      case "google_workspace":
        return (
          <span className={`${styles.badge} ${styles.badgeGoogle}`}>
            <FileText size={12} /> Google Docs
          </span>
        );
      case "gmail":
        return (
          <span className={`${styles.badge} ${styles.badgeGmail}`}>
            <Mail size={12} /> Gmail
          </span>
        );
      default:
        return <span className={styles.badge}>{platform}</span>;
    }
  };

  const formatDate = (dateStr: string) => {
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString(undefined, { 
        month: "short", 
        day: "numeric", 
        hour: "2-digit", 
        minute: "2-digit" 
      });
    } catch {
      return dateStr;
    }
  };

  return (
    <div className={`${styles.card} fade-in`}>
      <div className={styles.header}>
        <div className={styles.titleSection}>
          {getPlatformBadge(doc.platform)}
          <h3 className={styles.title}>{doc.title}</h3>
        </div>
      </div>

      <div className={styles.meta}>
        {doc.author && (
          <span className={styles.metaItem}>
            <User size={12} /> {doc.author}
          </span>
        )}
        <span className={styles.metaItem}>
          <Calendar size={12} /> {formatDate(doc.created_at)}
        </span>
      </div>

      <div className={styles.body}>{doc.body}</div>

      <div className={styles.cardFooter}>
        {doc.url ? (
          <a href={doc.url} target="_blank" rel="noopener noreferrer" className={styles.externalLink}>
            Open Original Resource <ExternalLink size={12} />
          </a>
        ) : (
          <span />
        )}

        <button 
          className={styles.stitchButton} 
          onClick={handleStitch} 
          disabled={isStitching}
        >
          {isStitching ? (
            <>
              <RefreshCw size={14} className="spin" /> Stitching Context...
            </>
          ) : (
            <>
              <Sparkles size={14} /> {hasStitched ? "Re-Stitch Context" : "Stitch Context"}
            </>
          )}
        </button>
      </div>

      {/* Stitched Output Panel */}
      {hasStitched && stitchResult && (
        <div className={styles.stitchPanel}>
          <div className={styles.stitchSummary}>
            <h4 className={styles.stitchSummaryTitle}>
              <Cpu size={14} /> Stitched AI Summary
            </h4>
            <p className={styles.stitchSummaryText}>{stitchResult.summary}</p>
          </div>

          {stitchResult.anomalies && (
            <div className={styles.anomalyBox}>
              <AlertTriangle size={16} />
              <div>
                <strong>Anomaly Detected: </strong>
                {stitchResult.anomalies}
              </div>
            </div>
          )}

          {stitchResult.suggested_actions && stitchResult.suggested_actions.length > 0 && (
            <div className={styles.actionsContainer}>
              <h5 className={styles.actionsTitle}>Suggested Actions</h5>
              <div className={styles.actionList}>
                {stitchResult.suggested_actions.map((act, index) => {
                  if (act.url) {
                    return (
                      <a 
                        key={index} 
                        href={act.url} 
                        target="_blank" 
                        rel="noopener noreferrer" 
                        className={styles.actionBtn}
                      >
                        {act.label} <ExternalLink size={12} />
                      </a>
                    );
                  }
                  return (
                    <button 
                      key={index} 
                      className={styles.actionBtn}
                      onClick={() => alert(`Triggered Mock Action: ${act.label}`)}
                    >
                      {act.label}
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
export default Card;
