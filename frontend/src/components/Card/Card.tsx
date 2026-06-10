import React, { useState } from "react";
import styles from "./Card.module.css";
import { 
  GitBranch, 
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
  Calendar,
  ListChecks,
  HelpCircle,
  ShieldAlert,
  Link2,
  Download
} from "lucide-react";
import type { Document, StitchResult } from "../../services/api";
import { api } from "../../services/api";

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
            <GitBranch size={12} /> GitHub
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

  const exportToMarkdown = () => {
    if (!stitchResult) return;

    let md = `# Context Card: ${doc.title}\n\n`;
    
    if (stitchResult.intent) {
      md += `**Intent**: ${stitchResult.intent.replaceAll("_", " ")}\n\n`;
    }
    
    md += `## Summary\n${stitchResult.summary}\n\n`;
    
    if (stitchResult.timeline && stitchResult.timeline.length > 0) {
      md += `## Timeline\n`;
      stitchResult.timeline.forEach(item => {
        md += `- **${item.label}** (${item.timestamp ? formatDate(item.timestamp) : "Related"}): ${item.detail}\n`;
      });
      md += `\n`;
    }

    if (stitchResult.evidence && stitchResult.evidence.length > 0) {
      md += `## Linked Evidence\n`;
      stitchResult.evidence.forEach(item => {
        const linkStr = item.url ? `[${item.title}](${item.url})` : `**${item.title}**`;
        md += `- ${linkStr} (${item.platform.replaceAll("_", " ")}): ${item.reason}\n`;
      });
      md += `\n`;
    }
    
    if (stitchResult.anomalies) {
      md += `## Anomalies\n${stitchResult.anomalies}\n\n`;
    }

    if (stitchResult.open_questions && stitchResult.open_questions.length > 0) {
      md += `## Open Questions\n`;
      stitchResult.open_questions.forEach(q => md += `- ${q}\n`);
      md += `\n`;
    }

    if (stitchResult.risks && stitchResult.risks.length > 0) {
      md += `## Risks\n`;
      stitchResult.risks.forEach(r => md += `- ${r}\n`);
      md += `\n`;
    }

    if (stitchResult.suggested_actions && stitchResult.suggested_actions.length > 0) {
      md += `## Suggested Actions\n`;
      stitchResult.suggested_actions.forEach(a => {
        const actionStr = a.url ? `[${a.label}](${a.url})` : a.label;
        md += `- ${actionStr}\n`;
      });
      md += `\n`;
    }

    const blob = new Blob([md], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `Context_Card_${doc.platform}_${doc.external_id}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
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
            <div className={styles.stitchSummaryTitle}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                <Cpu size={14} /> Stitched AI Summary
              </div>
              <button 
                className={styles.exportButton} 
                onClick={exportToMarkdown}
                title="Export as Markdown"
              >
                <Download size={14} /> Export MD
              </button>
            </div>
            {stitchResult.intent && (
              <span className={styles.intentBadge}>
                {stitchResult.intent.replaceAll("_", " ")}
              </span>
            )}
            <p className={styles.stitchSummaryText}>{stitchResult.summary}</p>
          </div>

          {stitchResult.timeline && stitchResult.timeline.length > 0 && (
            <div className={styles.contextSection}>
              <h5 className={styles.contextTitle}><ListChecks size={14} /> Timeline</h5>
              <div className={styles.timelineList}>
                {stitchResult.timeline.map((item, index) => (
                  <div key={`${item.label}-${index}`} className={styles.timelineItem}>
                    <span className={styles.timelineDate}>
                      {item.timestamp ? formatDate(item.timestamp) : "Related"}
                    </span>
                    <div>
                      <strong>{item.label}</strong>
                      <p>{item.detail}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {stitchResult.evidence && stitchResult.evidence.length > 0 && (
            <div className={styles.contextSection}>
              <h5 className={styles.contextTitle}><Link2 size={14} /> Linked Evidence</h5>
              <div className={styles.evidenceGrid}>
                {stitchResult.evidence.map((item, index) => (
                  <a
                    key={`${item.title}-${index}`}
                    href={item.url || "#"}
                    target={item.url ? "_blank" : undefined}
                    rel={item.url ? "noopener noreferrer" : undefined}
                    className={styles.evidenceItem}
                  >
                    <span>{item.platform.replaceAll("_", " ")}</span>
                    <strong>{item.title}</strong>
                    <p>{item.reason}</p>
                  </a>
                ))}
              </div>
            </div>
          )}

          {stitchResult.anomalies && (
            <div className={styles.anomalyBox}>
              <AlertTriangle size={16} />
              <div>
                <strong>Anomaly Detected: </strong>
                {stitchResult.anomalies}
              </div>
            </div>
          )}

          {stitchResult.open_questions && stitchResult.open_questions.length > 0 && (
            <div className={styles.contextSection}>
              <h5 className={styles.contextTitle}><HelpCircle size={14} /> Open Questions</h5>
              <ul className={styles.compactList}>
                {stitchResult.open_questions.map((question, index) => (
                  <li key={`${question}-${index}`}>{question}</li>
                ))}
              </ul>
            </div>
          )}

          {stitchResult.risks && stitchResult.risks.length > 0 && (
            <div className={styles.contextSection}>
              <h5 className={styles.contextTitle}><ShieldAlert size={14} /> Risks</h5>
              <ul className={styles.compactList}>
                {stitchResult.risks.map((risk, index) => (
                  <li key={`${risk}-${index}`}>{risk}</li>
                ))}
              </ul>
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
