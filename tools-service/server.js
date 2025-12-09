/**
 * Tools Microservice (MCP Server)
 * ===============================
 * Acts as the "Limbs" for the AI Agent.
 * Connects to:
 * - Manifest API (Resources, Incidents, Tickets, Graph)
 * - VictoriaMetrics & VictoriaLogs (Observability)
 * - Neo4j (Direct Graph Access)
 */

const express = require('express');
const axios = require('axios');
const neo4j = require('neo4j-driver');
const config = require('./config');

const app = express();
const PORT = config.SERVER_PORT || 3001;

// ============================================================================
// 1. CONFIGURATION & CONNECTIONS
// ============================================================================

// Neo4j Setup
const NEO4J_CONFIG = config.NEO4J_CONFIG;
let neo4jDriver = null;

if (NEO4J_CONFIG && NEO4J_CONFIG.uri) {
    try {
        neo4jDriver = neo4j.driver(
            NEO4J_CONFIG.uri,
            neo4j.auth.basic(NEO4J_CONFIG.username, NEO4J_CONFIG.password),
            { maxConnectionLifetime: 3 * 60 * 60 * 1000 }
        );
        console.log('🔧 Neo4j driver initialized');
    } catch (error) {
        console.error('❌ Failed to initialize Neo4j driver:', error.message);
    }
}

// Manifest API Setup
const MANIFEST_API_URL = config.MANIFEST_API_URL;
const MANIFEST_API_KEY = config.MANIFEST_API_KEY;
const MANIFEST_ORG_KEY = config.MANIFEST_ORG_KEY || 'dev';

// Victoria Configuration
const VICTORIA_METRICS_SELECT_URL = config.VICTORIA_METRICS_SELECT_URL;
const VICTORIA_LOGS_API_URL = config.VICTORIA_LOGS_API_URL || config.VICTORIA_LOGS_URL;

