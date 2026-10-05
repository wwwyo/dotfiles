import { rejection } from './fixture-paths.mjs';

export default function (pi: any) {
  pi.on('tool_call', async (event: any, ctx: any) => {
    const reason = rejection(event.toolName, event.input.path ?? '.', ctx.cwd, process.env.SKILL_EVAL_READ_ROOT!);
    if (reason) return { block: true, reason };
  });
}
