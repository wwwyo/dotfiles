# 非同期jobs・durable workflows・schedule

Paths in commands are relative to the skill root (the directory containing `SKILL.md`), unless stated otherwise.

| What you need to do | Product or tool to consider | When to choose it | Skill or reference |
| --- | --- | --- | --- |
| Process jobs asynchronously or buffer bursts of work | Queues | Decouple producers and consumers; use Workflows for durable multi-step orchestration | [Queues](queues/README.md) |
| Run a job that retries, waits, and resumes across steps | Workflows | Coordinate durable multi-step business processes | [Workflows](workflows/README.md) |
| Start a Worker on a recurring schedule | Cron Triggers | Trigger scheduled work; combine with Queues or Workflows for the work itself | [Cron Triggers](cron-triggers/README.md) |
