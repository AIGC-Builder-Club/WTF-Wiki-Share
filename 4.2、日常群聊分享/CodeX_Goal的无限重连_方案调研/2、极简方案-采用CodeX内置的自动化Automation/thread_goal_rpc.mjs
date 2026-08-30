#!/usr/bin/env node

import { spawn } from "node:child_process";
import { access } from "node:fs/promises";
import { constants } from "node:fs";
import readline from "node:readline";

const CODEX_BIN = "/Applications/ChatGPT.app/Contents/Resources/codex";
const REQUEST_TIMEOUT_MS = 15_000;
const THREAD_ID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function parseArgs(argv) {
  const [action, flag, threadId, ...extra] = argv;
  if (
    !["get", "set-active"].includes(action) ||
    flag !== "--thread-id" ||
    !THREAD_ID_RE.test(threadId ?? "") ||
    extra.length > 0
  ) {
    throw new Error(
      "usage: thread_goal_rpc.mjs <get|set-active> --thread-id <THREAD_ID>",
    );
  }
  return { action, threadId };
}

function publicGoal(goal) {
  if (!goal) return null;
  return {
    threadId: goal.threadId,
    status: goal.status,
    tokenBudget: goal.tokenBudget ?? null,
    tokensUsed: goal.tokensUsed,
    timeUsedSeconds: goal.timeUsedSeconds,
    createdAt: goal.createdAt,
    updatedAt: goal.updatedAt,
  };
}

async function openClient() {
  await access(CODEX_BIN, constants.X_OK);

  const child = spawn(CODEX_BIN, ["app-server", "--listen", "stdio://"], {
    stdio: ["pipe", "pipe", "pipe"],
  });
  const lines = readline.createInterface({ input: child.stdout });
  const pending = new Map();
  let nextId = 1;
  let stderr = "";
  let closed = false;

  child.stderr.on("data", (chunk) => {
    stderr = (stderr + chunk.toString()).slice(-4_000);
  });
  child.on("exit", (code, signal) => {
    closed = true;
    const detail = stderr.trim();
    for (const { reject, timer } of pending.values()) {
      clearTimeout(timer);
      reject(
        new Error(
          `app-server exited before responding (code=${code}, signal=${signal})${
            detail ? `: ${detail}` : ""
          }`,
        ),
      );
    }
    pending.clear();
  });
  lines.on("line", (line) => {
    let message;
    try {
      message = JSON.parse(line);
    } catch {
      return;
    }
    const waiter = pending.get(message.id);
    if (!waiter) return;
    pending.delete(message.id);
    clearTimeout(waiter.timer);
    if (message.error) {
      waiter.reject(new Error(JSON.stringify(message.error)));
    } else {
      waiter.resolve(message.result);
    }
  });

  const request = (method, params) => {
    if (closed) return Promise.reject(new Error("app-server is closed"));
    const id = nextId++;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        pending.delete(id);
        reject(new Error(`${method} timed out after ${REQUEST_TIMEOUT_MS}ms`));
      }, REQUEST_TIMEOUT_MS);
      pending.set(id, { resolve, reject, timer });
      child.stdin.write(`${JSON.stringify({ method, id, params })}\n`);
    });
  };

  let initialize;
  try {
    initialize = await request("initialize", {
      clientInfo: {
        name: "goal_monitor_automation",
        title: "Goal Monitor Automation",
        version: "1.0.0",
      },
      capabilities: { experimentalApi: true },
    });
    child.stdin.write(`${JSON.stringify({ method: "initialized", params: {} })}\n`);
  } catch (error) {
    lines.close();
    child.stdin.end();
    throw error;
  }

  return {
    request,
    userAgent: initialize.userAgent,
    close() {
      lines.close();
      child.stdin.end();
    },
  };
}

async function main() {
  const { action, threadId } = parseArgs(process.argv.slice(2));
  const client = await openClient();

  try {
    const beforeResult = await client.request("thread/goal/get", { threadId });
    const before = beforeResult.goal;
    if (!before || before.threadId !== threadId) {
      throw new Error(`no exact Goal mapping for thread ${threadId}`);
    }

    if (action === "get") {
      console.log(
        JSON.stringify({
          ok: true,
          action,
          method: "thread/goal/get",
          userAgent: client.userAgent,
          goal: publicGoal(before),
        }),
      );
      return;
    }

    if (before.status === "active") {
      console.log(
        JSON.stringify({
          ok: true,
          action,
          method: "thread/goal/get",
          intendedMethod: "thread/goal/set",
          changed: false,
          reason: "already-active",
          userAgent: client.userAgent,
          before: publicGoal(before),
          after: publicGoal(before),
        }),
      );
      return;
    }
    if (before.status !== "blocked") {
      throw new Error(
        `refusing blocked-only recovery from status ${JSON.stringify(before.status)}`,
      );
    }

    const setResult = await client.request("thread/goal/set", {
      threadId,
      status: "active",
    });
    if (setResult.goal?.threadId !== threadId || setResult.goal?.status !== "active") {
      throw new Error("thread/goal/set did not return the expected active Goal");
    }

    const afterResult = await client.request("thread/goal/get", { threadId });
    const after = afterResult.goal;
    if (!after || after.threadId !== threadId || after.status !== "active") {
      throw new Error("authoritative post-set verification did not return active");
    }

    console.log(
      JSON.stringify({
        ok: true,
        action,
        method: "thread/goal/set",
        changed: true,
        userAgent: client.userAgent,
        before: publicGoal(before),
        after: publicGoal(after),
      }),
    );
  } finally {
    client.close();
  }
}

main().catch((error) => {
  console.error(
    JSON.stringify({
      ok: false,
      error: error instanceof Error ? error.message : String(error),
    }),
  );
  process.exitCode = 1;
});
