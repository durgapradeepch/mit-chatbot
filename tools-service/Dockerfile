# Use lightweight Node.js image
FROM node:18-alpine

# Set working directory
WORKDIR /app

# Install dependencies first (better caching)
COPY package.json .
RUN npm install --production

# Copy source code
COPY server.js .
COPY config.js* ./

# Expose the API port
EXPOSE 3001

# Start the server
CMD ["node", "server.js"]
