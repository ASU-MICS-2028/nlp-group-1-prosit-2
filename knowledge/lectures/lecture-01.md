# Lecture 1: Introduction to NLP and Neural Networks

## In one paragraph
This was the first class. The instructor traced the path from the 1966 ELIZA chatbot to ChatGPT. Hand-written rules kept breaking, so the field moved to machine learning, then to huge neural networks powered by internet data, GPUs, the 2017 transformer and pre-training. He then covered grading and launched Prosit 1. The auto-generated transcript is garbled in places.

## Key ideas, explained simply
- **NLP:** computer systems that process (in a sense "understand") natural language. Natural language means any language not made for computers, so English or Twi, not Python. It also covers generation and speech.
- **Turing test:** if an observer cannot tell a human-machine chat from a human-human chat, the machine counts as intelligent.
- **Rule-based AI (ELIZA):** hand-coded response rules. They look clever but break easily.
- **Worked example, rule-based sentiment:** the class wrote `check_sentiment(sentence)`. It splits the sentence into words and checks them against a negative list (hate, not, sad) and a positive list (love, like, enjoy), else "neutral". It fails on mixed sentences and on "I don't hate jollof" (positive). Every new rule meets a case that breaks it.
- **Rule-based translation:** word-by-word swaps from a dictionary (a *lexicon*) give broken output. *Code-switching* (mixing languages, like saying "TV" in English inside Twi) is a research area.
- **Machine learning = learning from examples.** You write a *learning algorithm* and give it many labelled examples. It finds the patterns itself. A dataset in NLP is a **corpus** (plural **corpora**).
- **Neuron:** takes inputs x_i, each with a weight (importance) w_i, and outputs a **weighted sum**: `y = Σ_{i=1}^{3} x_i · w_i`. Example: predict student success from (attendance /100, assignments /10, yes/no factor). Student A is (50, 6, 1) and B is (60, 5, 1). Who does better depends on the weights, which are learned from past students' records.
- **Neural network:** many neurons connected, each output feeding the neurons ahead. The layered forward type is a **feed-forward network**. How the neurons are arranged is the **architecture**. Hidden neurons are a black box, but the predictions work.
- **Model = parameters.** A trained model is just its weights, a list of numbers. Figures looked up in class: about 175B (GPT-3.5) and 1.76T (GPT-4).
- **Deep learning:** adding neurons per layer makes a network wider, and adding layers makes it deeper. Neural networks faded after the 1980s but came back thanks to internet-scale data and GPUs (NVIDIA gaming chips that speed up training a lot).
- **Transformer (Google, 2017):** an architecture that does much of its work in parallel, so it trains fast on huge data.
- **Pre-training (self-supervised learning):** labelled data is scarce. So the model hides a word in unlabelled text and learns to predict it. The hidden word is a pseudo-label.
- **GPT = Generative Pre-trained Transformer.** OpenAI scaled transformers on web data and performance kept jumping (the "scaling laws" paper), leading to ChatGPT. Bigger models also need more data.
- **Language model:** predicts the next word. *Large* means billions of parameters or more. **High-resource** languages have lots of data and **low-resource** ones have little. **Fine-tuning** means further training an existing model for your task, because training from scratch costs billions.

## What the instructor said about assignments, deadlines, grading or expectations
- **Course:** three group Prosits at 10% each (30%), plus one quiz after each Prosit (weight not stated). The final project, on the group's own topic, is 40%. Start it early.
- **Topics:** Prosit 1 is building and adapting language models (first 3 weeks). Prosit 2 is **LLM agentic applications**. Prosit 3 is fine-tuning speech recognition.
- **Prosit 1 task:** as interns at a Ghanaian AI lab, build an N-gram model for a low-resource African language. Also build a domain-tuned English model (for example health). Show that both work.
- **Deliverables:** a public GitHub repo (code, experiments, evaluation scripts). Slides uploaded a day before presenting. An individual technical report. Each person submits the group's repo link on the viva platform (name garbled in the transcript; you sign in with Canvas).
- **Report:** Section A is individual. Answer guiding questions in your own words, within the stated paragraph counts, and always justify. Sections B and C are written by the group and cover the work and its evaluation.
- **Prosit grading:**

  | Part | Weight |
  |---|---|
  | Presentation (keep it technical, not a sales pitch) | 20% |
  | Technical report (B and C stated as 15% each) | 45% |
  | Viva quiz | 35% |

- **AI use:** expected and encouraged, but you must understand what it did. You are responsible for what you deploy. The viva quiz uses AI to read your code and write multiple-choice questions (4 options).
- **Section A voice:** the instructor prefers your own words, even if slightly less accurate. Tip: read, wait, then write without sources.

## Relevance to Prosit 2
- The lecture confirms Prosit 2 is about LLM agentic applications. One course goal is to design, build, evaluate and deploy LLM-based applications by calling LLM APIs, which is what our platform does.
- Section A: Little direct relevance to topics a–r. It gives background for **a (instruction tuning)** and **m (coding agents)** through pre-training, fine-tuning and transformers. It gives a short motivation for **l (human-in-the-loop)**: you are responsible for what your AI does.
- Build and viva: the viva questions are generated from our own repo, so every member must understand all of the code. The repo must be public.

## Likely quiz or viva questions
1. **What does a neuron compute?** A weighted sum of its inputs, y = Σ x_i · w_i.
2. **What is a model?** Its learned weights (parameters), which are just numbers.
3. **Why do rule-based systems fail?** New examples always break the rules (for example, "I don't hate jollof").
4. **What does GPT stand for, and why do transformers matter?** Generative Pre-trained Transformer. Transformers are highly parallel, so they can train on huge data.
5. **What is self-supervised pre-training?** Predicting hidden parts of unlabelled text, using the hidden part as a pseudo-label.
6. **What is fine-tuning?** Further training an already-trained model for a specific purpose.
