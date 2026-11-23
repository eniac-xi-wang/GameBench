# Third-party software and data

The MIT license at the repository root covers the GameBench contributors' benchmark code and documentation. Each upstream project retains its own rights and notices. Game names and trademarks belong to their respective owners. Engine source, game media, generated engine bundles, native executables and Java archives are obtained locally during setup. The fetch manifest records the exact commits. [Upstream lock](benchmarks/upstream.json)

| Dependency | Use and notices |
| --- | --- |
| ccleste | Fixed-point C port of Celeste Classic by Maddy Thorson and Noel Berry. GameBench derives the five starting scripts and four room prefixes locally from the pinned checkout's `test-tas.txt`. [Credits and port documentation](https://github.com/lemon32767/ccleste/tree/261d96f15af430b8111abc7a5250229246654f52) |
| 2048 | Uses the original tile, grid and game-manager logic. [Gabriele Cirulli's MIT license](https://github.com/gabrielecirulli/2048/blob/478b6ec346e3787f589e4af751378d06ded4cbbc/LICENSE.txt) |
| Pokémon Showdown | Headless battle simulation and legal team validation. Pokémon names and moves identify game mechanics. [Upstream license and notices](https://github.com/smogon/pokemon-showdown/blob/965a535ef892d13cd68cf75c076db26f9f32842a/LICENSE) |
| shapez.io | Builds a local headless simulation bundle from pinned source using the supplied build recipe. [Upstream GPL-3.0 license](https://github.com/tobspr-games/shapez.io/blob/8a79de5255fb6756f3a1d26579b1e9bc36e0c811/LICENSE) |
| Mindustry | Uses the official v160.7 headless server. [Source and license](https://github.com/Anuken/Mindustry/tree/17012d61d9e4c3cbd9820d87e81c24495486ac53) |
| Node.js, esbuild and Eclipse Temurin | Local tools retain the notices in their distributions. Node archives, esbuild package integrities, the Mindustry JAR and the automatic macOS JDK archive are pinned in the repository. [Node](benchmarks/node.json) · [esbuild](tools/package-lock.json) · [Java and server](mindbench/engine.json) |

The historical 2048 comparison includes results for the nneonneo solver. The public table distributes aggregate measurements. [Original solver](https://github.com/nneonneo/2048-ai)
