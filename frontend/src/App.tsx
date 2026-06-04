import { useState, useEffect } from "react";
import Layout from "./components/Layout/Layout";
import Dashboard from "./components/Dashboard/Dashboard";
import ConnectionPanel from "./components/ConnectionPanel/ConnectionPanel";
import Graph from "./components/Graph/Graph";

export default function App() {
  const [activeTab, setActiveTab] = useState("dashboard");
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  // Sync theme changes with CSS variables via documentElement attribute
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme((prev) => (prev === "dark" ? "light" : "dark"));
  };

  const handleSeedSuccess = () => {
    // Triggers auto-refresh on dashboard when mock data gets loaded
    setRefreshTrigger((prev) => prev + 1);
  };

  return (
    <Layout
      activeTab={activeTab}
      setActiveTab={setActiveTab}
      theme={theme}
      toggleTheme={toggleTheme}
    >
      {activeTab === "dashboard" && (
        <Dashboard refreshTrigger={refreshTrigger} />
      )}
      {activeTab === "connectors" && (
        <ConnectionPanel onSeedSuccess={handleSeedSuccess} />
      )}
      {activeTab === "graph" && (
        <Graph />
      )}
    </Layout>
  );
}