// ============================================================================
// 2. TOOL DEFINITIONS (Schema)
// ============================================================================
const MCP_TOOLS = {
    // --- RESOURCES ---
    get_resources: {
        name: "get_resources",
        description: "List all resources. Use search_resources for filtering.",
        inputSchema: {
            type: "object",
            properties: {
                page: { type: "integer", default: 1 },
                page_size: { type: "integer", default: 20 }
            }
        }
    },
    get_resource_by_id: {
        name: "get_resource_by_id",
        description: "Get a specific resource by ID (rid)",
        inputSchema: {
            type: "object",
            properties: {
                rid: { type: "string", required: true }
            },
            required: ["rid"]
        }
    },
    search_resources: {
        name: "search_resources",
        description: "Search resources with comprehensive filters",
        inputSchema: {
            type: "object",
            properties: {
                query: { type: "string", description: "Filter by ID, name, account, subtype" },
                name: { type: "string" },
                id: { type: "string" },
                status: { type: "string" },
                provider_key: { type: "string" },
                type: { type: "string" },
                created: { type: "string", description: "Date string" },
                updated: { type: "string", description: "Date string" },
                category: { type: "string" },
                sub_type: { type: "string" },
                provider_config_id: { type: "integer" },
                severity: { type: "string" },
                watch_level: { type: "string" },
                app_id: { type: "string" },
                sortBy: { type: "string", enum: ["updated_at", "provider_key", "watch_level", "resourceType", "resourceName", "resourceId", "resourceStatus", "criticality"] },
                direction: { type: "string", enum: ["asc", "desc"] },
                page: { type: "integer", default: 1 },
                page_size: { type: "integer", default: 20 }
            }
        }
    },

    // --- TICKETS ---
    get_tickets: {
        name: "get_tickets",
        description: "List all tickets",
        inputSchema: {
            type: "object",
            properties: {
                page: { type: "integer", default: 1 },
                page_size: { type: "integer", default: 20 }
            }
        }
    },
    get_ticket_by_id: {
        name: "get_ticket_by_id",
        description: "Get ticket by numeric ID",
        inputSchema: {
            type: "object",
            properties: {
                id: { type: "integer", required: true }
            },
            required: ["id"]
        }
    },
    search_tickets: {
        name: "search_tickets",
        description: "Search tickets with filters",
        inputSchema: {
            type: "object",
            properties: {
                query: { type: "string", description: "Text search in title, desc, status" },
                title: { type: "string" },
                status: { type: "string" },
                description: { type: "string" },
                severity: { type: "string" },
                source: { type: "string" },
                created_before: { type: "string" },
                created: { type: "string" },
                id: { type: "string" },
                sortBy: { type: "string", enum: ["updated_at", "title", "type", "priority", "status"] },
                direction: { type: "string", enum: ["asc", "desc"] },
                page: { type: "integer", default: 1 },
                page_size: { type: "integer", default: 20 }
            }
        }
    },

    // --- INCIDENTS ---
    get_incidents: {
        name: "get_incidents",
        description: "List all incidents",
        inputSchema: {
            type: "object",
            properties: {
                page: { type: "integer", default: 1 },
                page_size: { type: "integer", default: 20 }
            }
        }
    },
    get_incident_by_id: {
        name: "get_incident_by_id",
        description: "Get incident by ID string",
        inputSchema: {
            type: "object",
            properties: {
                id: { type: "string", required: true }
            },
            required: ["id"]
        }
    },
    search_incidents: {
        name: "search_incidents",
        description: "Search incidents with filters",
        inputSchema: {
            type: "object",
            properties: {
                query: { type: "string" },
                title: { type: "string" },
                status: { type: "string" },
                severity: { type: "string" },
                source: { type: "string" },
                created_before: { type: "string" },
                created: { type: "string" },
                sortBy: { type: "string", enum: ["updated_at", "title", "priority", "status"] },
                direction: { type: "string", enum: ["asc", "desc"] },
                page: { type: "integer", default: 1 },
                page_size: { type: "integer", default: 20 }
            }
        }
    },

    // --- CHANGELOGS ---
    get_changelogs: {
        name: "get_changelogs",
        description: "List changelogs",
        inputSchema: {
            type: "object",
            properties: {
                page: { type: "integer", default: 1 },
                page_size: { type: "integer", default: 20 }
            }
        }
    },
    get_changelog_by_id: {
        name: "get_changelog_by_id",
        description: "Get changelog by ID",
        inputSchema: {
            type: "object",
            properties: {
                id: { type: "string", required: true }
            },
            required: ["id"]
        }
    },
    search_changelogs: {
        name: "search_changelogs",
        description: "Search changelogs with detailed filters",
        inputSchema: {
            type: "object",
            properties: {
                severity: { type: "string" },
                provider_key: { type: "string" },
                description: { type: "string" },
                created: { type: "string" },
                created_before: { type: "string" },
                provider_config_id: { type: "integer" },
                doneByUser: { type: "boolean" },
                query: { type: "string" },
                category: { type: "string" },
                type: { type: "string" },
                event_type: { type: "string" },
                changeType: { type: "string" },
                changeAction: { type: "string" },
                application_id: { type: "integer" },
                sortBy: { type: "string", enum: ["create_date", "provider_key", "severity"] },
                direction: { type: "string", enum: ["asc", "desc"] },
                page: { type: "integer", default: 1 },
                page_size: { type: "integer", default: 20 }
            }
        }
    },

    // --- NOTIFICATIONS ---
    get_notifications: {
        name: "get_notifications",
        description: "List notifications",
        inputSchema: {
            type: "object",
            properties: {
                page: { type: "integer", default: 1 },
                page_size: { type: "integer", default: 20 }
            }
        }
    },

    // --- GRAPH ---
    get_graph_nodes: {
        name: "get_graph_nodes",
        description: "Retrieve graph nodes and relationships",
        inputSchema: {
            type: "object",
            properties: {
                key: { type: "string" },
                provider_key: { type: "string" },
                providerConfigurationId: { type: "string" },
                resourceType: { type: "string" },
                resourceSubType: { type: "string" },
                watch_level: { type: "string" },
                mitResourceId: { type: "string" },
                depth: { type: "string" },
                skip: { type: "string" },
                take: { type: "string" },
                nextNodeId: { type: "string" },
                nextRelationshipId: { type: "string" },
                applicationId: { type: "string" }
            }
        }
    },
    create_graph_link: {
        name: "create_graph_link",
        description: "Link two nodes",
        inputSchema: {
            type: "object",
            properties: {
                fromKey: { type: "string", required: true },
                toKey: { type: "string", required: true },
                relationship: { type: "string" }
            },
            required: ["fromKey", "toKey"]
        }
    },
    execute_graph_cypher: {
        name: "execute_graph_cypher",
        description: "Execute raw Cypher query",
        inputSchema: {
            type: "object",
            properties: {
                cypher: { type: "string", required: true }
            },
            required: ["cypher"]
        }
    },

    // --- OBSERVABILITY (VictoriaMetrics) ---
    query_logs: {
        name: "query_logs",
        description: "Execute LogSQL query",
        inputSchema: {
            type: "object",
            properties: {
                query: { type: "string", required: true },
                limit: { type: "integer", default: 1000 }
            },
            required: ["query"]
        }
    },
    query_metrics: {
        name: "query_metrics",
        description: "Execute PromQL query",
        inputSchema: {
            type: "object",
            properties: {
                query: { type: "string", required: true },
                start: { type: "string" },
                end: { type: "string" },
                step: { type: "string" }
            },
            required: ["query"]
        }
    }
};

