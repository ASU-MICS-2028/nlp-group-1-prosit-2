# Prosit 1 recap (for context)

Prosit 1, "Building and Adapting Language Models", had two parts:

1. **An Ewe language model.** A web corpus of 4.4M English–Ewe sentence pairs was cleaned down to 295k Ewe sentences: 77% duplicates, plus non-Ewe noise removed with an Ewe-letter filter. We then compared n-gram models (six smoothing methods, from add-k to modified Kneser-Ney) with an LSTM and a small Transformer trained from scratch. Finding: n-grams win below about 10,000 training sentences, neural models win above that. The best result was an LSTM at perplexity 46 on 100k sentences.
2. **Domain adaptation.** Qwen2.5-0.5B and SmolLM2-135M fine-tuned on health and agriculture text with LoRA, DoRA and full fine-tuning, plus a CPU-sized distilgpt2 + LoRA experiment.

Code: https://github.com/ASU-MICS-2028/nlp-group-1-prosit-1. Reports and slides: shared Drive, `NLP-GROUP-1/prosit 1/`.

## What carries over to Prosit 2

- **What earned credit:** comparing many options with real numbers (scaling curves, ablations, leaving out one cleaning step at a time), not just reporting one model. Prosit 2's rule 2 continues this.
- **Repo shape:** a README that says where everything is, results saved to files the report cites, fast tests of the core logic, and uv for setup.
- **Measurement care:** a metric is only meaningful with its conditions stated (for example, perplexity is only comparable with the same tokenizer). In Prosit 2 the equivalent is fixing the benchmark and hidden tests before tuning the agent, and running repeats because LLM output varies.
