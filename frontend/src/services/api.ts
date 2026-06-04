const API_BASE = "http://127.0.0.1:8000/api";

export interface Connector {
  id: number;
  platform: string;
  name: string;
  is_active: boolean;
  sync_interval_mins: number;
  last_sync?: string;
}

export interface Document {
  id: number;
  platform: string;
  external_id: string;
  title: string;
  body: string;
  url?: string;
  author?: string;
  created_at: string;
  synced_at: string;
}

export interface EntityLink {
  id: number;
  source: {
    id: number;
    title: string;
    platform: string;
  };
  target: {
    id: number;
    title: string;
    platform: string;
  };
  link_type: string;
  confidence: number;
  description: string;
}

export interface SuggestedAction {
  label: string;
  action_type: string;
  url?: string;
  payload?: any;
}

export interface StitchResult {
  summary: string;
  anomalies?: string;
  suggested_actions: SuggestedAction[];
  error?: string;
}

export interface AppConfig {
  gemini_api_key_configured: boolean;
  ollama_host: string;
  embedding_model: string;
}

export const api = {
  async getHealth(): Promise<{ status: string }> {
    const res = await fetch(`${API_BASE}/health`);
    return res.json();
  },

  async getConfig(): Promise<AppConfig> {
    const res = await fetch(`${API_BASE}/config`);
    return res.json();
  },

  async updateConfig(payload: { gemini_api_key?: string; ollama_host?: string }): Promise<{ status: string; config: AppConfig }> {
    const res = await fetch(`${API_BASE}/config`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return res.json();
  },

  async getConnectors(): Promise<Connector[]> {
    const res = await fetch(`${API_BASE}/connectors`);
    return res.json();
  },

  async createConnector(payload: { platform: string; name: string; auth_config: Record<string, any>; sync_interval_mins?: number }): Promise<Connector> {
    const res = await fetch(`${API_BASE}/connectors`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      throw new Error(`Failed to create connector: ${res.statusText}`);
    }
    return res.json();
  },

  async deleteConnector(connectorId: number): Promise<{ status: string }> {
    const res = await fetch(`${API_BASE}/connectors/${connectorId}`, {
      method: "DELETE",
    });
    return res.json();
  },

  async getDocuments(platform?: string, search?: string): Promise<Document[]> {
    const params = new URLSearchParams();
    if (platform) params.append("platform", platform);
    if (search) params.append("search", search);
    const res = await fetch(`${API_BASE}/documents?${params.toString()}`);
    return res.json();
  },

  async getDocument(docId: number): Promise<Document> {
    const res = await fetch(`${API_BASE}/documents/${docId}`);
    return res.json();
  },

  async getStitchCard(docId: number, useLocalLlm: boolean = false, localModel: string = "llama3"): Promise<StitchResult> {
    const params = new URLSearchParams();
    if (useLocalLlm) params.append("use_local_llm", "true");
    params.append("local_model", localModel);
    const res = await fetch(`${API_BASE}/documents/${docId}/stitch?${params.toString()}`);
    return res.json();
  },

  async getLinks(): Promise<EntityLink[]> {
    const res = await fetch(`${API_BASE}/links`);
    return res.json();
  },

  async seedMockData(): Promise<{ status: string; message: string }> {
    const res = await fetch(`${API_BASE}/seed-mock-data`, {
      method: "POST",
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Failed to seed demo database");
    }
    return res.json();
  },
};
