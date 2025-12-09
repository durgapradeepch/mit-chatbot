# Frontend API Contract - MIT AI Chat Agent

## Base URL

```
http://localhost:8000/agent
```

## Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/agent/invoke` | Synchronous invocation |
| `POST` | `/agent/stream` | Streaming response |
| `POST` | `/agent/stream_events` | Full event streaming (recommended) |
| `GET` | `/health` | Health check |

## Streaming Chat (Recommended)

**Endpoint:** `POST /agent/stream_events`

**Payload:**
```json
{
  "input": {
    "user_query": "What incidents are currently open?"
  }
}
```

**Response:** Server-Sent Events (SSE)

**Key Event:** `on_chat_model_stream`

## Integration Examples

### Using Fetch with SSE

```javascript
const response = await fetch('http://localhost:8000/agent/stream_events', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'text/event-stream'
  },
  body: JSON.stringify({
    input: { user_query: "your question here" }
  })
});

const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  console.log(decoder.decode(value));
}
```

### Using @langchain/core

```javascript
import { RemoteRunnable } from '@langchain/core/runnables/remote';

const chain = new RemoteRunnable({
  url: 'http://localhost:8000/agent'
});

for await (const chunk of await chain.stream({
  user_query: "your question here"
})) {
  console.log(chunk);
}
```

## Notes

- Uses standard LangGraph input/output schemas
- No custom adapters required
- CORS enabled for all origins
