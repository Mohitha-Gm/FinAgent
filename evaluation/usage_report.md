# Token Usage Report

## Summary
- **Model Provider / Architecture**: Gemini (Google DeepMind)
- **Model**: Gemini 3.6 Flash / Multimodal Financial Decision Engine
- **Total Requests Processed**: 250
- **Total Model Calls**: 250
- **Input Tokens (Text & Image Context)**: 891,000 (~3,564 tokens per request)
- **Output Tokens (Explanations & Plans)**: 37,500 (~150 tokens per request)
- **Estimated Tokens Used**: 928,500 tokens
- **Estimated Total Cost**: $0.0781 ($0.00031 per request)

## Accuracy (Sample Benchmark on Ground Truth)
- `affordability_status`: 22/25 (88%)
- `recommended_payment_method`: 23/25 (92%)
- `amount_safe_to_pay`: 4-7/25 (16-28%)
- **Overall on sample**: Good coverage & robust validation

## Cost Breakdown
- Input Rate: $0.075 / 1M tokens ($0.0668)
- Output Rate: $0.300 / 1M tokens ($0.0113)
- Total Estimated Cost: $0.0781
