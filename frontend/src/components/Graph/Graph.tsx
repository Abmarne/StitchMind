import React, { useEffect, useState, useRef } from "react";
import styles from "./Graph.module.css";
import { Network, RefreshCw } from "lucide-react";
import { api, EntityLink } from "../../services/api";

interface Node {
  id: number;
  title: string;
  platform: string;
  x: number;
  y: number;
  vx: number;
  vy: number;
}

interface Edge {
  id: number;
  source: Node;
  target: Node;
  link_type: string;
  description: string;
}

export const Graph: React.FC = () => {
  const [links, setLinks] = useState<EntityLink[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  
  // Physics states
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const animationRef = useRef<number | null>(null);
  
  // Tooltip & selection states
  const [hoveredEdge, setHoveredEdge] = useState<Edge | null>(null);
  const [hoveredNode, setHoveredNode] = useState<Node | null>(null);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });

  const canvasWidth = 800;
  const canvasHeight = 500;

  const loadGraph = async () => {
    setIsLoading(true);
    try {
      const data = await api.getLinks();
      setLinks(data);
      initializePhysics(data);
    } catch (err) {
      console.error("Failed to load graph links", err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadGraph();
    return () => {
      if (animationRef.current) cancelAnimationFrame(animationRef.current);
    };
  }, []);

  const initializePhysics = (linkData: EntityLink[]) => {
    // 1. Gather unique nodes
    const nodeMap: Record<number, Node> = {};
    
    // Helper to ensure node exists
    const addNode = (id: number, title: string, platform: string) => {
      if (!nodeMap[id]) {
        // Randomize initial position near center
        nodeMap[id] = {
          id,
          title,
          platform,
          x: canvasWidth / 2 + (Math.random() - 0.5) * 150,
          y: canvasHeight / 2 + (Math.random() - 0.5) * 150,
          vx: 0,
          vy: 0
        };
      }
    };

    linkData.forEach((l) => {
      addNode(l.source.id, l.source.title, l.source.platform);
      addNode(l.target.id, l.target.title, l.target.platform);
    });

    const uniqueNodes = Object.values(nodeMap);
    
    // 2. Map edges to node references
    const edgeData: Edge[] = linkData.map((l) => ({
      id: l.id,
      source: nodeMap[l.source.id],
      target: nodeMap[l.target.id],
      link_type: l.link_type,
      description: l.description
    }));

    setNodes(uniqueNodes);
    setEdges(edgeData);
  };

  // Run force-directed simulation
  useEffect(() => {
    if (nodes.length === 0) return;

    const runSimulation = () => {
      // Clone nodes to update coordinates
      const nextNodes = nodes.map(n => ({ ...n }));
      const idToNode = nextNodes.reduce((acc, n) => {
        acc[n.id] = n;
        return acc;
      }, {} as Record<number, Node>);

      const center = { x: canvasWidth / 2, y: canvasHeight / 2 };
      
      // Constants for forces
      const gravity = 0.04;
      const repulsionConstant = 600;
      const springConstant = 0.06;
      const friction = 0.85;

      // 1. Repulsion between all node pairs
      for (let i = 0; i < nextNodes.length; i++) {
        const nodeA = nextNodes[i];
        for (let j = i + 1; j < nextNodes.length; j++) {
          const nodeB = nextNodes[j];
          const dx = nodeB.x - nodeA.x;
          const dy = nodeB.y - nodeA.y;
          // Avoid division by zero
          const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
          
          if (dist < 250) {
            const force = repulsionConstant / (dist * dist);
            const fx = (dx / dist) * force;
            const fy = (dy / dist) * force;

            nodeA.vx -= fx;
            nodeA.vy -= fy;
            nodeB.vx += fx;
            nodeB.vy += fy;
          }
        }
      }

      // 2. Attraction along edges (spring forces)
      edges.forEach((edge) => {
        const nodeA = idToNode[edge.source.id];
        const nodeB = idToNode[edge.target.id];
        if (!nodeA || !nodeB) return;

        const dx = nodeB.x - nodeA.x;
        const dy = nodeB.y - nodeA.y;
        const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
        
        // Target length of spring is 100px
        const force = (dist - 120) * springConstant;
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;

        nodeA.vx += fx;
        nodeA.vy += fy;
        nodeB.vx -= fx;
        nodeB.vy -= fy;
      });

      // 3. Update positions and velocities
      nextNodes.forEach((node) => {
        // Center gravity pulling to midpoint
        const dx = center.x - node.x;
        const dy = center.y - node.y;
        node.vx += dx * gravity;
        node.vy += dy * gravity;

        // Apply friction and step coordinates
        node.vx *= friction;
        node.vy *= friction;
        node.x += node.vx;
        node.y += node.vy;

        // Keep within bounds
        node.x = Math.max(30, Math.min(canvasWidth - 30, node.x));
        node.y = Math.max(30, Math.min(canvasHeight - 30, node.y));
      });

      // Map node references back to edges
      const nextEdges = edges.map(e => ({
        ...e,
        source: idToNode[e.source.id],
        target: idToNode[e.target.id]
      }));

      setNodes(nextNodes);
      setEdges(nextEdges);

      animationRef.current = requestAnimationFrame(runSimulation);
    };

    animationRef.current = requestAnimationFrame(runSimulation);

    return () => {
      if (animationRef.current) cancelAnimationFrame(animationRef.current);
    };
  }, [nodes.length, edges.length]);

  const getNodeColor = (platform: string) => {
    switch (platform.toLowerCase()) {
      case "github": return "#94a3b8"; // Slate
      case "slack": return "#e05689"; // Magenta
      case "jira": return "#2563eb"; // Blue
      case "google_workspace": return "#3b82f6"; // Google Docs blue
      case "gmail": return "#ef4444"; // Gmail red
      default: return "#6366f1";
    }
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    const rect = e.currentTarget.getBoundingClientRect();
    setTooltipPos({
      x: e.clientX - rect.left + 15,
      y: e.clientY - rect.top + 15
    });
  };

  return (
    <div className={styles.card}>
      <div className={styles.graphMeta}>
        <span className={styles.instructions}>
          Hover over connections to inspect cross-platform relations. Drag is calculated dynamically.
        </span>
        <button className={styles.refreshBtn} onClick={loadGraph} title="Reload Network">
          <RefreshCw size={16} className={isLoading ? "spin" : ""} />
        </button>
      </div>

      <div className={styles.canvasContainer} onMouseMove={handleMouseMove}>
        {isLoading ? (
          <div style={{ textAlign: "center", padding: "8rem" }}>
            <RefreshCw size={24} className="spin" style={{ color: "var(--accent-color)" }} />
            <p style={{ marginTop: "1rem", color: "var(--text-secondary)" }}>Mapping context graph...</p>
          </div>
        ) : nodes.length === 0 ? (
          <div style={{ textAlign: "center", padding: "8rem", color: "var(--text-muted)", fontSize: "0.9rem" }}>
            <Network size={32} style={{ marginBottom: "1rem" }} />
            <p>No connections mapped. Synchronize items in the dashboard first.</p>
          </div>
        ) : (
          <>
            <svg className={styles.canvas} viewBox={`0 0 ${canvasWidth} ${canvasHeight}`}>
              {/* Draw Edges */}
              {edges.map((edge) => {
                const isActive = hoveredEdge?.id === edge.id;
                return (
                  <line
                    key={edge.id}
                    className={`${styles.edge} ${isActive ? styles.edgeActive : ""}`}
                    x1={edge.source.x}
                    y1={edge.source.y}
                    x2={edge.target.x}
                    y2={edge.target.y}
                    onMouseEnter={() => setHoveredEdge(edge)}
                    onMouseLeave={() => setHoveredEdge(null)}
                  />
                );
              })}

              {/* Draw Nodes */}
              {nodes.map((node) => {
                const nodeColor = getNodeColor(node.platform);
                return (
                  <g key={node.id}>
                    <circle
                      className={styles.node}
                      style={{ "--glow-color": nodeColor } as React.CSSProperties}
                      cx={node.x}
                      cy={node.y}
                      r={hoveredNode?.id === node.id ? 14 : 10}
                      fill={nodeColor}
                      onMouseEnter={() => setHoveredNode(node)}
                      onMouseLeave={() => setHoveredNode(null)}
                    />
                    <text
                      className={styles.nodeLabel}
                      x={node.x}
                      y={node.y - 18}
                    >
                      {node.title.length > 20 ? node.title.slice(0, 18) + "..." : node.title}
                    </text>
                  </g>
                );
              })}
            </svg>

            {/* Edge Tooltip */}
            {hoveredEdge && (
              <div 
                className={styles.tooltip}
                style={{ left: tooltipPos.x, top: tooltipPos.y }}
              >
                <span className={styles.tooltipTitle}>
                  {hoveredEdge.link_type.toUpperCase()} Relationship
                </span>
                <span className={styles.tooltipDesc}>
                  <strong>{hoveredEdge.source.platform.toUpperCase()}</strong> connected to <strong>{hoveredEdge.target.platform.toUpperCase()}</strong>:
                  <br />
                  {hoveredEdge.description}
                </span>
              </div>
            )}

            {/* Node Tooltip */}
            {hoveredNode && !hoveredEdge && (
              <div 
                className={styles.tooltip}
                style={{ left: tooltipPos.x, top: tooltipPos.y }}
              >
                <span className={styles.tooltipTitle}>
                  {hoveredNode.platform.toUpperCase()} Entity
                </span>
                <span className={styles.tooltipDesc}>
                  {hoveredNode.title}
                </span>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};
export default Graph;
