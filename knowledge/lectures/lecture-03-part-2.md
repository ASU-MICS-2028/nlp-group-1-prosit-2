# Lecture 3 (part 2): Understanding Neural Network Architectures

## In one paragraph
Post-training was the planned topic, but the session went back to basics instead: how a model turns words into meaningful vectors and learns them. One worked example ("I am going ___" → "to") covered one-hot input, hidden states, the output probability distribution, cross-entropy loss, backpropagation and gradient descent. The instructor then separated training from inference (where greedy and top-k sampling fit) and compared encoder-only (BERT), decoder-only (GPT-style) and encoder-decoder models. Post-training itself was not covered.

## Key ideas, explained simply
- **Token IDs carry no meaning.** Example: "The bag is blue" becomes IDs like 21, 46, 33, 25. These numbers are just labels. To do anything useful we need **vectors** (lists of numbers) that capture meaning.
- **Vectors live in a space.** With good vectors, words with similar meanings sit close together: king, queen and leader in one area, money and bank in another. Some dimensions can also capture grammar, such as plural vs. singular.
- **Word2Vec analogy (worked example).** With learned vectors, v(king) − v(man) + v(woman) ≈ v(queen). This is evidence that the vectors are good. (The transcript mis-hears "king" as "Kim"/"him".)
- **Vectors are learned through language modelling.** Hide the next word in real sentences and train a network to predict it. To do this well, it must build good representations of the earlier words.
- **One-hot encoding.** Each word is a vocabulary-sized vector with a single 1. Code uses plain IDs, which are one-hot in concept.
- **Hidden states and sequence encoding.** A network (RNN or Transformer) builds hidden states word by word, starting from zeros: "I" gives h, h plus "am" gives h′, h′ plus "going" gives h″, which represents the whole phrase. Turning words or sequences into vectors is **encoding**. Turning a vector back into language is **decoding**. In translation, English is encoded into vector space and decoded into French.
- **Output and maximum likelihood.** The model outputs a **probability distribution** over the vocabulary, not a token. A good model gives the correct answer high probability. If "to" gets only 0.01, the model is wrong.
- **Cross-entropy loss.** The ground truth is a distribution with 1 on "to" and 0 on everything else. Cross-entropy measures the gap between the model's distribution and that truth. Training pushes the probability of "to" up (0.01 → 0.1 → 0.2 …), and the loss goes down as it rises.
- **Gradient descent and backpropagation.** Weights are updated by adding the *negative* of the gradient of the loss (a gradient is like a derivative). **Backpropagation** is the algorithm that finds those gradients. The **forward pass** makes the prediction. Backprop plus gradient descent then adjusts the weights. This repeats many times. As the weights improve, the hidden-state vectors improve too.
- **Why update all weights, not just the decoder's?** The error may come from the encoder. Analogy: failing a quiz on React (the JavaScript library) may really be a gap in JavaScript. The model works out where to fix things.
- **Why not evaluate vectors directly?** No data says "this is the correct vector for this word". Vectors are judged through a grounded task, e.g. which candidate vector for "bad" makes "movie is bad" read more strongly negative.
- **Training vs. inference.** In training, only the probability distribution matters, compared with the ground truth. No sampling happens. In inference, we must pick a token from the distribution. **Greedy decoding** picks the highest-probability token, which can give repetitive output. **Top-k** samples from the k most likely tokens to add variety.
- **Decoding is a loop.** After "to", the context "I am going to" is used to predict "school", and so on.
- **Three architectures** (all map source text to prediction text):
  - *Encoder-decoder*: the encoder builds H and the decoder generates a sequence. Sequence-to-sequence, e.g. machine translation.
  - *Encoder-only* (e.g. BERT): encode, then a small classifier (an MLP) predicts a label, e.g. positive, negative or neutral sentiment.
  - *Decoder-only* (GPT-style, e.g. ChatGPT): no separate encoder. The input is used as context, and the model generates text. It still builds its own internal hidden states.
- **Encoders need not be bidirectional.** BERT (the "B" means bidirectional) was trained on left and right context with masked-word prediction. That worked better, but left-to-right encoders also exist.

Note: the auto-transcript is noisy in places. "Weights" appears as "dog use", "BERT" as "bed", and "encoder" as "Ikoda". Some student questions are only partly readable.

## What the instructor said about assignments, deadlines, grading or expectations
- The instructor noted that no one had submitted "the first one" (an earlier assignment) yet.
- Submissions must be **uploaded as a file**. Do not paste text in.
- The class should meet again on Thursday. The instructor asked students to confirm the meeting time. The details are unclear in the transcript.
- No grading criteria or dates.

## Relevance to Prosit 2
- **"ReAct" check:** every mention of "React" in this lecture means the **React JavaScript library**, used in a teaching analogy about backpropagation. The ReAct agent loop is **not** discussed.
- Background only; no Section A topic is covered directly. It gives the base for **a (instruction tuning)** and **j (RLHF)**: it explains the pretraining loss that post-training (the planned topic) builds on.
- For **d (prompt engineering)** and **m (coding agents)**: decoder-only LLMs use the prompt as context and generate token by token. Greedy decoding is more repeatable than top-k. Our inference (not stated in class): greedy-like settings may suit code and OpenAPI generation.
- For **e (RAG)**: the vector-similarity idea is the intuition behind embedding search.

## Likely quiz or viva questions
1. **What does a language model output at each step?** A probability distribution over the vocabulary, not a single token.
2. **What is cross-entropy loss here?** The gap between the predicted distribution and the one-hot ground truth. It falls as the correct token's probability rises.
3. **Backpropagation vs. gradient descent?** Backprop computes the gradients of the loss. Gradient descent updates the weights by adding the negative gradient.
4. **Where does top-k sampling happen?** Only at inference. Training uses the full distribution against the ground truth.
5. **Encoder-only vs. decoder-only vs. encoder-decoder?** BERT encodes and classifies. GPT uses the input as context and generates. Encoder-decoder maps a sequence to a sequence, e.g. translation.
