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
// 2. TOOL DEFINITIONS (Schema) - Optimized for LLM Tool Selection
// ============================================================================
const MCP_TOOLS = {
    // --- RESOURCES ---
    get_resources: {
        name: "get_resources",
        description: "List ALL resources in the inventory without keyword filtering. Use ONLY when the user asks to 'list everything' or 'browse all resources'. For specific names or types, use 'search_resources' instead.",
        inputSchema: {
            type: "object",
            properties: {
                page: { type: "integer", default: 1, description: "Page number for pagination" },
                page_size: { type: "integer", default: 20, description: "Number of items per page" }
            }
        }
    },
    get_resource_by_id: {
        name: "get_resource_by_id",
        description: "Retrieve a SINGLE resource by its exact alphanumeric Resource ID (rid). Use this when you have a specific ID (e.g. 'gke-cluster-1') from a previous search. Do NOT use for searching by name.",
        inputSchema: {
            type: "object",
            properties: {
                rid: { type: "string", required: true, description: "Exact Resource ID (e.g., 'i-0123456789', 'gke-prod-cluster')" }
            },
            required: ["rid"]
        }
    },
    search_resources: {
        name: "search_resources",
        description: "PRIMARY RESOURCE FINDER. Use this to find resources by name, type, provider, or status. Supports partial keyword matching. Use for queries like 'find cart service', 'show aws buckets', 'list critical resources', or 'check status of X'.",
        inputSchema: {
            type: "object",
            properties: {
                query: { type: "string", description: "General search keyword - searches name, account, and subtype fields" },
                name: { type: "string", description: "Filter by exact or partial resource name" },
                id: { type: "string", description: "Filter by resource ID substring" },
                status: { type: "string", description: "Filter by status (e.g., 'Active', 'Terminated', 'Running')" },
                provider_key: { type: "string", description: "Cloud provider key (e.g., 'aws', 'gcp', 'azure', 'kubernetes')" },
                type: { type: "string", description: "Resource type (e.g., 'Pod', 'EC2Instance', 'GKECluster', 'S3Bucket')" },
                created: { type: "string", description: "Resources created after this ISO date (e.g., '2024-01-01')" },
                updated: { type: "string", description: "Resources updated after this ISO date" },
                category: { type: "string", description: "Broad category (e.g., 'Compute', 'Database', 'Storage', 'Network')" },
                sub_type: { type: "string", description: "Specific subtype (e.g., 'GKE-Cluster', 'RDS-MySQL')" },
                severity: { type: "string", description: "Criticality level (e.g., 'High', 'Medium', 'Low', 'Critical')" },
                watch_level: { type: "string", description: "Monitoring priority level" },
                app_id: { type: "string", description: "Filter by associated Application ID" },
                sortBy: { type: "string", enum: ["updated_at", "provider_key", "watch_level", "resourceType", "resourceName", "resourceId", "resourceStatus", "criticality"], description: "Field to sort results by" },
                direction: { type: "string", enum: ["asc", "desc"], description: "Sort direction: ascending or descending" },
                page: { type: "integer", default: 1 },
                page_size: { type: "integer", default: 20 }
            }
        }
    },

    // --- TICKETS ---
    get_tickets: {
        name: "get_tickets",
        description: "List ALL tickets/service requests without filtering. Use only for broad browsing. For filtering by status, priority, or searching text, use 'search_tickets' instead.",
        inputSchema: {
            type: "object",
            properties: {
                page: { type: "integer", default: 1, description: "Page number" },
                page_size: { type: "integer", default: 20, description: "Items per page" }
            }
        }
    },
    get_ticket_by_id: {
        name: "get_ticket_by_id",
        description: "Retrieve a specific ticket by its numeric ID. Use when the user provides an exact ticket number like 'ticket #1234' or 'show me ticket 5678'.",
        inputSchema: {
            type: "object",
            properties: {
                id: { type: "integer", required: true, description: "Numeric Ticket ID (e.g., 1234)" }
            },
            required: ["id"]
        }
    },
    search_tickets: {
        name: "search_tickets",
        description: "Search tickets by content or filter by status/priority. Use for queries like 'open high priority tickets', 'tickets about database', 'issues created yesterday', or 'pending tickets'.",
        inputSchema: {
            type: "object",
            properties: {
                query: { type: "string", description: "Text search across title, description, and status fields" },
                title: { type: "string", description: "Filter by title text" },
                status: { type: "string", description: "Filter by status (e.g., 'open', 'closed', 'pending', 'in_progress')" },
                description: { type: "string", description: "Filter by description text" },
                severity: { type: "string", description: "Filter by severity level" },
                source: { type: "string", description: "Source system (e.g., 'Jira', 'ServiceNow', 'Zendesk')" },
                created_before: { type: "string", description: "Tickets created before this ISO date" },
                created: { type: "string", description: "Tickets created after this ISO date" },
                id: { type: "string", description: "Filter by ticket ID substring" },
                sortBy: { type: "string", enum: ["updated_at", "title", "type", "priority", "status"], description: "Sort field" },
                direction: { type: "string", enum: ["asc", "desc"], description: "Sort direction" },
                page: { type: "integer", default: 1 },
                page_size: { type: "integer", default: 20 }
            }
        }
    },

    // --- INCIDENTS ---
    get_incidents: {
        name: "get_incidents",
        description: "List ALL incidents without filtering. Use only for broad browsing. To find specific incidents or filter by status/severity, use 'search_incidents' instead.",
        inputSchema: {
            type: "object",
            properties: {
                page: { type: "integer", default: 1, description: "Page number" },
                page_size: { type: "integer", default: 20, description: "Items per page" }
            }
        }
    },
    get_incident_by_id: {
        name: "get_incident_by_id",
        description: "Retrieve details for a single incident by its ID string. Use when you have a specific incident ID from a previous search.",
        inputSchema: {
            type: "object",
            properties: {
                id: { type: "string", required: true, description: "Incident ID string" }
            },
            required: ["id"]
        }
    },
    search_incidents: {
        name: "search_incidents",
        description: "Search and filter incidents. PRIMARY INCIDENT FINDER. Use for queries like 'show active critical incidents', 'incidents related to payment service', 'recent outages', 'high severity alerts', or 'open incidents'.",
        inputSchema: {
            type: "object",
            properties: {
                query: { type: "string", description: "Text search across title, description, and triggered_by fields" },
                title: { type: "string", description: "Filter by title text" },
                status: { type: "string", description: "Filter status (e.g., 'New', 'Investigating', 'Resolved', 'Closed')" },
                severity: { type: "string", description: "Filter severity (e.g., 'High', 'Medium', 'Low', 'Critical')" },
                source: { type: "string", description: "Monitoring source (e.g., 'Datadog', 'CloudWatch', 'Internal')" },
                created_before: { type: "string", description: "Incidents created before this ISO date" },
                created: { type: "string", description: "Incidents created after this ISO date" },
                sortBy: { type: "string", enum: ["updated_at", "title", "priority", "status"], description: "Sort field" },
                direction: { type: "string", enum: ["asc", "desc"], description: "Sort direction" },
                page: { type: "integer", default: 1 },
                page_size: { type: "integer", default: 20 }
            }
        }
    },

    // --- CHANGELOGS ---
    get_changelogs: {
        name: "get_changelogs",
        description: "List the global history of changes (deployments, config updates, infrastructure modifications) across the entire organization. Use 'search_changelogs' for filtering specific changes.",
        inputSchema: {
            type: "object",
            properties: {
                page: { type: "integer", default: 1, description: "Page number" },
                page_size: { type: "integer", default: 20, description: "Items per page" }
            }
        }
    },
    get_changelog_by_id: {
        name: "get_changelog_by_id",
        description: "Retrieve a specific changelog entry by its ID.",
        inputSchema: {
            type: "object",
            properties: {
                id: { type: "string", required: true, description: "Changelog ID" }
            },
            required: ["id"]
        }
    },
    search_changelogs: {
        name: "search_changelogs",
        description: "Search change history to find 'who changed what and when'. Use for queries like 'recent deployments', 'changes to cart service', 'config updates yesterday', or 'who modified the database'.",
        inputSchema: {
            type: "object",
            properties: {
                severity: { type: "string", description: "Filter by change severity/impact level" },
                provider_key: { type: "string", description: "Source provider (e.g., 'github', 'aws', 'terraform', 'argocd')" },
                description: { type: "string", description: "Text search in change description" },
                created: { type: "string", description: "Changes after this ISO date" },
                created_before: { type: "string", description: "Changes before this ISO date" },
                provider_config_id: { type: "integer", description: "Filter by provider configuration ID" },
                doneByUser: { type: "boolean", description: "True for human-initiated changes, False for automated/system changes" },
                query: { type: "string", description: "General search query across all text fields" },
                category: { type: "string", description: "Change category" },
                type: { type: "string", description: "Change type" },
                event_type: { type: "string", description: "Specific event type (e.g., 'deployment', 'pull_request', 'config_change')" },
                changeType: { type: "string", description: "Type of change operation" },
                changeAction: { type: "string", description: "Action performed (e.g., 'create', 'update', 'delete')" },
                application_id: { type: "integer", description: "Filter by application ID" },
                sortBy: { type: "string", enum: ["create_date", "provider_key", "severity"], description: "Sort field" },
                direction: { type: "string", enum: ["asc", "desc"], description: "Sort direction" },
                page: { type: "integer", default: 1 },
                page_size: { type: "integer", default: 20 }
            }
        }
    },

    // --- NOTIFICATIONS ---
    get_notifications: {
        name: "get_notifications",
        description: "Retrieve a list of alerts and notifications from monitoring systems. Use for queries like 'show my alerts', 'recent notifications', or 'what alerts fired today'.",
        inputSchema: {
            type: "object",
            properties: {
                page: { type: "integer", default: 1, description: "Page number" },
                page_size: { type: "integer", default: 20, description: "Items per page" }
            }
        }
    },

    // --- GRAPH (Topology & Dependencies) ---
    get_graph_nodes: {
        name: "get_graph_nodes",
        description: "Retrieve topology data showing nodes and their relationships/dependencies. Use to understand service connections, infrastructure maps, or 'what depends on X'. Good for architecture and dependency questions.",
        inputSchema: {
            type: "object",
            properties: {
                key: { type: "string", description: "Node key to center the graph around" },
                provider_key: { type: "string", description: "Filter by cloud provider" },
                providerConfigurationId: { type: "string", description: "Provider configuration ID" },
                resourceType: { type: "string", description: "Filter graph by resource type (e.g., 'Service', 'Pod', 'Database')" },
                resourceSubType: { type: "string", description: "Filter by specific resource subtype" },
                watch_level: { type: "string", description: "Filter by monitoring priority" },
                mitResourceId: { type: "string", description: "Center graph around this specific Resource ID" },
                depth: { type: "string", description: "Traversal depth - how many levels of connections to return" },
                skip: { type: "string", description: "Number of nodes to skip (pagination)" },
                take: { type: "string", description: "Number of nodes to return" },
                nextNodeId: { type: "string", description: "Cursor for next page of nodes" },
                nextRelationshipId: { type: "string", description: "Cursor for next page of relationships" },
                applicationId: { type: "string", description: "Filter by application ID" }
            }
        }
    },
    create_graph_link: {
        name: "create_graph_link",
        description: "Create a relationship/link between two nodes in the graph. Use to establish dependencies or connections between resources.",
        inputSchema: {
            type: "object",
            properties: {
                fromKey: { type: "string", required: true, description: "Source node key" },
                toKey: { type: "string", required: true, description: "Target node key" },
                relationship: { type: "string", description: "Relationship type (e.g., 'DEPENDS_ON', 'CONNECTS_TO')" }
            },
            required: ["fromKey", "toKey"]
        }
    },
    execute_graph_cypher: {
        name: "execute_graph_cypher",
        description: "Execute a raw Cypher query against the Neo4j graph database. Use ONLY for complex relationship questions that standard tools cannot answer. Requires valid Cypher syntax.",
        inputSchema: {
            type: "object",
            properties: {
                cypher: { type: "string", required: true, description: "Valid Cypher query string (e.g., 'MATCH (n:Service)-[:DEPENDS_ON]->(m) RETURN n, m')" }
            },
            required: ["cypher"]
        }
    },

    // --- OBSERVABILITY (Logs & Metrics) ---
    query_logs: {
        name: "query_logs",
        description: "Search text logs using LogSQL syntax. Use for finding error messages, exceptions, stack traces, or specific log patterns. Good for queries like 'show errors from cart service', 'find timeout logs', or 'logs containing OutOfMemory'.",
        inputSchema: {
            type: "object",
            properties: {
                query: { type: "string", required: true, description: "LogSQL query (e.g., 'error AND service:cart', 'level:error', 'OutOfMemoryError')" },
                limit: { type: "integer", default: 1000, description: "Maximum number of log entries to return" }
            },
            required: ["query"]
        }
    },
    query_metrics: {
        name: "query_metrics",
        description: "Query numerical time-series metrics using PromQL. Use for CPU usage, memory, request rates, latency, or any numeric monitoring data. Good for queries like 'CPU usage of cart service', 'request rate last hour', or 'memory utilization'.",
        inputSchema: {
            type: "object",
            properties: {
                query: { type: "string", required: true, description: "PromQL query (e.g., 'sum(rate(http_requests_total[5m]))', 'container_cpu_usage_seconds_total')" },
                start: { type: "string", description: "Start timestamp (ISO format or relative like '-1h')" },
                end: { type: "string", description: "End timestamp (ISO format or 'now')" },
                step: { type: "string", description: "Query resolution step interval (e.g., '1m', '5m', '1h')" }
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
        this.tools.set('execute_graph_cypher', this.executeNeo4jCypher.bind(this));

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
            // STRICT HEADER DEFINITION
            // We define this explicitly to prevent lowercase normalization issues with WAF
            const headers = {
                'Mit-Api-Key': MANIFEST_API_KEY,
                'Mit-Org-Key': MANIFEST_ORG_KEY,
                'Accept': 'application/json'
            };

            // If we have an Org ID, add it too (per WAF requirements)
            if (config.MANIFEST_ORG_ID) {
                headers['Mit-Org-ID'] = config.MANIFEST_ORG_ID;
            }

            console.log(`📡 GET ${MANIFEST_API_URL}${endpoint}`);
            console.log(`🔑 Headers:`, JSON.stringify(headers)); // Debug: verify casing is preserved

            const response = await axios.get(`${MANIFEST_API_URL}${endpoint}`, {
                headers: headers,
                params: params,
                timeout: 30000,
                validateStatus: (status) => status < 500 // Don't throw for 4xx, only 5xx
            });
            return response.data;
        } catch (error) {
            console.error(`❌ API Error ${endpoint}:`, error.message);
            if (error.response) {
                console.error(`   Status: ${error.response.status}`);
                console.error(`   Data:`, JSON.stringify(error.response.data));
            }
            return {
                success: false,
                error: error.response?.data?.message || error.message,
                status: error.response?.status
            };
        }
    }

    async callManifestPost(endpoint, body) {
        try {
            const headers = {
                'Mit-Api-Key': MANIFEST_API_KEY,
                'Mit-Org-Key': MANIFEST_ORG_KEY,
                'Content-Type': 'application/json'
            };

            if (config.MANIFEST_ORG_ID) {
                headers['Mit-Org-ID'] = config.MANIFEST_ORG_ID;
            }

            console.log(`📡 POST ${MANIFEST_API_URL}${endpoint}`);
            console.log(`🔑 Headers:`, JSON.stringify(headers));

            const response = await axios.post(`${MANIFEST_API_URL}${endpoint}`, body, {
                headers: headers,
                timeout: 30000
            });
            return response.data;
        } catch (error) {
            console.error(`❌ API Error ${endpoint}:`, error.message);
            if (error.response) {
                console.error(`   Status: ${error.response.status}`);
                console.error(`   Data:`, JSON.stringify(error.response.data));
            }
            return {
                success: false,
                error: error.response?.data?.message || error.message,
                status: error.response?.status
            };
        }
    }

    // --- NEO4J DIRECT QUERY ---

    async executeNeo4jCypher(params) {
        const { cypher } = params;
        if (!neo4jDriver) {
            return { success: false, error: 'Neo4j driver not initialized' };
        }
        const session = neo4jDriver.session();
        try {
            console.log(`🔷 Neo4j Cypher:`, cypher);
            const result = await session.run(cypher);
            const records = result.records.map(record => {
                const obj = {};
                record.keys.forEach(key => {
                    const value = record.get(key);
                    // Handle Neo4j Integer type
                    if (neo4j.isInt(value)) {
                        obj[key] = value.toNumber();
                    } else if (value && typeof value === 'object' && value.properties) {
                        // Handle Node/Relationship objects
                        obj[key] = { ...value.properties, _labels: value.labels };
                    } else {
                        obj[key] = value;
                    }
                });
                return obj;
            });
            return { success: true, data: records, count: records.length };
        } catch (error) {
            console.error(`❌ Neo4j Error:`, error.message);
            return { success: false, error: error.message };
        } finally {
            await session.close();
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