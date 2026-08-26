# Communications — Policy, Collection Procedure, and Meeting Costs

> **Source:** `../source-material/Introduction Project Student Instructions.pdf`, p.1 ("Communication") and p.2
> (the seven-step meeting procedure).

---

## The policy, in one line

> "You may have unlimited communication via the written word digitally… **You will be required to submit
> a full record of your communications at the end of this project.**"

Two consequences that change how the team should behave from day one:

1. **Writing is free and unlimited. Talking is billed.** Anything that can be written should be written.
   The course has literally priced this preference at 1 Schrute Buck per person per minute.
2. **Everything written is a graded submission.** Discord messages, DMs, emails — all of it, in full,
   handed in around 15 SEP. Write accordingly: professional, specific, no side channels that would be
   awkward to submit, and **nothing deleted**.

**"Full record" is a collection problem, and it is only solvable in advance.** If nobody exports the
channel until 15 SEP and someone has left the server, deleted a DM, or the history has scrolled past a
free-tier limit, there is no recovering it. Export early, export repeatedly.

---

## Ground rules to agree on in the first standup

| Rule | Why |
|---|---|
| **One team Discord server, one primary text channel** | One channel to export beats six. Add `#standup`, `#design`, `#code` only if the team really needs them, and export every one of them. |
| **No DMs for project decisions.** Move it to the channel. | A DM between two people is part of "the full record" but is far harder to collect, and it cuts the other two out. |
| **Nobody deletes messages. Nobody deletes the server.** Not at the end either. | The record is a deliverable until it has been submitted **and** graded. |
| **Decisions get stated in writing even if they were reached out loud** | A decision made in a 5-minute standup and never written down does not exist for the report, the journal, or the record. |
| **Name one person as record-keeper** | Exporting is a two-minute job that only fails when it is nobody's job. |
| **Email threads: everyone on every reply.** Use reply-all. | Keeps the thread as a single exportable object. |
| **Anything sent to Dr. Watson or the TA gets forwarded into the channel** | Otherwise it is in one person's inbox and outside the record. |

---

## Collecting the record

### Discord

**Discord desktop is installed on this host** (snap `discord` 1.0.154, verified 2026-08-25 with
`snap list discord`). Three routes, best first:

**Option A — DiscordChatExporter (best fidelity, needs a check).**
A .NET command-line/GUI tool that exports a channel to HTML, plain text, CSV, or JSON with timestamps
and attachments. **`dotnet` 8.0.30 is installed on this host** (`dotnet --list-runtimes`, verified), so
the runtime prerequisite is already met.

```bash
# UNVERIFIED — this tool is not installed here; these are the shapes of the commands, not a tested recipe.
# Check the project's own README for the current release and its actual CLI before trusting any of it.
#   https://github.com/Tyrrrz/DiscordChatExporter
cd ~/Downloads && unzip DiscordChatExporter.Cli.zip -d dce && cd dce
dotnet DiscordChatExporter.Cli.dll channels -t "<TOKEN>" -g "<GUILD_ID>"     # list channels
dotnet DiscordChatExporter.Cli.dll export  -t "<TOKEN>" -c "<CHANNEL_ID>" \
       -f HtmlDark -o "sys301-<channel>-$(date +%F).html" --media
```

⚠ **UNVERIFIED / read before using:**
- ❓ Not installed on this machine; command syntax, flag names, and the current release are **UNVERIFIED**.
- ❓ Its maintenance status and latest version as of 2026-08 are **UNVERIFIED** — check the repo's last
  commit date and say that date out loud before recommending it
  ([knowledge-retrieval](../../directives/knowledge-retrieval.md)).
- ⚠ **It requires an authentication token.** Using a *personal user* token to automate the Discord
  client is against Discord's Terms of Service and can get an account actioned. A **bot token** on a
  server the team owns is the defensible path: create an application in the Discord Developer Portal,
  invite the bot to the team server with read-message-history, and use the bot token. **This is the
  operator's decision to make** — do not automate a personal account on our say-so.
- Enable **Developer Mode** (User Settings → Advanced) to right-click → Copy ID for guild/channel IDs.

**Option B — Discord's own data request (no token, no ToS question, slow).**
User Settings → Privacy & Safety → **Request all of my Data**; Discord emails a download package.
⚠ **UNVERIFIED:** the current menu path and the turnaround time (historically advertised as up to 30
days). **Far too slow to start on 15 SEP** — if this is the chosen route, request it in the first week.
It also returns *your* data, not the channel's, so four members may need four requests.

**Option C — manual, and it always works.**
Scroll the channel to the very top, select all, copy, paste into
`docs/course/team/comms-export/discord-<channel>-YYYY-MM-DD.md`, and take screenshots of anything the
paste mangles. Ugly, tedious, zero dependencies, zero ToS risk. **Do this once in week 1 as a floor**,
even if Option A is being pursued — a bad export that exists beats a good one that doesn't.

