The first capture used a UDP port BPF, which omitted noninitial IP fragments.
rtps_packets.jsonl, rtps_summary.json, server_sedp_publications.json and rtps_reliability.json are partial-decoder artifacts.
Do not infer that SEDP samples 4..16 were not sent from them. Full-fragment capture reconstructs these outgoing samples.
Use full_capture_analysis/fragment_summary.json for separate outgoing/incoming coverage; outgoing complete does not mean delivered.
