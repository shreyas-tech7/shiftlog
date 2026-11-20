# Contributing

1. Run `./init.sh`. It must pass before and after your change.
2. Write a test that fails first. Name the broken case in its docstring.
3. Keep the standard library as the only runtime dependency.
4. Start every process through `gatedcrew.proc.run` with a timeout. A test checks this.
5. Never type numbers into README.md. Change the code or rerun the benchmark, then run `gatedcrew readme`.
6. Tests must run offline and inside temp folders.
7. Open a pull request with a short "Before" and "After".
