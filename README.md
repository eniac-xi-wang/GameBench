# GameBench

GameBench measures what a complete coding Agent can improve over several iterations. Each session starts with a working baseline, game source, an editable submission and a development evaluator. At the end of research the host freezes the submission, runs the original engine independently, verifies the replay and reports the task's raw score. [Historical results across all five games](results/RESULTS.md)

## Run a benchmark

From the repository root, with **Python 3.12+, Git and a C++20 compiler**:

```sh
./bench
```

The default runs Celeste Classic 100m using the supplied baseline. On the first run it fetches the pinned game, derives the starting script and compiles the headless engine. It prints the path to a new HTML report with a playable replay. Expected score is **94 frames**. No account, API key, Docker or model call is needed.

```sh
./bench --list
./bench --all --out runs/all-games
./bench --tasks shapez-stack mindustry-surge-alloy --out runs/factories
./bench --tasks showdown-expanded --submission /path/to/policy-directory --out runs/my-policy
```

Use a new output directory for each run. Omit `--out` for a fresh timestamped directory. The default `smoke` budget uses smaller random test sets. Select a research budget explicitly to run the full random test sizes. The baseline mode grades a second copy of the original submission and checks that it matches the independent baseline.

**Supported host.** The full suite is tested on Apple Silicon macOS with Command Line Tools. The two policy games (2048 and Showdown) use macOS Seatbelt for policy isolation. Celeste, shapez and Mindustry use data submissions. Mindustry automatically installs a pinned JDK on macOS arm64. On other Unix hosts it accepts `MINDBENCH_JAVA_HOME` pointing at a JDK 17+ with `java` and `javac`; these hosts have not undergone the full acceptance run. Games, Node, Java and npm dependencies are installed under the checkout when selected. First use needs internet access or the offline caches described below. Allow several GB for all game trees and workspaces.

For original game visuals, export a standalone 2048 or shapez web replay, import a factory into Mindustry, or open the official Showdown animation. [Game playback and local asset setup](docs/game-playback.md)

## Tasks and scores

| Game | Task IDs | Submission and primary score |
| --- | --- | --- |
| Celeste Classic | `celeste-100m`, `celeste-300m`, `celeste-400m`, `celeste-600m`, `celeste-700m` | JSON button timeline. Minimize frames to the next room from a fixed entry and seed; failure scores 601. |
| shapez | `shapez-cut`, `shapez-paint`, `shapez-stack` | JSON layout. Maximize correct deliveries over 3,600 ticks on the given map. |
| 2048 | `2048-policy` | JavaScript policy. Maximize mean score on fresh, paired tile streams subject to action, CPU and move limits. |
| Pokémon Showdown | `showdown-policy`, `showdown-expanded` | JavaScript policy. Maximize mean win credit. The legacy task has three opponents. The expanded task uses six strata and five opponents with team ownership and battle side swapped. |
| Mindustry | `mindustry-plastanium-bio-oil`, `mindustry-blast-compound`, `mindustry-surge-alloy` | JSON blueprint. Maximize the target items in the native core after 18,000 ticks on a fixed complex-production map. |

There are 14 registered tasks. A task is one optimization session per system and repeat. In expanded Showdown the same submitted program plays all six strata. The 12 basic Mindustry maps appear in the historical results; the release runs the three complex production chains. Each game keeps its own units. [Registry](benchmarks/suite.json) · [Task contracts](gamebench/registry.py)

## Run an Agent

