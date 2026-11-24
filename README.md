# Procurement Extraction Pipeline

This service downloads a PDF from an HTTPS URL, extracts procurement text, asks an OpenAI-compatible model to produce the five-agent JSON payload, validates it, and POSTs the result to a downstream webhook.

## Setup

1. Install Node.js 20 or newer.
2. Run `npm install`.
3. Copy `.env.example` to `.env` and configure `OPENAI_API_KEY`, `DOWNSTREAM_WEBHOOK_URL`, and the webhook secrets.
4. Start with `npm start`.

## Webhook

Send an HTTP `POST` to `/v1/extract`:

```json
{
  "pdfUrl": "https://example.com/procurement.pdf",
  "callbackId": "optional-customer-reference"
}
```

Set `INBOUND_WEBHOOK_TOKEN` to require `Authorization: Bearer <token>`.

The service returns immediately with a job ID and processes it in the background:

```json
{
  "jobId": "uuid",
  "status": "queued"
}
```

Poll `GET /v1/jobs/:jobId`.

On success or blocked extraction, the downstream webhook receives:

- `jobId`
- `callbackId`
- `sourceUrl`
- `result`
- `error` (only on failure)

Set `DOWNSTREAM_WEBHOOK_TOKEN` to send `Authorization: Bearer <token>`.

## Health

`GET /health` returns service health and queue configuration.

## Deployment

- Build and run the container:

  ```sh
  docker build -t procurement-pipeline .
  docker run --env-file .env -p 3000:3000 procurement-pipeline
  ```

- Run behind HTTPS with a process manager or container platform.
- Set secrets through the hosting provider, never in source control.
- Add a persistent database and signed queue before high-volume production use.
- The current in-memory job store does not survive restarts; it is not a durable queue.
- Use an HTTPS PDF host and DNS allowlisting appropriate for your organization.
