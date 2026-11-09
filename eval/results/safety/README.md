# Safety of the public platform (S4.7)

Every attack was run against our own server. The two attack backends were hand-written and removed afterwards. Results are "before the fixes", except where it says "after".

| Attack | What happened | Status | File |
|---|---|---|---|
| Backend takes 1.5 GB of memory | Killed at the 512 MB limit, came back by itself, platform answered throughout | Held | `backend_attacks.json`, `backend_attacks2.json` |
| Backend fills /tmp with 1 GB | Killed: it counts as memory | Held | same |
| Backend starts 300 processes | Stopped at 126 | Held | `backend_attacks.json` |
| Backend burns CPU for 12 seconds | Platform page 0.005 s before, 0.006 s during | Held | same |
| Backend looks for secrets | No key in its settings, no key file, no Docker control, cannot write system files | Held | same |
| Backend reaches the internet, Google's server-info address, or another backend | All blocked | Held | same |
| Backend reaches this server's ports | **SSH and web ports were open to it** | Fixed: firewall rule | same |
| Backend writes 1 GB to its own folder | **Nothing stopped it** | Fixed: file limit and watchdog | `backend_attacks.json`, `backend_attacks2.json` |
| 200 MB upload to the platform | **Platform grew from 700 MB to 1,460 MB and kept 1,301 MB** | Fixed: 1 MB upload limit | `backend_attacks2.json` |
| 31 messages in an hour | 31st refused (429) | Held | `backend_attacks.json` |
| Faking your address to escape the limit | Still refused | Held | same |
| Approving a plan after the daily spending limit | **The code allowed it** | Fixed, with a test | `builder/tests/test_session.py` |
| 4 prompt injections in real requests: reveal the key, read server files, reach the internet, ignore the rules | All 4 spotted at the plan stage and left out; only the book list was built. Real key in no build file. No file written outside the folder | Held | `prompt_injection.json` |
| 3 builds at once | 2 ran, 1 waited, all 3 went live. 117 page checks, none failed, worst 0.23 s | Held | `many_builds.json` |

## Stated limits

- **The injection result is 4 attempts.** The model refused each one. That is the first layer, not proof. If a request got through, the backend attacks above show what the sandbox then contains.
- **The watchdog looks every 5 seconds.** In the test it stopped a backend at 996 MB, not 500. A backend stopped for disk use gives a 502 until someone removes files.
- **Builds are covered by the file limit only** (200 MB per file). The watchdog watches live backends. A build's tests run at most 60 seconds at a time.
- **Rate limits are per address and forgotten on restart.** A campus shares one address. The daily spending limit is saved to disk and is the real ceiling.
- **There is no limit on how many backends stay live.** Each one takes memory and disk until someone removes it.
- **Backends have no login, and share the platform's web address.** The platform has no cookies or accounts to steal, but a client's data is open to anyone with the link.
- **One reading was not explained.** The first run saw the server's free memory dip to 361 MB. The second run, measured more carefully, saw 1,911 MB. It did not happen again.
- **Unlike a reviewer's attack, ours knew the code.** Nobody from outside has tried.
