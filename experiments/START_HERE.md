# Your first ANVIL edit

ANVIL helps you inspect a proposed code change before you apply it. Start with
one small Python file. You do not need to understand its research architecture.

## Choose your starting point

**Just want to see it work?** [Open the recorded demonstration](https://www.titansforge.tech/anvil-demonstration).
To reproduce it without a model, download **ANVIL-Demonstration.zip** from the
[demo release](https://github.com/Titans-Forge-LLC/anvil/releases/tag/demo-workbench-2026-09-25),
extract it, and open `index.html`. In a terminal, change into the extracted
`ANVIL-Demonstration` folder and run:

```sh
python3 --version
python3 verify.py
```

Use Python 3.10 or later. Expect `"passed": 5`, with every check `true`.
No extra Python packages are needed. These checks replay a recorded answer;
they do not ask a model to solve a new task. If the terminal cannot find
`verify.py`, you are not inside the extracted folder. Windows users can use
`py -3` instead of `python3` if that is their installed Python launcher.

**Want a new answer on your code?** Follow the small exercise below. You need
Python 3.10+, Git to obtain this repository, and a working local Splash model
server. The demo ZIP is not the full live workbench installation. ANVIL does
not install or start a server. If you have no local model yet, use the replay
first, then follow [Splash's setup instructions](https://github.com/incoai/splash#quick-start).
Hardware requirements depend on the model you select.

## Try one small repair

From a terminal, obtain the project and enter its directory:

```sh
git clone https://github.com/Titans-Forge-LLC/anvil.git
cd anvil
python3 experiments/workbench.py --help
```

With your local Splash server already running, start the review session.
Change the port below if your server uses a different one:

```sh
python3 experiments/workbench.py --backend splash --splash-url http://127.0.0.1:8000 --interactive --project-root .
```

The ANVIL prompt alone does not prove the model server is ready. At the prompts:

| Prompt | Enter |
|---|---|
| File | `examples/workbench_sample.py` |
| Editable scope number | `1` (the displayed `average` function) |
| Read-only helper names | Press Enter |
| Requested change | `Return zero for empty input while preserving other cases and the function name.` |
| Output format | Press Enter for replacement |

A successful proposal displays `Reviewable: True` and a diff. Look for an empty
input check and preserved averaging behavior. Reviewable means you can inspect
it; it does not mean the answer is correct. The source file should remain unchanged.

Choose `e` only after inspecting the proposal, then enter `first-edit.patch`.
Success reports `Exported` and `Nothing was applied or executed`. From a separate
terminal in the same repository, check that the patch fits:

```sh
git -c core.autocrlf=false apply --check first-edit.patch
```

A successful check normally prints nothing. It does not apply the patch or test
the code. If you decide to apply it yourself, verify these behaviors afterward:
`average([]) == 0`, `average([2, 4]) == 3`, and `average([-2, 2]) == 0`.

## If something goes wrong

- **Connection failure:** confirm your server is running and the local port is
  correct. If authentication is enabled, set matching `SPLASH_API_KEY` values
  for the server and client. Do not share the key in a bug report.
- **Incomplete or rejected answer:** start with this tiny example; use
  `--max-tokens 2048` if the replacement does not fit. Inspect every new result.
- **Source changed:** request a fresh proposal using the current file.
- **Patch already exists:** choose a new filename; export does not overwrite it.
- **No model yet:** the recorded replay above works without one.

The in-process Apple Silicon MLX alternative and detailed limits are documented
in [WORKBENCH.md](WORKBENCH.md). Keep that as a reference after your first run.

## Tell us what happened

[Open an issue](https://github.com/Titans-Forge-LLC/anvil/issues/new) with:
your OS/Python version, backend/model name, the step that stopped you, expected
versus actual behavior, and whether you would use the workflow again. Include
a small public example if possible. Leave out private code, credentials and
unredacted transcripts.
