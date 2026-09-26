'use strict';

// The connector each app launches (Claude and Codex both run
// `node bridge.js mcp --name <Name>`). It speaks MCP over stdin/stdout and
// forwards every tool call to the hub, starting the hub first if it isn't
// running yet. Nothing but protocol messages may be written to stdout.

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const readline = require('readline');
const { spawn } = require('child_process');
const config = require('./config');

const BRIDGE_SCRIPT = path.join(__dirname, '..', 'bridge.js');

const SERVER_INSTRUCTIONS = `This server lets you hold a live, turn-by-turn conversation with another AI agent (for example Claude talking with Codex) while the user watches and controls it from a browser panel.
- Only start a conversation after the user has clearly agreed to it.
- Once in a conversation, keep going: after each reply call say_and_wait, and whenever a result says to wait, call wait_for_reply again. Don't stop to ask the user questions mid-conversation; they can interject, pause or stop from the panel.
- Messages marked as coming from the user take priority over the other agent.
- When the conversation ends, stop calling these tools and give the user a short summary.`;

const conversationArg = {
  type: 'string',
  description: 'The conversation code (e.g. "blue-otter"). Optional: leave it out to use the conversation you are already in.',
};

const TOOLS = [
  {
    name: 'start_conversation',
    description: 'Start a live chat with another AI agent (e.g. Codex or Claude) through the bridge. ONLY call this after the user has said yes to you starting a chat. Sends your opening message and returns a short code the user gives the other agent so it can join.',
    inputSchema: {
      type: 'object',
      properties: {
        topic: { type: 'string', description: 'A short title for the chat, e.g. "Review the database migration plan".' },
        message: { type: 'string', description: 'Your opening message to the other agent: introduce what you need, with enough context (file paths, goals, constraints) for them to help.' },
        with: { type: 'string', description: 'Who you want to talk to, e.g. "Codex" or "Claude".' },
      },
      required: ['topic', 'message'],
    },
  },
  {
    name: 'join_conversation',
    description: 'Join a bridge chat that another AI agent started. Use this when the user asks you to join a bridge conversation or bridge chat. If they give a code like "blue-otter", pass it; if not, leave it out to join the latest chat that is waiting (no need to ask for a code). Returns the conversation so far.',
    inputSchema: {
      type: 'object',
      properties: { conversation: { type: 'string', description: 'The conversation code, e.g. "blue-otter". Leave it out to join the latest chat waiting to be joined.' } },
    },
  },
  {
    name: 'say_and_wait',
    description: 'Send your next message in the bridge chat, then wait for the reply. Follow the NEXT STEP in the result (usually: call wait_for_reply again if the reply has not arrived yet).',
    inputSchema: {
      type: 'object',
      properties: {
        message: { type: 'string', description: 'Your message to the other agent. Keep it focused; one message per turn.' },
        conversation: conversationArg,
      },
      required: ['message'],
    },
  },
  {
    name: 'wait_for_reply',
    description: 'Wait for the next message in the bridge chat (from the other agent or the user). Returns after about a minute even if nothing arrived; follow the NEXT STEP in the result.',
    inputSchema: { type: 'object', properties: { conversation: conversationArg } },
  },
  {
    name: 'end_conversation',
    description: 'End the bridge chat when you and the other agent have finished, including a short summary of what you agreed. The user can also end it from the panel.',
    inputSchema: {
      type: 'object',
      properties: {
        summary: { type: 'string', description: 'A short summary of the outcome and any agreed next steps.' },
        conversation: conversationArg,
      },
    },
  },
];

const ACTIONS = {
  start_conversation: 'start',
  join_conversation: 'join',
  say_and_wait: 'say',
  wait_for_reply: 'wait',
  end_conversation: 'end',
};

function parseArgs(argv) {
  const opts = { name: 'Agent', waitSeconds: 50 };
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === '--name') opts.name = argv[++i];
    else if (argv[i] === '--wait-seconds') opts.waitSeconds = Number(argv[++i]) || opts.waitSeconds;
  }
  return opts;
}