// ============================================================================
// 3. TOOL REGISTRY IMPLEMENTATION
// ============================================================================

class MCPToolRegistry {
    constructor() {
        this.tools = new Map();
        this.registerTools();
    }

    registerTools() {
        // --- Resource Tools ---
        this.tools.set('get_resources', this.callManifestGet.bind(this, '/client/resource'));
        this.tools.set('get_resource_by_id', (params) => this.callManifestGet(`/client/resource/${params.rid}`, {}));
        this.tools.set('search_resources', this.callManifestGet.bind(this, '/client/resource/search'));
        // Helper wrappers for specific resource metadata (if needed)
        this.tools.set('get_resource_version', (params) => this.callManifestGet(`/client/resource/${params.resource_id}/version`, {}));
        this.tools.set('get_resource_metadata', (params) => this.callManifestGet(`/client/resource/${params.resource_id}/metadata`, {}));
        this.tools.set('get_resource_tickets', (params) => this.callManifestGet(`/client/resource/${params.resource_id}/ticket`, {}));

        // --- Ticket Tools ---
        this.tools.set('get_tickets', this.callManifestGet.bind(this, '/client/ticket'));
        this.tools.set('get_ticket_by_id', (params) => this.callManifestGet(`/client/ticket/${params.id}`, {}));
        this.tools.set('search_tickets', this.callManifestGet.bind(this, '/client/ticket/search'));

        // --- Incident Tools ---
        this.tools.set('get_incidents', this.callManifestGet.bind(this, '/client/incident'));
        this.tools.set('get_incident_by_id', (params) => this.callManifestGet(`/client/incident/${params.id}`, {}));
        this.tools.set('search_incidents', this.callManifestGet.bind(this, '/client/incident/search'));
        this.tools.set('get_incident_changelogs', (params) => this.callManifestGet(`/client/incident/${params.id}/changelogs`, {}));
        this.tools.set('get_incident_curated', (params) => this.callManifestGet(`/client/incident/${params.id}/curated`, {}));

        // --- Changelog Tools ---
        this.tools.set('get_changelogs', this.callManifestGet.bind(this, '/client/changelog'));
        this.tools.set('get_changelog_by_id', (params) => this.callManifestGet(`/client/changelog/${params.id}`, {}));
        this.tools.set('search_changelogs', this.callManifestGet.bind(this, '/client/changelog/search'));
        this.tools.set('get_changelog_by_resource', (params) => this.callManifestGet(`/client/changelog/resource/${params.resource_id}`, {}));
        this.tools.set('get_changelog_list_by_resource', (params) => this.callManifestGet(`/client/changelog/resource/${params.resource_id}/list`, {}));

        // --- Notification Tools ---
        this.tools.set('get_notifications', this.callManifestGet.bind(this, '/client/notification'));
        this.tools.set('get_notification_by_id', (params) => this.callManifestGet(`/client/notification/${params.id}`, {}));
        this.tools.set('get_notification_rule', (params) => this.callManifestGet(`/client/notification/rule/${params.ruleId}`, {}));
        this.tools.set('get_notifications_by_resource', (params) => this.callManifestGet(`/client/notification/resource/${params.rid}`, {}));

        // --- Graph Tools ---
        this.tools.set('get_graph_nodes', this.callManifestGet.bind(this, '/client/graph'));
        this.tools.set('create_graph_link', (params) => this.callManifestPost('/client/graph', params));
        this.tools.set('execute_graph_cypher', (params) => this.callManifestPost('/client/graph/cypher', { cypher: params.cypher }));

        // --- Observability Tools ---
        this.tools.set('query_logs', this.queryLogs.bind(this));
        this.tools.set('query_metrics', this.queryMetrics.bind(this));
    }

