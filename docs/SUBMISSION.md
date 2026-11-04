# Submission kit

## Before 6:00 PM Ecuador (deadline is 9:00 PM)
- [ ] Repo is public and the README renders (open it logged out).
- [ ] No `.env`, no `private/`, no real names, ID numbers or phone numbers in the repo.
- [ ] Video recorded, uploaded (YouTube *Unlisted* or Vimeo), link opens in a private window.
- [ ] Everyone who worked on it is listed on the submission page.
- [ ] Post on X with the video, link copied into the submission form.
- [ ] Submit on the Cerebral Valley platform. Do not wait for 9:00 PM.

## 3-minute video (English narration, or Spanish with English subtitles)
Show only what you actually ran. Record the terminal at a large font size.

| Time | Show | Say |
|---|---|---|
| 0:00–0:25 | One photo of the footbridge or water plant, no faces | "In 2024 I wrote a proposal to keep this community's water plant and evacuation route running through power cuts. It was never reviewed. Reading it again, the system was never sized and the budget did not add up." |
| 0:25–0:50 | Terminal: the command | "So I built the tool it needed: an agent that turns a site's documents into a sized solar design, and never invents a number." |
| 0:50–1:50 | `python -m solar_agent agent cases/example-agent`, output scrolling | Narrate: it reads the survey and datasheets, every input cites an exact quote, it fetches real irradiance for the site, it sizes the system. Say clearly the example case is synthetic. |
| 1:50–2:20 | Open `runs/example-agent/proposal.md`: Results, the derivation tree, "Open questions" | "Every number traces to a source. What nobody measured is listed for a person to confirm. The text is written by code, so it cannot contain a figure that was not computed." |
| 2:20–2:45 | `pytest` showing 41 passed, then the README's "Evidence" section | "On the first live run Muse Spark recorded 45 instead of 0.45, looped on a status tool, and the run was reported as finished without sizing. I found all three, fixed them and added tests." |
| 2:45–3:00 | README top | "Built with Muse Spark 1.3 through the Meta Model API. It is a preliminary design for an engineer to sign, and it is where I take that 2024 proposal next." |

Do not claim: SAM 3.1, voice, open-weight models, real-site results, product comparison, or a budget from real quotes.

## X post
> In 2024 my proposal to keep a rural water plant and evacuation route running through blackouts in Ecuador was set aside before anyone reviewed it. For the @Meta hackathon I built the tool it needed: an agent (Muse Spark) that turns a site's documents into a sized solar design where every number cites its source and nothing is invented. Demo + code: <repo link> <video>

## Form answers (adapt)
- Track: Build for Your World.
- One line: An agent that sizes solar + storage for rural infrastructure with every number traced to a source, and hands what it cannot prove to a person.
- New work: all code written Oct 27 – Nov 4. The 2024 proposal is background and is not in the repo.
- Meta tooling: Muse Spark 1.3 via the Meta Model API, tool calling, reasoning model.

## Real-datasheet segment (use it in place of the 1:50-2:20 row if time is tight)
Show the second run: the six `ask_human` lines, then the top of `proposal.md` with the ILLUSTRATIVE ONLY box.
Say: "With one real datasheet and notes from my 2024 proposal, the agent does not invent a design. It asks the six
things that must be measured on site, and the report is stamped illustrative. Testing it also showed me a limit: this
luminaire has its own panel and battery, and the agent did not notice. That is the next thing I fix."
