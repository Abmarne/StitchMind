import React, { useEffect, useState } from "react";
import styles from "./Layout.module.css";
import { LayoutDashboard, Cable, Network, Sun, Moon, GitMerge, ClipboardList } from "lucide-react";
import { api } from "../../services/api";

interface LayoutProps {
  children: React.ReactNode;
  activeTab: string;
  setActiveTab: (tab: string) => void;
  theme: "dark" | "light";
  toggleTheme: () => void;
}

export const Layout: React.FC<LayoutProps> = ({
  children,
  activeTab,
  setActiveTab,
  theme,
  toggleTheme,
}) => {
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const checkConnection = async () => {
      try {
        const res = await api.getHealth();
        if (res.status === "ok") {
          setConnected(true);
        } else {
          setConnected(false);
        }
      } catch (err) {
        setConnected(false);
      }
    };
    checkConnection();
    // Poll backend health status every 10s
    const interval = setInterval(checkConnection, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className={styles.container}>
      <aside className={styles.sidebar}>
        <div>
          <div className={styles.brand}>
            <div className={styles.logoIcon}>
              <GitMerge size={18} strokeWidth={3} />
            </div>
            <span className={styles.brandText}>StitchMind</span>
          </div>

          <nav className={styles.nav}>
            <button
              className={`${styles.navLink} ${activeTab === "dashboard" ? styles.activeNavLink : ""}`}
              onClick={() => setActiveTab("dashboard")}
              style={{ background: "none", border: "none", width: "100%", textAlign: "left" }}
            >
              <LayoutDashboard size={18} />
              <span>Dashboard</span>
            </button>
            <button
              className={`${styles.navLink} ${activeTab === "connectors" ? styles.activeNavLink : ""}`}
              onClick={() => setActiveTab("connectors")}
              style={{ background: "none", border: "none", width: "100%", textAlign: "left" }}
            >
              <Cable size={18} />
              <span>Connectors</span>
            </button>
            <button
              className={`${styles.navLink} ${activeTab === "briefs" ? styles.activeNavLink : ""}`}
              onClick={() => setActiveTab("briefs")}
              style={{ background: "none", border: "none", width: "100%", textAlign: "left" }}
            >
              <ClipboardList size={18} />
              <span>Daily Briefs</span>
            </button>
            <button
              className={`${styles.navLink} ${activeTab === "graph" ? styles.activeNavLink : ""}`}
              onClick={() => setActiveTab("graph")}
              style={{ background: "none", border: "none", width: "100%", textAlign: "left" }}
            >
              <Network size={18} />
              <span>Context Graph</span>
            </button>
          </nav>
        </div>

        <div className={styles.footer}>
          <div className={styles.statusIndicator}>
            <span
              className={`${styles.statusDot} ${
                connected ? styles.statusDotConnected : styles.statusDotDisconnected
              }`}
            />
            <span>{connected ? "Local Core Connected" : "Core Connecting..."}</span>
          </div>
        </div>
      </aside>

      <div className={styles.content}>
        <header className={styles.header}>
          <h2 className={styles.headerTitle}>
            {activeTab === "dashboard" 
              ? "Stitched Context" 
              : activeTab === "connectors" 
              ? "External Connections" 
              : activeTab === "briefs"
              ? "Daily Briefs"
              : "Knowledge Graph Network"}
          </h2>
          <div className={styles.headerActions}>
            <button className={styles.themeToggle} onClick={toggleTheme} title="Toggle Theme">
              {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
            </button>
          </div>
        </header>
        <main className={styles.main}>{children}</main>
      </div>
    </div>
  );
};
export default Layout;
