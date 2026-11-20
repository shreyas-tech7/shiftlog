# Proposals

Ideas that the brief did not list. Shreyas picks what gets built.

- A worker adapter for a real coding agent command line tool (the brief's stretch item). Steps are in docs/HUMAN_STEPS.md. Not built in this run.
- Sign the audit head with an SSH key, so a forged chain needs the key.
- Run the worker under `bwrap` or a container when one is present, as an opt-in real sandbox.
- A per-gate allowance on approve, such as "allow this one command once".
- A `gatedcrew watch` mode that prints each audit line as it lands.
