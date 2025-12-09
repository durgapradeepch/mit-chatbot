/**
 * Configuration for Tools Microservice
 * Loads settings from environment variables
 */

// Parse NEO4J_CONFIG from environment (JSON string)
let neo4jConfig = null;
if (process.env.NEO4J_CONFIG) {
    try {
        neo4jConfig = JSON.parse(process.env.NEO4J_CONFIG);
    } catch (e) {
        console.warn('Failed to parse NEO4J_CONFIG:', e.message);
    }
}

module.exports = {
    // Server Configuration
    SERVER_PORT: process.env.SERVER_PORT || 3001,

    // Manifest API Configuration
    MANIFEST_API_URL: process.env.MANIFEST_API_URL,
    MANIFEST_API_KEY: process.env.MANIFEST_API_KEY,
    MANIFEST_ORG_KEY: process.env.MANIFEST_ORG_KEY,
    MANIFEST_ORG_ID: process.env.MANIFEST_ORG_ID,

    // Neo4j Configuration
    NEO4J_CONFIG: neo4jConfig,

    // VictoriaMetrics & VictoriaLogs Configuration
    VICTORIA_METRICS_SELECT_URL: process.env.VICTORIA_METRICS_SELECT_URL,
    VICTORIA_LOGS_URL: process.env.VICTORIA_LOGS_URL,
};
