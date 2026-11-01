# Development observations

The first 19-case missing-analysis red log and the later five-case missing-CDR
red log are preserved in full, alongside the final 24-case pass and 766-case
suite. An intermediate strict float-equality assertion failed at 2.7755575615628914e-17
versus zero; the assertion was corrected to a 1e-15 numerical comparison. Its
original fixed-name development log was overwritten by the later CDR-red run;
this note records that limitation rather than reconstructing a complete log.

`replay-first.stderr` retains the original 100 ms hold refusal. The diagnostic
reader was corrected to report it as REJECTED and use the last detached step,
not to weaken the gate. `replay-second.stderr` retains Windows WinError 32 from
the read-only SQLite handle. Explicit connection closing fixed that cleanup.
Neither reader failure triggered another simulation or changed raw bytes.
