import "dotenv/config";
import express from "express";
import { randomUUID } from "node:crypto";
import multer from "multer";
import { downloadAndExtractPdf } from "./pdf.js";
import { createExtractionClient, extractProcurement } from "./pipeline.js";

const app = express();
app.disable("x-powered-by");
app.use(express.json({ limit: "1mb" }));

const port = Number(process.env.PORT || 3000);
const maxPdfBytes = Number(process.env.MAX_PDF_BYTES || 20 * 1024 * 1024);
const pdfTimeoutMs = Number(process.env.PDF_DOWNLOAD_TIMEOUT_MS || 30_000);
const jobs = new Map();
const inboundToken = process.env.INBOUND_WEBHOOK_TOKEN;
const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: maxPdfBytes },
  fileFilter: (_req, file, cb) => {
    const isPdfName = file.originalname?.toLowerCase().endsWith(".pdf");
    const isPdfType = file.mimetype === "application/pdf";
    cb(null, Boolean(isPdfName || isPdfType));
  }
});

let extractionClient;
try {
  extractionClient = createExtractionClient();
} catch (error) {
  console.error(error.message);
}

function requireInboundAuth(req, res, next) {
  if (!inboundToken) return next();
  const expected = `Bearer ${inboundToken}`;
  if (req.get("authorization") !== expected) {
    return res.status(401).json({ error: "Unauthorized" });
  }
  next();
}

app.get("/health", (_req, res) => {
  res.json({
    status: "ok",
    extractionConfigured: Boolean(extractionClient),
    downstreamConfigured: Boolean(process.env.DOWNSTREAM_WEBHOOK_URL),
    activeJobs: [...jobs.values()].filter((job) => job.status === "processing").length
  });
});

app.get("/v1/jobs/:jobId", (req, res) => {
  const job = jobs.get(req.params.jobId);
  if (!job) return res.status(404).json({ error: "Job not found" });
  res.json(job);
});

async function postToDownstream(job) {
  const webhookUrl = process.env.DOWNSTREAM_WEBHOOK_URL;
  if (!webhookUrl) return;

  let delivered = false;
  let lastError = null;

  for (let attempt = 1; attempt <= 3 && !delivered; attempt++) {
    try {
      const headers = { "content-type": "application/json" };
      if (process.env.DOWNSTREAM_WEBHOOK_TOKEN) {
        headers.authorization = `Bearer ${process.env.DOWNSTREAM_WEBHOOK_TOKEN}`;
      }

      const response = await fetch(webhookUrl, {
        method: "POST",
        headers,
        body: JSON.stringify({
          jobId: job.id,
          callbackId: job.callbackId,
          sourceUrl: job.sourceUrl,
          result: job.result,
          error: job.error || null
        }),
        signal: AbortSignal.timeout(30_000)
      });

      if (!response.ok) {
        throw new Error(`Downstream webhook returned HTTP ${response.status}`);
      }
      delivered = true;
    } catch (error) {
      lastError = error.message;
      if (attempt < 3) {
        await new Promise((resolve) => setTimeout(resolve, attempt * 1000));
      }
    }
  }

  job.downstreamDelivered = delivered;
  job.downstreamError = delivered ? null : lastError;
}

async function processJob(job) {
  job.status = "processing";
  job.startedAt = new Date().toISOString();

  try {
    // LLM/Gemini extraction disabled for webhook send/receive testing
    // const extracted = await downloadAndExtractPdf(job.sourceUrl, {
    //   maxBytes: maxPdfBytes,
    //   timeoutMs: pdfTimeoutMs
    // });
    // job.pageCount = extracted.pageCount;
    // job.result = await extractProcurement(extractionClient, extracted.text);
    job.pageCount = 1;
    job.result = {
      endpoint_action: "upsert_procurement_record",
      publish_status: "ready",
      quality_flags: [],
      training_candidates: [],
      payload: {
        procurementDate: null,
        place: null,
        abcAmount: null,
        abcCurrency: null,
        bidDate: null,
        medicines: []
      }
    };
    job.status = "completed";
  } catch (error) {
    job.status = "failed";
    job.error = error instanceof Error ? error.message : "Unknown extraction error";
  }

  job.completedAt = new Date().toISOString();
  await postToDownstream(job);
}

app.post("/v1/extract", requireInboundAuth, (req, res) => {
  const { pdfUrl, callbackId } = req.body || {};
  if (typeof pdfUrl !== "string" || !pdfUrl.trim()) {
    return res.status(400).json({ error: "pdfUrl is required" });
  }

  let parsedUrl;
  try {
    parsedUrl = new URL(pdfUrl);
  } catch {
    return res.status(400).json({ error: "pdfUrl must be a valid absolute URL" });
  }
  if (parsedUrl.protocol !== "https:" || parsedUrl.username || parsedUrl.password) {
    return res.status(400).json({ error: "pdfUrl must be HTTPS and contain no credentials" });
  }

  const job = {
    id: randomUUID(),
    status: "queued",
    callbackId: typeof callbackId === "string" ? callbackId : null,
    sourceUrl: pdfUrl,
    createdAt: new Date().toISOString(),
    result: null,
    error: null,
    downstreamDelivered: null
  };

  jobs.set(job.id, job);
  res.status(202).json({ jobId: job.id, status: "queued" });
  void processJob(job);
});

app.post(
  "/v1/extract/upload",
  requireInboundAuth,
  upload.single("file"),
  async (req, res) => {
    if (!req.file) {
      return res.status(400).json({ error: "A PDF file is required" });
    }
    if (!extractionClient) {
      return res.status(503).json({ error: "OPENAI_API_KEY is not configured" });
    }

    const callbackId = typeof req.body.callbackId === "string" ? req.body.callbackId : null;
    const job = {
      id: randomUUID(),
      status: "queued",
      callbackId,
      sourceUrl: null,
      createdAt: new Date().toISOString(),
      result: null,
      error: null,
      downstreamDelivered: null
    };
    jobs.set(job.id, job);

    try {
      // LLM/Gemini extraction disabled for webhook send/receive testing
      // const pdfParse = (await import("pdf-parse")).default;
      // const parsed = await pdfParse(req.file.buffer);
      // const text = (parsed.text || "").trim();
      // if (!text) {
      //   job.status = "failed";
      //   job.error = "The PDF contains no extractable text; scanned-PDF OCR is not yet enabled";
      //   job.completedAt = new Date().toISOString();
      //   await postToDownstream(job);
      //   return res.status(422).json({
      //     jobId: job.id,
      //     error: job.error
      //   });
      // }
      // const result = await extractProcurement(extractionClient, text);
      job.pageCount = 1;
      job.result = {
        endpoint_action: "upsert_procurement_record",
        publish_status: "ready",
        quality_flags: [],
        training_candidates: [],
        payload: {
          procurementDate: null,
          place: null,
          abcAmount: null,
          abcCurrency: null,
          bidDate: null,
          medicines: []
        }
      };
      job.status = "completed";
      job.completedAt = new Date().toISOString();
      await postToDownstream(job);
      res.json({
        jobId: job.id,
        callbackId,
        sourceName: req.file.originalname,
        pageCount: job.pageCount,
        result
      });
    } catch (error) {
      job.status = "failed";
      job.error = error instanceof Error ? error.message : "Extraction failed";
      job.completedAt = new Date().toISOString();
      await postToDownstream(job);
      res.status(502).json({
        jobId: job.id,
        error: job.error
      });
    }
  }
);

app.use((err, _req, res, _next) => {
  console.error(err);
  res.status(err.status || 500).json({ error: "Internal server error" });
});

export { app };
