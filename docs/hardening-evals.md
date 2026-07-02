# V1 Hardening Evals

Status: Draft
Created: 2026-07-02

This phase uses private ChatGPT export evidence to harden OCR and live-agent behavior without committing private diary data.

## Private Image Extraction

Extract embedded images from the private ChatGPT HTML export:

```bash
python scripts/extract_chatgpt_image_assets.py \
  "private/Health - Diário_ Nutrição e Perda de Peso.html"
```

Outputs stay ignored under `private/chatgpt-assets/`:

- `images/`: extracted JPEG/PNG/WebP files.
- `manifest.json`: hashes, dimensions, offsets, short redacted context, and `review_classification`.

Review `manifest.json` and classify useful images as:

- `nutrition_label`
- `meal_photo`
- `screenshot_other`
- `irrelevant`

Use the helper to classify selected image IDs:

```bash
python scripts/update_chatgpt_image_classification.py \
  --classification nutrition_label \
  chatgpt_image_045 chatgpt_image_044
```

## Private OCR Fixtures

Create one JSON file per reviewed nutrition label under `private/ocr-evals/`.

Example:

```json
{
  "id": "batavo_protein_label_001",
  "image_path": "../chatgpt-assets/images/chatgpt_image_001_abc123.jpg",
  "mime_type": "image/jpeg",
  "barcode": "7891000000000",
  "min_confidence": 0.35,
  "expected_text_contains": ["Iogurte", "Proteinas", "Porcao"]
}
```

Run private OCR evals:

```bash
PRIVATE_OCR_EVALS=true OLLAMA_VISION_MODEL=llava make test-private-ocr-evals
```

The test asks the configured Ollama vision model to extract label text, then feeds that text through the normal label proposal flow. It asserts proposal-grade output without applying any food-library mutation.

## ChatGPT-Derived Live-Agent Eval Candidates

Extract redacted eval candidates:

```bash
python scripts/extract_chatgpt_eval_candidates.py \
  "private/Health - Diário_ Nutrição e Perda de Peso.html" \
  --out private/evals/chatgpt-eval-candidates.jsonl
```

The generated JSONL is private and review-oriented. It groups prompts into:

- correction
- review note
- ambiguity or version reference
- weird meal phrasing
- restaurant or social estimate

Committed live evals live in `tests/live/evals/core_agent_cases.jsonl`. They assert invariants such as proposal-gated writes, visible confidence, and version-history grounding.

## Commands

Default deterministic gate:

```bash
make test
```

Local live-model gate:

```bash
LIVE_MODEL_TESTS=true LIVE_MODEL_NAME=ornith:9b make test-live-model
```

Private OCR gate:

```bash
PRIVATE_OCR_EVALS=true OLLAMA_VISION_MODEL=llava make test-private-ocr-evals
```

Cloud model comparison, opt-in only:

```bash
CLOUD_MODEL_CALLS_ENABLED=true CLOUD_MODEL_NAME=glm-5.2:cloud make test-cloud-evals
```

## Privacy Rule

Do not commit raw images, private manifests, private JSONL candidates, OCR eval JSON files, or generated eval reports. The repository commits only extraction tools, schemas, synthetic examples, and tests.
