import OpenAI from "openai";

const EXTRACTION_SYSTEM_PROMPT = `You are an unattended procurement extraction pipeline.
Process the source text strictly and output ONLY a valid JSON object in the exact
Agent 5 website payload structure. Never invent or estimate data.

AGENT 1:
Extract procurementDate, place, ABC amount/currency, and bidDate.
Normalize dates to YYYY-MM-DD. Use null for missing values.

AGENT 2:
Identify every medicine or medical supply line item. Preserve exact original line
text in raw_description. Extract quantity and unit only when explicit. Extract
pack size only when explicit. Flag ambiguous dosage, unit, pack size, or quantity.

AGENT 3:
Extract unit/total price only if explicitly printed for that line item. Never
derive prices from ABC or quantities.

AGENT 4:
Merge records. Missing medicine list or corrupted core structure is blocked.
Core metadata missing alone is a warning, not necessarily blocked.

AGENT 5:
Use exactly this JSON shape:
{
  "endpoint_action": "upsert_procurement_record",
  "publish_status": "ready | needs_review | blocked",
  "quality_flags": ["string"],
  "training_candidates": [{"medicine_name":"string","raw_description":"string","reason":"string"}],
  "payload": {
    "procurementDate":"YYYY-MM-DD | null",
    "place":"string | null",
    "abcAmount":"number | null",
    "abcCurrency":"string | null",
    "bidDate":"YYYY-MM-DD | null",
    "medicines":[
      {
        "lineNumber":"string | number | null",
        "name":"string",
        "dosageOrForm":"string | null",
        "quantity":"number | null",
        "unit":"string | null",
        "packageSizeValue":"number | null",
        "packageSizeUnit":"string | null",
        "hasPrice":"boolean",
        "unitPrice":"number | null",
        "totalPrice":"number | null",
        "currency":"string | null",
        "flags":["string"]
      }
    ]
  }
}`;

export function createExtractionClient() {
  if (!process.env.OPENAI_API_KEY) {
    throw new Error("OPENAI_API_KEY is not configured");
  }

  return new OpenAI({
    apiKey: process.env.OPENAI_API_KEY,
    baseURL: process.env.OPENAI_BASE_URL || "https://api.openai.com/v1"
  });
}

export async function extractProcurement(client, sourceText) {
  if (!sourceText || !sourceText.trim()) {
    throw new Error("Extracted PDF text is empty");
  }

  const response = await client.chat.completions.create({
    model: process.env.OPENAI_MODEL || "gpt-4o-mini",
    temperature: 0,
    response_format: { type: "json_object" },
    messages: [
      { role: "system", content: EXTRACTION_SYSTEM_PROMPT },
      {
        role: "user",
        content: `TRAINING_EXAMPLES:\n[]\n\nACTIVE_RULES:\n[]\n\nRAW_PROCUREMENT_TEXT:\n${sourceText}`
      }
    ]
  });

  const content = response.choices[0]?.message?.content;
  if (!content) {
    throw new Error("The extraction model returned no content");
  }

  let result;
  try {
    result = JSON.parse(content);
  } catch {
    throw new Error("The extraction model returned invalid JSON");
  }

  validatePayload(result);
  return result;
}

export function validatePayload(result) {
  if (!result || typeof result !== "object" || Array.isArray(result)) {
    throw new Error("Extraction result must be an object");
  }
  if (result.endpoint_action !== "upsert_procurement_record") {
    throw new Error("Extraction result has an invalid endpoint_action");
  }
  if (!["ready", "needs_review", "blocked"].includes(result.publish_status)) {
    throw new Error("Extraction result has an invalid publish_status");
  }
  if (!Array.isArray(result.quality_flags) || !Array.isArray(result.training_candidates)) {
    throw new Error("Extraction result quality fields must be arrays");
  }
  if (!result.payload || !Array.isArray(result.payload.medicines)) {
    throw new Error("Extraction result payload is missing medicines");
  }

  for (const medicine of result.payload.medicines) {
    if (!medicine || typeof medicine.name !== "string" || !medicine.name.trim()) {
      throw new Error("Every extracted medicine must have a name");
    }
    if (typeof medicine.hasPrice !== "boolean") {
      throw new Error(`Medicine ${medicine.name} is missing hasPrice`);
    }
    if (!Array.isArray(medicine.flags)) {
      throw new Error(`Medicine ${medicine.name} flags must be an array`);
    }
  }
}
