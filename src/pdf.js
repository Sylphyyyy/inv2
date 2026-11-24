import pdfParse from "pdf-parse";

export function validatePdfUrl(rawUrl) {
  let url;
  try {
    url = new URL(rawUrl);
  } catch {
    throw new Error("pdfUrl must be a valid absolute URL");
  }
  if (url.protocol !== "https:") {
    throw new Error("pdfUrl must use HTTPS");
  }
  if (url.username || url.password) {
    throw new Error("pdfUrl must not contain credentials");
  }
  return url;
}

export async function downloadAndExtractPdf(pdfUrl, options = {}) {
  const maxBytes = options.maxBytes ?? 20 * 1024 * 1024;
  const timeoutMs = options.timeoutMs ?? 30_000;
  const url = validatePdfUrl(pdfUrl);

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  let response;
  try {
    response = await fetch(url, {
      redirect: "error",
      signal: controller.signal,
      headers: { Accept: "application/pdf,*/*" }
    });
  } finally {
    clearTimeout(timeout);
  }

  if (!response.ok) {
    throw new Error(`PDF download failed with HTTP ${response.status}`);
  }

  const contentLength = Number(response.headers.get("content-length") || 0);
  if (contentLength > maxBytes) {
    throw new Error(`PDF exceeds the ${maxBytes}-byte limit`);
  }

  const arrayBuffer = await response.arrayBuffer();
  if (arrayBuffer.byteLength > maxBytes) {
    throw new Error(`PDF exceeds the ${maxBytes}-byte limit`);
  }

  const contentType = (response.headers.get("content-type") || "").toLowerCase();
  if (!contentType.includes("pdf") && !url.pathname.toLowerCase().endsWith(".pdf")) {
    throw new Error("Downloaded resource is not identified as a PDF");
  }

  const parsed = await pdfParse(Buffer.from(arrayBuffer));
  const text = (parsed.text || "").trim();
  if (!text) {
    throw new Error("The PDF contains no extractable text; scanned-PDF OCR is not yet enabled");
  }

  return {
    text,
    pageCount: parsed.numpages || null
  };
}
