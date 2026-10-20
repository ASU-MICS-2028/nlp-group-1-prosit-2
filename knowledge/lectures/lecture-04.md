# Lecture 4: LLM to Agentic AI Journey

> Source: an auto-summary plus a raw transcript that is often garbled. The course instructor launched Prosit 2. A second instructor (a guest) then taught information retrieval. Unclear parts are flagged.

## In one paragraph

Prosit 1 used LLMs only for next-token prediction. Prosit 2 asks how a next-token predictor ends up doing "magic", like building and deploying software from one sentence. The task is a platform where non-developers create backend APIs in natural language. The instructor also gave the report structure and grading weights. The second instructor then gave intuition for factoid questions, instruction tuning, hallucination and RAG. They also taught the basics of information retrieval: bag of words, the term-document matrix, weighting, log normalization, add-one, and the TF part of TF-IDF. IDF and BM25 were named but **not taught**. Students must read them in the textbook.

## How the instructor framed Prosit 2

- **Motivation**: tools like Lovable, Replit, v0 and Base44 build full apps (frontend, backend, database) from plain language. They are replacing drag-and-drop no-code tools. The instructor said Wix bought Base44 for about 80 million dollars. It was a one-person project about six months old.
- **Client**: "Mesura", an AI research company in Ghana that is interested in coding agents for web apps.
- **Client's design belief**: coding agents should follow **separation of concerns** and **modularity**. That means a separate frontend and backend that talk through a **well-defined API**. Modularity means each module does one job, so you can change one part without breaking the others.
- **Task**: a non-developer types in natural language and gets a set of **backend APIs**. They can keep **refining** it, and the system applies the changes.
- **Core question**: a base model given "build me a website using React" should just continue the text (e.g. "...use TypeScript"). Yet real systems write, build and deploy code. The Prosit is to **understand and implement** that jump.
- **Concepts to master** (topics a to r): instruction tuning, preference learning, alignment, prompting/CoT, RAG, agentic AI, multi-agent systems, reasoning and planning, memory, RLHF, privacy and security, human-in-the-loop, coding agents, the thought-action-observation loop **ReAct** ("not the React frontend framework"), tool use, decomposition and self-reflection, MCP, and orchestration.
- **Industry view**: most industry AI work, the instructor guessed 80 to 90 percent, is "using an LLM and doing something interesting on top of it". It is no longer about training your own model.
- **Hint**: last year's teams took many different approaches, and the instructor enjoyed the variety. "A lot of directions you can do."

## Key ideas, explained simply

**Experimental mindset**
- No theory gives you the right hyperparameters, so you try things. In one story, a student's model only trained once she found the right learning rate in an obscure online thread.
- **No free lunch**: gaining in one direction usually costs you in another.
- **Ablation study**: say you add techniques A, B and C, and the score goes from 80% to 90%. Remove them one at a time (and in combinations) to see what each one contributed.

**LLM terms**
- **Query**: what the user is searching for. **Factoid question**: asks for one specific fact with no opinion. Examples: "What is the capital of Ghana?" (Accra) and "How many letters are in the English alphabet?" (26).
- **Instruction tuning**: give a pre-trained model **instruction-output pairs**, e.g. `Question: What is the capital of Ghana? Answer: Accra`. This teaches it how to respond. Special markers (like start/end tokens) are stripped from the output. It is still next-word prediction: "nothing fancy is happening".
- **Prompting example (not real fine-tuning)**: for a Montessori app, the speaker transcribed a real conversation and had Claude generate similar samples. They then told the model to mimic that style. Tips:
  - Convert every modality to text, because "text is highly solved".
  - In engineering, define your own success metric. It does not have to be F1.
