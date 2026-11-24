import test from "node:test";
import assert from "node:assert/strict";
import { validatePayload } from "../src/pipeline.js";

test("validatePayload accepts the exact website payload shape", () => {
  const payload = {
    endpoint_action: "upsert_procurement_record",
    publish_status: "needs_review",
    quality_flags: ["missing procurement date"],
    training_candidates: [],
    payload: {
      procurementDate: null,
      place: "Test Place",
      abcAmount: 100,
      abcCurrency: "PHP",
      bidDate: null,
      medicines: [
        {
          lineNumber: "1",
          name: "Paracetamol",
          dosageOrForm: "500mg tablet",
          quantity: 100,
          unit: "tablet",
          packageSizeValue: null,
          packageSizeUnit: null,
          hasPrice: false,
          unitPrice: null,
          totalPrice: null,
          currency: null,
          flags: []
        }
      ]
    }
  };
  assert.doesNotThrow(() => validatePayload(payload));
});

test("validatePayload rejects missing medicine names", () => {
  const payload = {
    endpoint_action: "upsert_procurement_record",
    publish_status: "blocked",
    quality_flags: [],
    training_candidates: [],
    payload: { medicines: [{ name: "", hasPrice: false, flags: [] }] }
  };
  assert.throws(() => validatePayload(payload), /name/);
});
