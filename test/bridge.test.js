'use strict';

// End-to-end tests: two real connector processes (playing Claude and Codex)
// talk MCP over stdio to a real hub, and the "panel" drives it over HTTP.

const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawn, execFileSync } = require('child_process');
const { Store } = require('../src/conversations');

const ROOT = path.join(__dirname, '..');
const HOME = fs.mkdtempSync(path.join(os.tmpdir(), 'llw-test-'));
const PORT = 20000 + Math.floor(Math.random() * 20000);
const ENV = { ...process.env, LLW_BRIDGE_HOME: HOME, LLW_BRIDGE_PORT: String(PORT), LLW_NO_BROWSER: '1' };

class Agent {
  constructor(name, waitSeconds = 1) {
    this.proc = spawn(process.execPath, [path.join(ROOT, 'bridge.js'), 'mcp', '--name', name, '--wait-seconds', String(waitSeconds)], { env: ENV });
    this.nextId = 1;
    this.pending = new Map();
    let buffer = '';
    this.proc.stdout.on('data', (chunk) => {
      buffer += chunk;
      let i;
      while ((i = buffer.indexOf('\n')) >= 0) {
        const msg = JSON.parse(buffer.slice(0, i));
        buffer = buffer.slice(i + 1);
        this.pending.get(msg.id)?.(msg);
        this.pending.delete(msg.id);
      }
    });
  }

  request(method, params) {
    const id = this.nextId++;
    this.proc.stdin.write(`${JSON.stringify({ jsonrpc: '2.0', id, method, params })}\n`);
    const promise = new Promise((resolve) => this.pending.set(id, resolve));
    promise.id = id;
    return promise;
  }

  call(name, args = {}) {
    const promise = this.request('tools/call', { name, arguments: args });
    const text = promise.then((msg) => msg.result.content[0].text);
    text.id = promise.id;
    return text;
  }

  cancel(id) {
    this.proc.stdin.write(`${JSON.stringify({ jsonrpc: '2.0', method: 'notifications/cancelled', params: { requestId: id } })}\n`);
  }

  close() {
    this.proc.kill();
  }
}

function token() {
  return fs.readFileSync(path.join(HOME, 'token'), 'utf8').trim();
}

async function panel(action, body) {
  const res = await fetch(`http://127.0.0.1:${PORT}/api/panel/${action}`, {
    method: 'POST',
    headers: { 'content-type': 'application/json', 'x-bridge-token': token() },
    body: JSON.stringify(body),
  });
  return res.json();
}

