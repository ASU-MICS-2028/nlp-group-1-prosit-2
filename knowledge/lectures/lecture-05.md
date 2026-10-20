# Lecture 5: Transformer Concepts and LLM Training

## In one paragraph
The instructor reviewed the core ideas of the transformer chapter (chapter 7) of Jurafsky and Martin's *Speech and Language Processing*. The math is left to the Deep Learning course. Topics: what a transformer is, attention, contextual embeddings, sampling, parallelism and positional embeddings, and why output tokens cost more than input tokens. The lecture then recapped pre-training and introduced instruction tuning (SFT), parameter-efficient fine-tuning (PEFT) and LoRA. Time ran out during the LoRA example.

## Key ideas, explained simply
- **Transformer.** A neural network architecture that generally performs best and is the backbone of state-of-the-art LLMs. Others mentioned: RNNs, CNNs, LSTMs, Mamba, feed-forward networks.
- **Attention.** Attention gives more weight to the words that matter most for the current prediction. In "The dog could not cross the street because it was too tired/wide", "tired" makes "it" the dog and "wide" makes it the street, so a good model attends most to that word (illustrative weight about 0.7). Attention weights are learned during training like other parameters.
- **Coreference resolution vs word sense disambiguation.** Coreference resolution means working out what a word like "it" refers back to. Word sense disambiguation means picking the right meaning of a word with several meanings, such as "model" (neural network or fashion model) in "The model was wearing a lovely dress".
- **Preprocessing must fit the task.** For example, lowercasing can lose the "shouting" signal of CAPITALS in sentiment analysis. Whatever tokenization you choose, use it the same way in training and at inference.
- **Static vs contextual embeddings.** An embedding is a vector that represents a token. A static embedding gives "bank" the same vector every time. A contextual embedding changes with the surrounding words, so "bank" next to "deposited money" gets a different vector from "bank" next to "river walk". Key principle: **better representations lead to better predictions.** Analogy: grayscale images suffice to tell a phone from a laptop, but colour images win when colour matters.
- **Output and sampling.** The model outputs a probability distribution over the next token; you sample from it. Greedy sampling always picks the most likely token. Top-k was also mentioned. Temperature moves sampling between two extremes: greedy at one end and almost uniform at the other.
- **Parallelism and positional embeddings.** Transformers process all tokens at the same time, not one after another like RNNs. That is why GPUs matter and why huge training runs are feasible. Because of this parallel processing, word order is not learned automatically. So each input is the **token embedding + positional embedding**.
- **Token pricing.** APIs charge per million input tokens and per million output tokens. Figures given (model names garbled in the transcript): about $4 in / $20 out, and $10 in / $50 out, per million tokens. Input is cheaper because the prompt is read in parallel. Output is dearer because generation is autoregressive (one token at a time). Even filler like "please" is billed.
- **Pre-training.** This is self-supervised learning. Part of the text is hidden and used as the label for the rest. No human labelling is needed, so models can be trained at internet scale.
- **Fine-tuning.** You continue training an already-trained model on new data with the same objective, next-token prediction.
- **Instruction tuning / SFT.** This is fine-tuning on pairs of instructions and answers. Examples: "Translate 'hello friend' to French" with its answer, or "Write a Python program that does X" with the code. It still uses next-token prediction. A base model may just continue the text plausibly (e.g. reply to a shoplifting question with another similar question); after SFT it follows the instruction. The aim is **generalization** to new variations, not **memorization** (like a student who memorized past quiz answers).
- **PEFT and LoRA.** Retraining every weight of a huge base model needs enormous compute and data. PEFT trains only a subset of parameters and still works well. LoRA (Low-Rank Adaptation) is one specific PEFT technique. The setup example went this far: input x = [3, 4, 9] (size 1×3) times a weight matrix W (size 3×2, so 6 parameters) gives h = xW (size 1×2) for 2 hidden units. **The lecture ended here.** The low-rank idea itself was not explained.

## What the instructor said about assignments, deadlines, grading or expectations
- The instructor will say by the weekend what happens on Tuesday (a student asked whether it means presentations).
- Students will use LLM APIs in their project, so they should understand token pricing.
- Some end-of-class remarks are too garbled to summarize.

## Relevance to Prosit 2
- **(a) Instruction tuning:** this lecture is the main source on SFT, PEFT and LoRA.
- **(m) Coding agents:** "Write a Python program that does X" was given as an SFT example.
- **(c) LLM alignment / (j) RLHF / (b) preference learning:** the shoplifting example motivates post-training. RLHF and preference methods were not covered in this lecture.
- **(d) Prompt engineering:** tokens cost money and output costs about 5× input. Keep agent prompts short and limit verbose outputs.
- **Platform:** a ReAct loop with Planner, Builder and Tester agents re-sends context on each step, so budget tokens and cap output length.

## Likely quiz or viva questions
1. **Why are output tokens priced higher than input tokens?** Input is processed in parallel, but output is generated one token at a time (autoregressively), which uses more compute.
2. **Why do transformers need positional embeddings?** They process tokens in parallel, so word order is lost unless position information is added to each token embedding.
3. **What is the difference between fine-tuning and instruction tuning?** Both continue next-token training. Instruction tuning uses instruction–answer pairs so the model learns to follow instructions.
4. **What is PEFT and why use it?** It trains only a subset of the parameters; full retraining is too costly. LoRA is one example.
5. **What does attention do?** It weights the most relevant words more heavily when making a prediction, for example "tired" when working out what "it" refers to.
