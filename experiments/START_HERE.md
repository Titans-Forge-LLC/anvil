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
Python 3.10+, Git to obtain this repository, and a working local Splash or
TensorFold model server. The demo ZIP is not the full live workbench installation. ANVIL does
not install or start a server. If you have no local model yet, use the replay
first, then follow [Splash's setup instructions](https://github.com/incoai/splash#quick-start).
Hardware requirements depend on the model you select.

**Already have a saved proposal?** Use the offline restart instructions below;
you do not need to install or start a model to review and export it.

## Try one small repair

From a terminal, obtain the project and enter its directory:

```sh
git clone https://github.com/Titans-Forge-LLC/anvil.git
cd anvil
python3 experiments/workbench.py --help
```

These commands use the current `main` branch in a fresh clone. The workbench is
still an experimental preview, not a newly tagged release. The older demo ZIP
does not include multi-function transactions or saved checkpoints. Preserve any
unfinished work before updating an existing checkout.

With your local Splash server already running, start the review session.
Change the port below if your server uses a different one:

```sh
python3 experiments/workbench.py --backend splash --splash-url http://127.0.0.1:8000 --interactive --project-root .
```

Or, with your existing TensorFold server running, use this command instead:

```sh
python3 experiments/workbench.py --backend tensorfold --tensorfold-url http://127.0.0.1:18420 --interactive --project-root .
```

Neither command installs or starts a server. Keep your model and code local.
Interactive mode validates the project folder before starting a backend, then
checks the HTTP model catalog before asking for a file. A reachable
catalog does not prove model loading or generation will succeed. At the prompts:

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

At the `File:` prompt, enter `:help` for a reminder of selection, checkpoint and
review commands. Help is local and does not inspect source or ask the model.

Choose `e` only after inspecting the proposal, then enter `first-edit.patch`.
Success reports `Exported` and `Nothing was applied or executed`. From a separate
terminal in the same repository, check that the patch fits:

```sh
git -c core.autocrlf=false apply --check first-edit.patch
```

A successful check normally prints nothing. It does not apply the patch or test
the code. If you decide to apply it yourself, verify these behaviors afterward:
`average([]) == 0`, `average([2, 4]) == 3`, and `average([-2, 2]) == 0`.

## Stop now, review later — no model needed

Before applying anything to the source, choose `s` at the review prompt, enter
`first-edit.anvil-checkpoint.json`, then choose `q` to exit. A checkpoint contains
the proposed code, original source hash and editable scope. It is not encrypted,
authenticated, tested or approved just because it was saved. Keep it private.

You may now stop your model server using its normal shutdown procedure. From the
same repository directory, start a new session:

```sh
python3 experiments/workbench.py --backend offline --interactive --project-root .
```

At `File:`, enter `:load first-edit.anvil-checkpoint.json`. Inspect the restored
scope and diff. Choose `e` and enter a **new** filename, `resumed-edit.patch`.
The source stays unchanged; offline restore/export makes no model request.
You can check the exported patch with:

```sh
git -c core.autocrlf=false apply --check resumed-edit.patch
```

If the source changed since saving (including applying the earlier patch),
loading is refused. Request a fresh proposal instead. To revise an unchanged
source, restart with a model backend and load the same checkpoint there.

## Next: one change across related functions

On a small file of your own, select 2–4 displayed function numbers separated by
commas, for example `1,2`. Describe the related change once. ANVIL requests one
transaction, validates every selected member and preserves all surrounding
source bytes. Review, save and export use the same commands as above.

You choose the related functions; ANVIL does not discover dependencies or prove
that the code behaves correctly. Test the patch yourself before adopting it.
Fewer requests do not guarantee less elapsed time: longer answers and corrections
still count.

## If something goes wrong

- **Connection failure:** confirm your server is running and the local port is
  correct. If authentication is enabled, configure the client key for your backend
  (`SPLASH_API_KEY` or `TENSORFOLD_API_KEY`) to match the server. Do not share it in a bug report.
- **Markdown-wrapped answer:** choose `n` for a new request and add “Return only raw Python code, without Markdown fences or explanation.”
- **Incomplete or rejected answer:** start with this tiny example; use
  `--max-tokens 2048` if the replacement does not fit. Inspect every new result.
- **Source changed:** request a fresh proposal using the current file.
- **Patch already exists:** choose a new filename; export does not overwrite it.
- **No model yet:** the recorded replay above works without one.
- **Offline revision refused:** offline mode only reviews saved proposals.
  Restart with a model backend to generate a new answer.

A failed save/export or a failed, rejected or incomplete revision keeps your
last good proposal at the review prompt. Choose a different output filename,
save the retained proposal, or quit. No model request is retried automatically.
Keeping a proposal does not bypass the source-change check: if the source has
changed, start a fresh request before exporting.

The in-process Apple Silicon MLX alternative and detailed limits are documented
in [WORKBENCH.md](WORKBENCH.md). Keep that as a reference after your first run.

## Tell us what happened

[Open an issue](https://github.com/Titans-Forge-LLC/anvil/issues/new) with:
your OS/Python version, backend/model name, the step that stopped you, expected
versus actual behavior, and whether you would use the workflow again. Include
a small public example if possible. Leave out private code, credentials and
unredacted transcripts.