async function snapshot() {
  const controller = new AbortController();
  const res = await fetch(`http://127.0.0.1:${PORT}/api/events?token=${token()}`, { signal: controller.signal });
  const reader = res.body.getReader();
  let text = '';
  while (!text.includes('\n\n')) text += new TextDecoder().decode((await reader.read()).value);
  controller.abort();
  return JSON.parse(text.split('data: ')[1].split('\n')[0]).conversations;
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function stopHub() {
  await panel('shutdown', {}).catch(() => {});
  for (let i = 0; i < 50; i++) {
    try {
      await fetch(`http://127.0.0.1:${PORT}/api/health`);
    } catch {
      return;
    }
    await sleep(50);
  }
}

test('two agents hold a conversation that the user can steer', async (t) => {
  const claude = new Agent('Claude');
  const codex = new Agent('Codex');
  t.after(async () => {
    claude.close();
    codex.close();
    await stopHub();
  });

  const init = await claude.request('initialize', { protocolVersion: '2025-06-18', capabilities: {}, clientInfo: { name: 't', version: '1' } });
  assert.strictEqual(init.result.serverInfo.name, 'llw-bridge');
  await codex.request('initialize', { protocolVersion: '2025-06-18', capabilities: {}, clientInfo: { name: 't', version: '1' } });
  const tools = await claude.request('tools/list', {});
  assert.deepStrictEqual(tools.result.tools.map((x) => x.name),
    ['start_conversation', 'join_conversation', 'say_and_wait', 'wait_for_reply', 'end_conversation']);

  // Claude starts a chat.
  const started = await claude.call('start_conversation', { topic: 'Plan review', message: 'Hi Codex, can you review plan.md?', with: 'Codex' });
  const id = started.match(/join bridge conversation ([a-z]+-[a-z]+)/)[1];
  assert.match(started, /localhost:\d+/);

  // Before Codex joins, Claude's wait times out politely.
  assert.match(await claude.call('wait_for_reply'), /Codex hasn't joined yet/);
  assert.match(await claude.call('say_and_wait', { message: 'hello?' }), /NOT sent: Codex hasn't joined/);

  // Codex joins without needing the code and sees the opening message.
  const joined = await codex.call('join_conversation');
  assert.match(joined, new RegExp(id));
  assert.match(joined, /Claude said:[\s\S]*review plan\.md/);
  assert.match(joined, /reply to Claude with say_and_wait/);

  // Claude is listening; Codex's reply wakes it up.
  const claudeWaiting = claude.call('wait_for_reply');
  await sleep(100);
  assert.match(await claude.call('say_and_wait', { message: 'too soon' }), /NOT sent: it's Codex's turn/);
  const codexReply = codex.call('say_and_wait', { message: 'Looks good, but step 3 is risky.' });
  const heard = await claudeWaiting;
  assert.match(heard, /Codex said:[\s\S]*step 3 is risky/);
  assert.match(heard, /It's your turn/);
  assert.match(await codexReply, /Your message was delivered[\s\S]*Claude is still working/);

  // The user interjects while it's Claude's turn: Claude's next message is held back so it can take it into account.
  await panel('interject', { id, text: 'Please keep step 3, it is required.' });
  const held = await claude.call('say_and_wait', { message: 'Let us drop step 3.' });
  assert.match(held, /NOT sent[\s\S]*/);
  assert.match(held, /The user \(the human you both work for\) interjected:[\s\S]*keep step 3/);
  const codexListening = codex.call('wait_for_reply');
  await sleep(100);
  assert.match(await claude.call('say_and_wait', { message: 'OK, keeping step 3 but adding a backup first.' }), /Codex is still working|delivered/);
  const codexHeard = await codexListening;
  assert.match(codexHeard, /interjected:[\s\S]*keep step 3/);
  assert.match(codexHeard, /Claude said:[\s\S]*adding a backup/);

  // Pause: Codex is told to hold; resume lets it carry on.
  await panel('pause', { id });
  assert.match(await codex.call('wait_for_reply'), /paused/);
  const afterResume = codex.call('wait_for_reply');
  await sleep(100);
  await panel('resume', { id });
  assert.match(await afterResume, /It's your turn/);

  // A cancelled wait (user pressed Esc) stops listening.
  const claudeWait = claude.call('wait_for_reply');
  await sleep(200);
  let conv = (await snapshot()).find((c) => c.id === id);
  assert.strictEqual(conv.participants.find((p) => p.name === 'Claude').listening, true);
  claude.cancel(claudeWait.id);
  await sleep(200);
  conv = (await snapshot()).find((c) => c.id === id);
  assert.strictEqual(conv.participants.find((p) => p.name === 'Claude').listening, false);

  // Stop: whoever is waiting is told to wrap up and summarise.
  const lastWait = claude.call('wait_for_reply');
  await sleep(100);
  await panel('stop', { id });
  assert.match(await lastWait, /The user has ended this conversation[\s\S]*summary/);
  assert.match(await codex.call('say_and_wait', { message: 'one more thing' }), /The user has ended this conversation/);

  conv = (await snapshot()).find((c) => c.id === id);
  assert.strictEqual(conv.status, 'ended');
  assert.deepStrictEqual(conv.messages.filter((m) => m.from !== 'system').map((m) => m.from), ['A', 'B', 'human', 'A']);
  assert.ok(!JSON.stringify(conv).includes('session'), 'panel snapshot must not leak session ids');
});

test('the hub rejects requests without the token or from other hosts', async (t) => {
  const agent = new Agent('Probe');
  t.after(async () => {
    agent.close();
    await stopHub();
  });
  await agent.call('wait_for_reply'); // Starts the hub if needed.
  const noToken = await fetch(`http://127.0.0.1:${PORT}/api/panel/pause`, { method: 'POST', body: '{}' });
  assert.strictEqual(noToken.status, 401);
  const status = await new Promise((resolve, reject) => {
    require('http').get({ host: '127.0.0.1', port: PORT, path: '/', headers: { host: 'evil.example' } }, (res) => resolve(res.statusCode)).on('error', reject);
  });
  assert.strictEqual(status, 403);
});

test('turn limit and repetition pause the conversation', async () => {
  const store = new Store({ dataDir: fs.mkdtempSync(path.join(os.tmpdir(), 'llw-store-')) });
  const a = { session: 'a', name: 'Claude' };
  const b = { session: 'b', name: 'Codex' };
  const { conv } = store.start(a, { topic: 't', message: 'm1' });
  store.join(b);
  conv.maxTurns = 3;
  // Each agent has to have heard the other before it can speak.
  const say = async (who, text) => {
    await store.wait(who, conv.id, { timeoutMs: 10 });
    return store.say(who, conv.id, text);
  };
  assert.strictEqual((await say(b, 'm2')).kind, 'sent');
  const third = await say(a, 'm3');
  assert.strictEqual(conv.status, 'paused');
  assert.strictEqual(conv.pauseReason, 'turn_limit');
  assert.match(third.note, /limit of 3/);
  store.panel('resume', { id: conv.id });
  assert.strictEqual(conv.status, 'active');
  assert.strictEqual(conv.maxTurns, 13);

  await say(b, 'Same thing again');
  await say(a, 'ok');
  await say(b, 'same thing   AGAIN');
  assert.strictEqual(conv.pauseReason, 'repeating');

  // Resuming after the agents' connectors restart still finds them by name.
  const restarted = { session: 'a2', name: 'Claude' };
  store.panel('resume', { id: conv.id });
  await store.wait(restarted, undefined, { timeoutMs: 10 });
  assert.strictEqual(store.say(restarted, undefined, 'new approach').kind, 'sent');
  const ended = store.end(b, conv.id, 'We agreed on the new approach.');
  assert.strictEqual(ended.kind, 'ended');
  assert.strictEqual(conv.endedBy, 'B');
});

test('setup installs and uninstalls cleanly', () => {
  const project = fs.mkdtempSync(path.join(os.tmpdir(), 'llw-project-'));
  const codexHome = fs.mkdtempSync(path.join(os.tmpdir(), 'llw-codex-'));
  const originalClaudeMd = '# My project\n\nExisting notes.\n';
  const originalToml = 'model = "gpt-5"\n\n[mcp_servers.other]\ncommand = "other"\n';
  fs.writeFileSync(path.join(project, 'CLAUDE.md'), originalClaudeMd);
  fs.writeFileSync(path.join(codexHome, 'config.toml'), originalToml);
  const env = { ...ENV, CODEX_HOME: codexHome };
  const run = (...args) => execFileSync(process.execPath, [path.join(ROOT, 'setup.js'), ...args], { env, encoding: 'utf8' });

  run(project);
  run(project); // Running twice must not duplicate anything.
  const mcp = JSON.parse(fs.readFileSync(path.join(project, '.mcp.json'), 'utf8'));
  assert.deepStrictEqual(mcp.mcpServers['llw-bridge'].args.slice(1), ['mcp', '--name', 'Claude']);
  const settings = JSON.parse(fs.readFileSync(path.join(project, '.claude', 'settings.local.json'), 'utf8'));
  assert.ok(settings.permissions.allow.includes('mcp__llw-bridge__say_and_wait'));
  assert.ok(!settings.permissions.allow.includes('mcp__llw-bridge__start_conversation'), 'starting a chat must still ask the user');
  assert.deepStrictEqual(settings.enabledMcpjsonServers, ['llw-bridge']);
  const claudeMd = fs.readFileSync(path.join(project, 'CLAUDE.md'), 'utf8');
  assert.ok(claudeMd.startsWith(originalClaudeMd.trim()));
  assert.strictEqual(claudeMd.split('llw-bridge:start').length, 2);
  assert.ok(fs.readFileSync(path.join(project, 'AGENTS.md'), 'utf8').includes('join_conversation'));
  const toml = fs.readFileSync(path.join(codexHome, 'config.toml'), 'utf8');
  assert.strictEqual(toml.split('[mcp_servers.llw_bridge]').length, 2);
  assert.match(toml, /args = \[".*bridge\.js", "mcp", "--name", "Codex"\]/);

  run('--uninstall', project);
  assert.strictEqual(fs.readFileSync(path.join(project, 'CLAUDE.md'), 'utf8'), originalClaudeMd);
  assert.strictEqual(fs.readFileSync(path.join(codexHome, 'config.toml'), 'utf8'), originalToml);
  assert.ok(!fs.existsSync(path.join(project, '.mcp.json')));
  assert.ok(!fs.existsSync(path.join(project, 'AGENTS.md')));
  assert.ok(!fs.existsSync(path.join(project, '.claude', 'settings.local.json')));
});
