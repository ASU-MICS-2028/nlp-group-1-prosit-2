# Lecture 3 (part 1): AI Innovation and Language Models

## In one paragraph
This session was a guest research talk with open Q&A, not a syllabus lecture. The main threads were: community-built AI, **model merging**, "languageless" large language models that keep reasoning and knowledge apart from language skills, modular models, **learning during inference** with evolutionary strategies, the difference between continual learning and lifelong learning, why LLMs "forget" between chats, and how the speaker uses AI tools in research. The transcript is garbled in places; some project names are unreadable.

## Key ideas, explained simply
- **Community-driven AI.** The speaker wants AI to be built by many contributors, not by one central company. Example: a crowd-sourced benchmark (name garbled) where people submit sentences machine translation gets wrong, plus rules to check translations.
- **Model merging.** Combine the parameters of two same-architecture models, each fine-tuned for a different task, into one model of the same size. A model is a non-linear function, so averaging weights should not work, but with "some tricks" it does: both tasks work, each slightly worse than its original. If people keep fine-tuning from the newest merged model, no limit was found; if all fine-tune once from the same old model, gains level off fast.
- **Languageless LLMs.** Small models (~100M parameters, ~100M training words) match huge models on syntax and simple semantics. So most parameters in big models must hold knowledge and reasoning, not language. The idea is to learn reasoning in one shared core and treat each language as a thin layer on top. The problem today: facts are not shared across languages. In one experiment the team duplicated English into two identical "copies" with the same tokens. Seeing a fact in the other copy was worth about 70 to 110 times less than seeing it in the same copy.
- **Tokens and compute.** An LLM predicts one token at a time. Languages that split into more tokens (or more Unicode bytes, as non-Latin scripts do) make the model use more compute for the same problem. Byte-level models do not fix this. A shared vector space (an "interlingua") could.
- **Modular models.** These would have swappable parts for reasoning, language, culture or a domain. A student noted more modules means a bigger attack surface; the speaker said modules also allow private parts. End-to-end training still usually wins.
- **Three ways to optimise.** Gradient descent is the most direct and the most sample-efficient, but costly. Reinforcement learning (RL) only gets a signal at the end, and the agent chooses its actions. Evolutionary strategies / genetic algorithms change the weights first, then check whether the change helped. They are the least sample-efficient.
- **Learning at inference with evolutionary strategies** (unpublished, under review). Most GPU use goes to inference anyway (the speaker said about 80% at one large provider). So: add tiny random noise to the weights on each server. One random seed describes the noise. Collect rewards (e.g. "the code ran without error"). Every ~1000 steps, keep noise that scored well on average. No extra compute, no latency, and (the speaker argued) no privacy issue, since only seeds and rewards are shared.
- **Continual vs lifelong learning.** Continual learning usually means fighting "catastrophic forgetting". Lifelong learning means always adding new knowledge. Some forgetting is fine if you learn more than you forget. An agent should learn most from the problems it actually meets.
- **Why chatbots "forget".** The weights never change after a conversation. "Memory" today is either the context window or saved prompts and facts. The speaker called saved-fact personalisation clumsy. Each session restarts from the same frozen model.
- **How the speaker uses AI.** LLMs are bad at writing final text but very good as a critic ("what is the weakest point of my paper?"). The speaker turned writing tips into a reusable Claude skill that critiques drafts, and used Claude Code to extend a game platform to ~100 languages: get one working, then have it check and verify the rest. They rarely use LLMs for new ideas.

## What the instructor said about assignments, deadlines, grading or expectations
After the talk the instructor called a five-minute break and said the class would come back "for the quiz". No quiz details were given.

## Relevance to Prosit 2
- **i Memory mechanisms:** the clearest link. Context-window memory and saved facts are not real learning, because weights stay frozen.
- **f Agentic AI / m Coding agents / p Self-reflection:** a coding agent can use reward signals such as "the code ran without error". This fits our Tester agent: run generated FastAPI code and feed errors back.
- **j RLHF / b Preference-based learning:** background on gradient descent vs RL vs evolutionary strategies.
- **k Privacy & security:** modular systems widen the attack surface but allow private parts.
- **d Prompt engineering:** use the LLM as a critic, and package repeated instructions as a reusable "skill".
- **l Human-in-the-loop:** The speaker does not trust LLM-written text without human checking.

## Likely quiz or viva questions
1. What is model merging? Combining the weights of two same-architecture models, each fine-tuned for a different task, into one model that does both, with each task slightly worse.
2. Why does an LLM forget what you told it in an earlier session? Its weights never change. "Memory" is just the context window or saved facts.
3. How do evolutionary strategies differ from RL? ES changes the weights first, then checks the reward. RL acts first, then updates from the reward. ES is the least sample-efficient.
4. What is a "languageless" LLM? A model whose knowledge and reasoning sit in a shared, language-independent core, with language as a thin layer on top.
5. Why do some languages cost more compute? They split into more tokens or bytes, and the model does one step per token.
6. Continual vs lifelong learning? Continual learning fights forgetting. Lifelong learning keeps adding new knowledge and accepts some forgetting.
