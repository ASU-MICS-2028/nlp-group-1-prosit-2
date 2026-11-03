# Lecture 8: How the Frontend, Backend and Agent Fit Together; What Prosit 2 Must Deliver

## In one paragraph
This lecture is the clearest statement so far of what the finished Prosit 2 platform must do. It opened with a group's progress update (they had one agent left to build, a test/evaluation agent). Then the instructor drew the architecture on the board: a prompt page sends the user's message to a backend endpoint, and the backend hands it to an agent. He explained where the agent can run and why the page should never talk to the agent directly. He then defined the output. The agent must leave behind a **fully working backend that we host**, with a real database, and return its link and its endpoints. He walked through the agent loop step by step (plan, write code, write files, set up the database and server, run, test, fix, repeat). He explained why the agent needs tools, where MCP fits, and named some agent harnesses and frameworks. The session ended with comments on the last classwork's grading, then unrelated side chat (omitted). The recording is patchy in places, and it is not always clear which speaker is the instructor.

Mis-transcriptions: "Lavable" is Lovable. "Redpill" is probably Replit (both are named in the Prosit 2 brief). "Open Development Kit" is Google's ADK. A library heard as "code sling" is unclear in the recording.

## Key ideas, explained simply
- **Three parts: page, backend, agent.** The user types into a prompt page (the frontend). The page sends the message to an endpoint on our backend, for example `process message`. That endpoint passes the message to the agent. He compared it to a normal web app, where `GET /menu` runs a function that reads the menu from a database and returns it.
- **Where the agent runs: two options.**
  1. **Inside the backend's code:** a global `agent` object is created when the server starts, and the endpoint calls something like `agent.process_message(message)`.
  2. **As a separate service:** an agent built with a framework that gives it its own API, which the backend calls.
- **Always put a backend between the page and the agent.** Never expose the agent directly to the page. The backend can clean the input and guard against prompt injection. It is the same reason a page should never talk to the database directly.
- **The model is the brain, the agent uses it.** A local model can be loaded into the backend's memory. A cloud model (Anthropic, OpenAI) needs a separate API call. Either way, the model alone is not enough: the agent is what makes use of it to get work done.
- **HTTP is stateless.** Each request is new, and the server does not remember earlier ones. Some other connections (he mentioned web servers keeping a persistent connection) know who is connected.
- **The agent loop.** He asked what a developer does when told "build me a library backend", then said the agent does the same:
  1. plan the endpoints and the data (for example `POST /books`, `GET /books/{id}`, `GET /search?title=`);
  2. generate the code;
  3. write it to files (a whole project, not one file);
  4. set up a database and a server;
  5. run the project;
  6. test it against the live endpoints (add a book, check it is in the database);
  7. if something fails, find the bug and go back to generating code.

  It is **a `while` loop, not a fixed number of steps: break when the API's tests pass.**
- **The loop must take new messages while it works.** Example: the user starts a library build, then says "I don't want an endpoint for adding books, I'll load them from a CSV file". That message must change what the agent is doing. In his words, the loop is "always active": planning, doing, checking.
- **Why tools.** An LLM can say "write this code to a file" or "start a server", but it cannot do either. The agent needs a tool for each action: writing files, setting up a database, running the project.
- **Where MCP fits.** Setting up a database on a service like Supabase takes many API calls (create the database, create tables, set privileges). A human reads the documentation to find them. An MCP server lists a service's tools so the agent can discover which to call. He stressed that Supabase was only an example, not a requirement.
- **Harnesses and frameworks.** Harnesses are generic agent loops (he named Hermes and OpenClaw). Frameworks help you build your own (LangChain, LangGraph, Google ADK). He said a framework is probably better than building all the orchestration in pure Python, but that it is our choice. Single-agent or multi-agent is also our choice.

## What the instructor said about assignments, deadlines or grading
- **The required output:** "a fully functioning backend that the agent has built, with all the methods and everything working".
- **We host it.** Users are not technical, so we host the backend on a server and look after the database and all the infrastructure, the way Lovable and Replit do. He said "not most. All", and mentioned possibly a custom domain. Sending the user code to run themselves, or a backend that returns dummy data, is not enough.
- **What the agent returns:** a result, not just a link. That means the backend's address plus its methods (for example "get books", "add book"). If the user adds a book, they get a success reply, and getting books afterwards returns it.
- **No frontend for the generated backend.** The full vision would also generate a React frontend that talks to the generated backend, but for this prosit, only the backend.
- **Make it easy to try:** Swagger docs ("how a lot of people did it last time") or a page where the user can click to send requests. Postman also works.
- **"The middle" is ours to design:** everything between the agent receiving "build this" and a running backend that accepts requests.
- **Classwork grading** (apparently the instructor):
  - The section average was about 91% and technical parts were generally good.
  - Some reports were far too long. The paragraph counts given add up to roughly 4–7 pages, but one report reached 20.
  - Answers written without restating the question were sometimes weaker.
- **Timeline:** a student said the group would aim to finish "next week". The real deadline was not stated in the recording.
- **Next class:** the instructor will let the class try building an agent (the exact tool he named is unclear in the recording).

## Relevance to Prosit 2
- **The platform:** this adds three requirements to what we planned.
  1. The built backend must stay running, publicly reachable, with its data kept.
  2. Our own backend must sit between the page and the agent.
  3. The agent must accept follow-up messages during a build.
- **f Agentic AI, n Perceive-plan-act (ReAct), o Tool use:** the agent loop and "the LLM cannot write files, so it needs tools" are exactly these topics.
- **g Multi-agent systems:** he noted some groups use several agents. A group in the update was building a separate test/evaluation agent that checks the coding agent's work.
- **k Privacy and security:** proxying through a backend to clean input and block prompt injection.
- **l Human-in-the-loop:** a user changing their mind mid-build must steer the agent.
- **Report:** keep it to the page counts. Restating the question helps.

## Likely quiz or viva questions
1. Why not let the page call the agent directly? The backend can clean input and stop prompt injection, just as a page should not call the database directly.
2. When does the agent loop stop? When the generated API's tests pass. It is a `while` loop, not a fixed number of steps.
3. Why does an agent need tools? An LLM only produces text. It cannot write files, start servers or create databases, so tools do those actions.
4. What does MCP add? A standard way for a service to list its tools so an agent can discover and call them.
5. What must the platform return to the user? The address of a running, hosted backend and its endpoints, with a real database behind it.
6. What is the difference between a harness and a framework? A harness is a ready-made generic agent loop. A framework is a toolkit for building your own.
