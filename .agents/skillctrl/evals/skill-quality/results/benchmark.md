# Current skill evaluation

Snapshot: `db1fa8c3be8f29278ba6a9f1f35ad6f2d0e39abf`.
Pi 0.87.1 / opencode-go/space-bunny-free / high. One completed run for each of six tasks.

| Metric | Current |
| --- | ---: |
| Assertions passed | 35/36 |
| Pass rate across tasks | 97% ± 7% |
| Completed-run time across tasks | 126.3s ± 91.1s |
| Completed-run tokens across tasks | 266769 ± 170352 |

The CLI schema query fails. The standard deviations describe different tasks, not repeated-run variance.
Time/tokens do not establish speed or cost improvement. Human validation of criteria is pending.
The exact grader model ID was not recorded. Tool-call counts use result.json array lengths. Error counts are postprocessed native tool_execution_end isError events, published as each row’s is_error boolean.
Subsequent main/review changes have not received a full model rerun.

[Original before/after evidence](https://github.com/wwwyo/dotfiles/tree/e07b6d5005387f54db01fa0cda5384d1a252a262/.agents/skillctrl/evals/skill-quality/results) is retained in commit history.