### Email

**Gmail (per-thread, exact, no tooling)** — open the thread → ⋮ (three-dot menu) → **Download message**
→ saves the message as `.eml`. Repeat per message in the thread; or ⋮ → **Print all** → destination
**Save as PDF** to get the whole thread as one file. ❓ **UNVERIFIED** — the exact menu wording in the
2026 Gmail UI; the operator should confirm both against the live interface.

**Gmail (bulk) — Google Takeout.** `takeout.google.com` → deselect all → select **Mail** → export →
download an `.mbox`. ❓ **UNVERIFIED**: current UI, whether label-scoped export is still offered, and the
turnaround. Label the project thread first (e.g. `SYS301`) so the export is scoped, if that option exists.

**Outlook / school mail** — ❓ **UNVERIFIED**: whichever client the school uses; "Save as" or print-to-PDF
per thread is the universal fallback.

**Thunderbird** is **not installed on this host** (`which thunderbird` returns nothing, verified), so
the ImportExportTools NG route would require installing it first.

### Where exports live

`docs/course/team/comms-export/` — create it when the first export happens, **with an `INDEX.md`**
listing what each dated export covers. Every docs folder has one
([documentation-discipline](../../directives/documentation-discipline.md)).

⚠ **Check the repo's `.gitignore` and think before committing an export.** It contains four people's
names and everything they wrote. Whether it belongs in git or is handed in separately is the
**operator's call**. And note that git mutations here are human-only
([scope.md blacklist](../../scope.md#permanently-out-of-scope-blacklist--enforced-not-deferred)).

### Suggested cadence

| When | Do |
|---|---|
| First class day (25 AUG) | Agree the ground rules. Do one manual Option C export to prove the record exists. |
| End of each sprint (27 AUG, 8 SEP) | Re-export the channel. |
| Demo Day (10 SEP) | Export everything, including email. |
| Before submitting (15 SEP) | Final export; check nothing is missing between the earlier snapshots and this one. |

Exports are cumulative snapshots, not replacements — **keep every dated file**. If the last export is
corrupt, the previous one covers all but a few days.

---

## Meeting costs — the reason to write instead of meet

**Free:** unlimited written digital communication · a **20-minute sprint planning meeting** at the start
of each sprint · a **5-minute stand-up** at the start of each day of the sprint.

**Billed:** any face-to-face beyond that.

| | Rate |
|---|---|
| Each team member present | **1 SB per person per minute** |
| Someone from another team | **2 SB per minute** (1 to the "bank", 1 to their team) |
| Rounding | **Down** to the nearest minute |

The instructions' own example: three team members meeting for 3:55 → 3 people × 3 minutes = **9 SB**.

### The procedure (p.2) — all seven steps, in order

1. **Inform Dr. Watson or the TA** that you wish to hold an in-person meeting.
2. The charge above applies, to simulate travel expense and the cost of participants' time.
3. **Assemble all meeting personnel at the meeting table.**
4. **Dr. Watson or the TA says "begin" and starts the stopwatch.**
5. When finished, **the SCRUM Master shall state "Meeting Adjourned"** — the meter runs until this is said.
6. Dr. Watson or the TA informs you of the bill (rounded down to the nearest minute).
7. **The Supplier pays the bill.** ⚠ **"If you are unable to pay the bill, then you shall return
   materials to cover the difference"** — and materials return at 90% of listed price, rounded down,
   so an unaffordable meeting destroys ~10% of the returned value permanently.

### Do the arithmetic before asking for a meeting

Current balance: **56 SB** (`./inventory.py`, 2026-08-25).

| Meeting | Cost | As a fraction of 56 SB |
|---|---:|---|
| 4 people × 5 min | 20 SB | 36% |
| 4 people × 10 min | 40 SB | 71% |
| 3 people × 10 min | 30 SB | 54% |
| 2 people × 5 min | 10 SB | 18% |
| 4 people × 10 min + 1 outsider × 10 min | 60 SB | **over budget** |

A four-person, ten-minute meeting costs **40 SB — more than the entire drivetrain bought so far**
(2 motors + 2 wheels = 34 SB). Write the message.

**When a meeting is actually worth it:** a decision that has stalled in writing across two class days;
a physical inspection that has to be done together (Builder + Designer looking at the same part); a
conflict that text is making worse. **Never for a status update** — that is what the free 5-minute
standup is for.

**Before the meeting, write down the question you are meeting to answer**, and put the answer back in
the channel afterwards. Otherwise you paid Schrute Bucks for something that leaves no trace in the
record, the journal, or the report.