async function health(port) {
  try {
    const res = await fetch(`http://127.0.0.1:${port}/api/health`, { signal: AbortSignal.timeout(1500) });
    const body = await res.json();
    return body.app === 'llw-bridge' ? 'ok' : 'other';
  } catch (err) {
    if (err instanceof SyntaxError) return 'other';
    return 'down';
  }
}

async function ensureHub(port) {
  let state = await health(port);
  if (state === 'ok') return;
  if (state === 'other') throw new Error(`Another program is already using port ${port}, so the bridge can't start. Set LLW_BRIDGE_PORT to a different number.`);
  spawn(process.execPath, [BRIDGE_SCRIPT, 'hub'], { detached: true, stdio: 'ignore', windowsHide: true, env: process.env }).unref();
  for (let i = 0; i < 40; i++) {
    await new Promise((r) => setTimeout(r, 150));
    state = await health(port);
    if (state === 'ok') return;
  }
  throw new Error(`The bridge didn't start. Check ${path.join(config.home(), 'hub.log')} for details.`);
}

function runMcp(argv) {
  const opts = parseArgs(argv);
  const port = config.port();
  const session = crypto.randomUUID();
  const inflight = new Map();

  const send = (msg) => process.stdout.write(`${JSON.stringify(msg)}\n`);
  const reply = (id, result) => send({ jsonrpc: '2.0', id, result });
  const fail = (id, code, message) => send({ jsonrpc: '2.0', id, error: { code, message } });

  async function callHub(action, args, signal) {
    await ensureHub(port);
    const token = fs.readFileSync(path.join(config.home(), 'token'), 'utf8').trim();
    const res = await fetch(`http://127.0.0.1:${port}/api/agent/${action}`, {
      method: 'POST',
      headers: { 'content-type': 'application/json', 'x-bridge-token': token },
      body: JSON.stringify({ ...args, session, name: opts.name, waitSeconds: opts.waitSeconds }),
      signal,
    });
    const body = await res.json();
    if (!res.ok) return { text: body.error || `Bridge error (${res.status}).`, isError: true };
    return { text: body.text, isError: false };
  }

  async function callTool(id, params) {
    const action = ACTIONS[params && params.name];
    if (!action) return fail(id, -32602, `Unknown tool: ${params && params.name}`);
    const controller = new AbortController();
    inflight.set(id, controller);
    try {
      const { text, isError } = await callHub(action, params.arguments || {}, controller.signal);
      reply(id, { content: [{ type: 'text', text }], isError });
    } catch (err) {
      if (controller.signal.aborted) return undefined; // Cancelled: no response is expected.
      reply(id, { content: [{ type: 'text', text: `Couldn't reach the bridge: ${err.message}` }], isError: true });
    } finally {
      inflight.delete(id);
    }
    return undefined;
  }

  function handle(msg) {
    const { id, method, params } = msg;
    switch (method) {
      case 'initialize':
        ensureHub(port).catch(() => {}); // Warm up so the panel is available straight away.
        return reply(id, {
          protocolVersion: (params && params.protocolVersion) || '2025-06-18',
          capabilities: { tools: {} },
          serverInfo: { name: 'llw-bridge', version: config.VERSION },
          instructions: SERVER_INSTRUCTIONS,
        });
      case 'ping':
        return reply(id, {});
      case 'tools/list':
        return reply(id, { tools: TOOLS });
      case 'tools/call':
        return callTool(id, params);
      case 'notifications/cancelled': {
        const controller = params && inflight.get(params.requestId);
        if (controller) controller.abort();
        return undefined;
      }
      default:
        if (id !== undefined && method) return fail(id, -32601, `Method not found: ${method}`);
        return undefined;
    }
  }

  const rl = readline.createInterface({ input: process.stdin });
  rl.on('line', (line) => {
    if (!line.trim()) return;
    let msg;
    try {
      msg = JSON.parse(line);
    } catch {
      return fail(null, -32700, 'Parse error');
    }
    for (const m of Array.isArray(msg) ? msg : [msg]) handle(m);
    return undefined;
  });
  rl.on('close', () => process.exit(0));
}

module.exports = { runMcp, ensureHub, TOOLS };