- **Hallucination**: confident but wrong output. Not all knowledge is on the web (private files, company databases, the unindexed web). Asked about private data, the model still produces fluent nonsense.
- **RAG**: give the LLM **external data** as a kind of external memory to answer from. The model already knows language. It lacks the specific facts in your PDF. This "sometimes, to a large extent" reduces hallucination. Variants such as graph RAG exist.
- **When not to use RAG**: retrieval adds **latency**. If the data is already public, the model may already know it, so test that first. "RAG is not always the best answer."
- NotebookLM-style idea (the speaker's guess, not the real design): PDF text, then LLM turns it into a conversation, then text-to-speech.

**Information retrieval (IR)**
- **IR**: retrieving any media based on a user's information need.
- **Ad hoc retrieval**: queries change, documents stay fixed (e.g. questions about fixed company policies, or a library). **The course focuses on this.**
- **Information filtering**: the reverse. The query is fixed and the documents change.
- **Document**: anything indexed and searched (a page, a paper, even a sentence). **Collection / corpus**: a set of documents.
- **Sparse retrieval**: word-count methods. **TF-IDF** is the classic one. **BM25** is "relatively newer".
- **Dense retrieval**: uses embeddings. The speaker said projects will "most likely" use dense retrieval. Only sparse retrieval was taught.
- The "-" in TF-IDF is a hyphen, not subtraction. TF-IDF = Term Frequency, Inverse Document Frequency.
- **Bag of words**: a document becomes an unordered set of words with their counts. Word position is ignored.
  - Example collection. Doc 1: "I hated the fact that the hero ... died in the end". Doc 2: "...it was a romantic movie. In fact it was a tragedy."
  - Across the collection, "I" appears 2 times and "hated" 1 time. A document's counts form its vector, so we can do arithmetic on text.
- **Term-document matrix**: counts of each term (unigrams here) in each document. Worked example with As You Like It, Twelfth Night, Julius Caesar and Henry V.
  - battle = 1, 0, 7, 13.
  - The other numbers are garbled. They read roughly as: good 114, 80, 62, 89; fool 36, 58, 1, 4; wit about 20, 15, 2, 3.
  - Confirmed later in the lecture: As You Like It has fool 36 and battle 1. Henry V has fool 4 and battle 13.
  - A row is a word's vector. A column is a document's vector.
- **Insight from raw counts**: lots of "fool" suggests As You Like It is a comedy, which it is. More "battle" suggests Henry V is darker. It is actually a history play, a class outside the "comedy vs tragedy" choice.
- **Distance vs ratio**: As You Like It gives |36 - 1| = 35, using the absolute value so distance is positive. Henry V gives |13 - 4| = 9. Ratios (36/1 vs 4/13) give different information.
- **Plotting**: plot each play as a point (fool, battle). As You Like It sits at (36, 1) and Henry V at (4, 13). More words give an n-dimensional space. Good embeddings carry more: similar words cluster together.
- **Weighting**: multiply by a coefficient to show relative importance. Example: education 70%, experience 30% in a hiring score. **Term weighting** does the same for words.
- **Normalization**: put values onto the same scale (e.g. 0 to 1) so they can be compared.
- **Log normalization**: shrinks outliers but keeps order and relative relationships.
  - log10(10) = 1, log10(10,000) = 4, log10(100,000) = 5, log10(1,000,000) = 6. The trick is to count the zeros.
  - Very common words ("is", "the") are too "loud", like a banana taking over a smoothie. The log quiets them while rare words keep a voice.
- **Add one**: log(0) is undefined, so add 1 first. Every value shifts by one and the order is unchanged. Analogy: give everyone 10 pesewas, and the richest person is still the richest. The speaker did not know why 1 rather than another number. (A convex/concave tangent was garbled and is not core.)
- **TF formula (as given):**

  $$\text{tf}_{t,d} = \begin{cases} 1 + \log_{10}\big(\text{count}(t,d)\big) & \text{if count}(t,d) > 0 \\ 0 & \text{otherwise} \end{cases}$$

  A term repeated in a document says something about it. A document full of "Q4" should come back for the query "Q4". (The speaker said TF covers "the entire collection", but the formula counts within one document d.)
- **Rest of the pipeline (sketched only)**:
  1. IDF is the other half of TF-IDF.
  2. TF-IDF scores are stored in an **inverted index**, so you don't rescan everything.
  3. The query is compared to documents with **cosine similarity** to find the most relevant ones.
  4. The **IDF and BM25 formulas were not given**. "Read up on the IDF part, BM25, and the actual RAG."

## What the instructor said about assignments, deadlines, grading or expectations

- **Section A** is written in your own words. Its goal is to show the company the journey from pre-trained LLMs to coding agents.
  - **3 to 5 pages in total** for all topics, not per topic.
  - **Tell a story** of how a pre-trained LLM becomes a coding agent, showing where each concept fits.
- **Section B** covers what you built, your choices and why, and evaluation. Learning outcomes come with the brief. The **rubric is the same** as Prosit 1.
- **Citations**: no need to cite general knowledge in your own words (e.g. what CoT is). Cite specific claims and results. Use quotes plus a citation for borrowed wording. Not every sentence needs a citation.
- **Weights**: Prosits 30% in total. The transcript is unclear, but it suggests that doing only two Prosits gets you graded out of 20 of the 30. Three quizzes 30%, which test theory and are "usually the most challenging". Final project 40%.
- **Prosit 1**: presentations and quizzes come once all submissions are in, aiming for Tuesday.
- **Prosit 2 duration**: garbled. It sounded like a default of three (weeks).

## Relevance to Prosit 2

- **Section A topics this lecture covers**:
  - (a) Instruction tuning: the Q/A-pair example.
  - (e) RAG: why hallucination happens, and the latency trade-off.
  - (d) Prompt engineering: the few-shot style example.
  - (f) Agentic AI and (m) coding agents: the "next token to magic" story.
  - (n) ReAct: named only. The other topics are listed but not explained.
- **Retrieval part**: the platform uses BM25. This lecture gives the building blocks: bag of words, term-document matrix, log-scaled TF with +1, inverted index and cosine ranking. Take the IDF/BM25 maths from the textbook. The speaker expected dense retrieval, so be ready to defend choosing BM25.
- **Architecture**: the client wants separation of concerns, modularity and a well-defined API contract. This matches FastAPI backends with an OpenAPI contract and separate Planner/Builder/Tester agents (orchestration, multi-agent).
- **Refinement**: the iterative refine loop is a stated requirement. It supports human-in-the-loop (l).

## Likely quiz or viva questions

1. **What is Prosit 2's central question?** How a next-token predictor becomes able to build software from a natural-language request.
2. **Which design principles does the client want coding agents to follow?** Separation of concerns and modularity: a separate frontend and backend joined by a well-defined API.
3. **What is instruction tuning?** Training a pre-trained model on instruction-output pairs so it learns how to respond to requests.
4. **Why do LLMs hallucinate on private data, and how does RAG help?** That data was never on the indexed web. RAG supplies it as external data at answer time.
5. **When is RAG a bad choice?** When the model already knows the information, because retrieval adds latency for no benefit.
6. **What is the difference between ad hoc retrieval and information filtering?** Ad hoc: queries change, documents are fixed. Filtering: the query is fixed, documents change.
7. **Give the TF formula and say why it uses a log and +1.** tf = 1 + log10(count) if count > 0, else 0. The log dampens frequent words, and the guard avoids log(0).
8. **What is the difference between sparse and dense retrieval?** Sparse uses word counts (TF-IDF, BM25). Dense uses embeddings in a vector space.
