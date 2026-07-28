# Deploying AgentSentinel for a showcase

Scope (see the conversation/`next_steps.md` for why): a public dashboard with
real results baked in, plus a real, always-green CI badge — both reliable,
neither dependent on a live LLM call succeeding in front of a viewer. Live
cloud evaluation of the three real target agents is explicitly out of scope
here (see `docs/architecture.md` for why that's a bigger, separate project).

Two manual steps below need your own GitHub/Streamlit accounts — I can't do
those on your behalf. Everything else is already done and committed.

## What's already prepared

- `demo_data.db` — a committed (not gitignored — see `.gitignore`'s explicit
  exception) SQLite snapshot with real results: a toy-agent regression
  catch/recover cycle, and a real RAG chatbot run including the confirmed
  injection-resistance case. The dashboard defaults to this file automatically
  when no local override is set (`agentsentinel/dashboard/app.py`), so a fresh
  deploy shows real content immediately with zero setup.
- `requirements.txt` (repo root) — what Streamlit Community Cloud auto-detects
  to install the app's dependencies.
- `.github/workflows/ci.yml` — runs the test suite on every push, plus
  `agentsentinel gate --agent toy-agent` with a rolling SQLite baseline
  cached between runs (via `actions/cache`), so it's a real, working
  regression gate from the first push onward — no API key needed, since the
  toy agent and its deterministic scorers require none.

## Step 1 (manual): push to GitHub

If you don't already have a GitHub repo for this project:

```bash
cd "GITHUB proj/agentsentinel"
gh repo create agentsentinel --public --source=. --remote=origin
git push -u origin master
```

(No `gh` CLI? Create the repo manually at github.com/new, then:)
```bash
git remote add origin https://github.com/<your-username>/agentsentinel.git
git push -u origin master
```

Once pushed, the CI workflow runs automatically. Check the **Actions** tab on
GitHub — you should see `test` and `gate` jobs, both green. Push again (any
commit) and the `gate` job's log will show it comparing against the previous
run's baseline via the restored cache.

Add the CI badge to the top of `README.md` (replace `<your-username>`):
```markdown
![CI](https://github.com/<your-username>/agentsentinel/actions/workflows/ci.yml/badge.svg)
```

## Step 2 (manual): deploy the dashboard on Streamlit Community Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with
   GitHub.
2. **New app** → select the `agentsentinel` repo, branch `master`.
3. Main file path: `agentsentinel/dashboard/app.py`
4. Deploy. First build takes a minute or two (installing streamlit/pandas +
   the package itself via `requirements.txt`'s `-e .`).
5. Once live, it opens straight to the **Overview** tab with real data from
   `demo_data.db` — no configuration needed. Check the **🛡️ Injection** tab
   specifically; that's the most resume-compelling screenshot the project
   produces (the confirmed RAG chatbot injection-resistance result).

You'll get a URL like `https://<something>.streamlit.app` — that's the link
to put on a resume/portfolio.

## Regenerating `demo_data.db` later

If you want fresher/more complete showcase data later (e.g. once the
`adk-003` injection verdict is confirmed — see `next_steps.md`), regenerate
it the same way it was built:

```bash
python -m agentsentinel.cli gate --agent toy-agent --db-path demo_data.db
# ... (break something in toy_agent.py temporarily, gate again, fix, gate again)
python -m agentsentinel.cli run --agent rag-chatbot-langchain --db-path demo_data.db --scorers all
```
Then commit the updated `demo_data.db` and push — Streamlit Community Cloud
redeploys automatically on push to the connected branch.

## What's intentionally NOT deployed

Live evaluation of the three real target agents (LangGraph research
assistant, RAG chatbot, ADK stock agent) still only runs locally, on this
machine, against each target repo's own local venv. That's a real, larger
undertaking (containerizing three separate Python environments) — see
`next_steps.md` if that becomes worth doing later. The showcase above doesn't
need it: the dashboard shows real, already-generated results, and the CI gate
demonstrates the actual mechanism (regression detection) with zero
dependency on a live agent call succeeding.