    getAvailableTools() {
        return Object.values(MCP_TOOLS);
    }

    async executeTool(toolName, parameters) {
        if (!this.tools.has(toolName)) {
            throw new Error(`Tool '${toolName}' not found`);
        }
        console.log(`🔨 Executing: ${toolName}`, JSON.stringify(parameters));
        return await this.tools.get(toolName)(parameters);
    }

    // --- GENERIC API HELPERS ---

    async callManifestGet(endpoint, params) {
        try {
            console.log(`📡 GET ${MANIFEST_API_URL}${endpoint}`, params);
            const response = await axios.get(`${MANIFEST_API_URL}${endpoint}`, {
                headers: {
                    'Mit-Api-Key': MANIFEST_API_KEY,
                    'Mit-Org-Key': MANIFEST_ORG_KEY,
                    'Accept': 'application/json'
                },
                params: params, // Axios automatically serializes this object
                timeout: 30000
            });
            return response.data;
        } catch (error) {
            console.error(`❌ API Error ${endpoint}:`, error.message);
            // Return safe error object so Agent doesn't crash
            return {
                success: false,
                error: error.response?.data?.message || error.message,
                status: error.response?.status
            };
        }
    }

    async callManifestPost(endpoint, body) {
        try {
            console.log(`📡 POST ${MANIFEST_API_URL}${endpoint}`, body);
            const response = await axios.post(`${MANIFEST_API_URL}${endpoint}`, body, {
                headers: {
                    'Mit-Api-Key': MANIFEST_API_KEY,
                    'Mit-Org-Key': MANIFEST_ORG_KEY,
                    'Content-Type': 'application/json'
                },
                timeout: 30000
            });
            return response.data;
        } catch (error) {
            console.error(`❌ API Error ${endpoint}:`, error.message);
            return {
                success: false,
                error: error.response?.data?.message || error.message,
                status: error.response?.status
            };
        }
    }

    // --- OBSERVABILITY IMPLEMENTATIONS ---

    async queryLogs(params) {
        const { query, limit = 1000 } = params;
        try {
            const response = await axios.get(`${VICTORIA_LOGS_API_URL}/query`, {
                params: { query, limit },
                timeout: 30000
            });
            // Handle NDJSON
            if (typeof response.data === 'string') {
                const lines = response.data.trim().split('\n');
                return { logs: lines.map(l => { try { return JSON.parse(l); } catch (e) { return null; } }).filter(l => l) };
            }
            return { logs: response.data };
        } catch (error) {
            return { success: false, error: `VictoriaLogs Error: ${error.message}` };
        }
    }

    async queryMetrics(params) {
        const { query, start, end, step } = params;
        try {
            const response = await axios.get(`${VICTORIA_METRICS_SELECT_URL}/select/0/prometheus/api/v1/query_range`, {
                params: { query, start, end, step },
                timeout: 30000
            });
            return response.data;
        } catch (error) {
            return { success: false, error: `VictoriaMetrics Error: ${error.message}` };
        }
    }
}

// ============================================================================
// 4. SERVER SETUP
// ============================================================================

const mcpRegistry = new MCPToolRegistry();
app.use(express.json());

// Discovery Endpoint
app.get('/api/mcp/tools', (req, res) => {
    res.json({ tools: mcpRegistry.getAvailableTools() });
});

// Execution Endpoint
app.post('/api/mcp/execute', async (req, res) => {
    try {
        const { tool_name, parameters } = req.body;
        if (!tool_name) return res.status(400).json({ error: 'tool_name required' });

        const result = await mcpRegistry.executeTool(tool_name, parameters || {});
        res.json({ success: true, result });
    } catch (error) {
        console.error('Execution Error:', error);
        res.status(500).json({ success: false, error: error.message });
    }
});

// Health Check
app.get('/api/health', (req, res) => {
    res.json({ status: 'healthy', version: '2.0.0', service: 'Tools Sidecar' });
});

app.listen(PORT, () => {
    console.log(`🚀 Tools Microservice running on port ${PORT}`);
    console.log(`🔗 Manifest API Target: ${MANIFEST_API_URL}`);
});