Install the optional DeepSeek SDK into a virtual environment, export `DEEPSEEK_API_KEY` or set it in a local `.env`, then launch. The next command that uses `--system deepseek-default` makes paid provider calls.

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-agent.txt
./bench --tasks celeste-100m --system deepseek-default --budget 30m
```

The official SDK adapter uses the system manifest's model and the native harness defaults. Other harnesses can use a JSON manifest with a native command, its actual version, a model identifier, and the names of credentials it needs. The command receives the writable workspace as its current directory. Its argument list can include `{python}`, `{workdir}` and `{instruction}`. Run the harness noninteractively and pass it the neutral instructions in that file. To compare two systems, register both in **the same invocation**:

```sh
./bench --tasks showdown-expanded --budget 30m --system system-a.json --system system-b.json
```

Each system gets a separate home directory, the same starter files, the same native simulation API, and a development client inside its workspace. It may inspect source, write analysis programs, run tools, change the submission and ask for another development evaluation with `python3 bench.py trial-name [round|validation]`. The requested credential names are forwarded only to the native agent launcher. Logs and local run directories are ignored by Git. [System manifest template](benchmarks/systems/external-template.json) · [DeepSeek manifest](benchmarks/systems/deepseek-default.json)

## How to interpret a run

- **Budget.** Smoke gives each research session 60 seconds and runs once. The 30m, 2h and 8h profiles run three fresh sessions per system per task, each with the named wall-clock allowance. Thus `--budget 30m` can use 90 minutes of research per system per task. Preparation and final judging run outside that allowance. System-reported costs and tokens may be unavailable. This release implements elapsed-time budgets. [Budget profiles](benchmarks/budgets.json)
- **Selection and randomness.** The host freezes the last on-disk submission at exit or deadline. All submissions in the comparison freeze before stochastic final cases are generated. Within a repeat the baseline and all submissions receive identical cases. 2048 uses 2 final games in smoke or 128 in research. Legacy Showdown uses 12 or 1,152 games. Expanded Showdown uses 120 or 1,920 games, with legal team combinations excluded across published development and fresh final splits. Fixed maps and room entrances measure fixed-instance optimization.
- **Evidence.** Open `index.html` for scores and replays. `comparison.json` contains per-task scores across repeats. `report.json` contains baseline and submission results, paired differences and paths to independent engine records. `cohort.json`, `sealed.json` and `private/tests.json` preserve registration, hashes and the actual final draw. Recheck a saved evaluation in the same checkout with `python3 -m gamebench verify runs/NAME/grading/systems/SYSTEM/TASK/0`. A failed harness launch, invalid submission or failed baseline check returns a nonzero exit status.
- **Scope.** This is a **local, unranked** backend for trusted researchers. A native agent can read its host, and host-wide CPU, RAM, disk, network and detached processes are not fully isolated. Use a dedicated machine or VM for untrusted agents. Historical scores were collected under multiple protocols. Seed variation within a game and variation across independent Agent research runs are distinct sources of uncertainty. [Historical tables and limitations](results/RESULTS.md)

## Reproducibility and publication

The default checkout contains the evaluator, manifests, baseline definitions, build recipes, historical aggregate data and their provenance hashes. Node archives and the Mindustry binaries are verified by SHA-256; npm builds use lockfiles. The Celeste baselines and prefixes are derived from the pinned upstream recording as part of setup. [Pinned game sources](benchmarks/upstream.json) · [Third-party notices](THIRD_PARTY.md) · [License](LICENSE)

The release acceptance run passed all 14 baseline tasks in a clean macOS arm64 clone using local dependency caches. Both sides of each comparison were independently evaluated and replay-checked. Twelve protocol tests passed, including a no-model native process that edited the Celeste baseline twice, used both development replays and froze a 92-frame submission. [Acceptance record](results/release-acceptance.json)

For offline setup, `GAMEBENCH_SOURCE_CACHE` can point to a directory of local Git repositories named as in the upstream lock. `GAMEBENCH_DOWNLOAD_CACHE` can contain the fixed archives, including `server-release.jar` and `mindustry-jdk21.tar.gz` for the automatic JDK. npm supports its own populated `npm_config_cache` with `npm_config_offline=true`. Final runs write into their own directories.

To check the public historical table from the committed data, run `python3 tools/history.py --check`. With the original private archive, `python3 tools/history.py --archive /path/to/archive --check` also verifies every selected source hash and regenerates the data in memory. Public readers can reproduce the tables without access to the private archive. After setting up Celeste, 2048 and Showdown, run the protocol tests with `python3 -m unittest discover -s tests`.
