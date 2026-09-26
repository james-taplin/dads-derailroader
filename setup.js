#!/usr/bin/env node
'use strict';

// Connects Claude and Codex to the bridge for one or more project folders.
//
//   node setup.js "/path/to/my project"              set up (safe to run again)
//   node setup.js --uninstall "/path/to/my project"  undo everything setup did
//
// What it changes:
//   <project>/.mcp.json                    tells Claude how to start the bridge
//   <project>/.claude/settings.local.json  lets Claude use the bridge without asking every message
//                                          (starting a chat still needs your OK)
//   <project>/CLAUDE.md and AGENTS.md      a short section teaching both agents how to use it
//   ~/.codex/config.toml                   tells Codex how to start the bridge
// Any file it changes is backed up first as <file>.llw-backup.

const fs = require('fs');
const os = require('os');
const path = require('path');
const config = require('./src/config');

const SERVER = 'llw-bridge';
const CODEX_SERVER = 'llw_bridge';
const BRIDGE = path.join(__dirname, 'bridge.js');
const START = '<!-- llw-bridge:start -->';
const END = '<!-- llw-bridge:end -->';
const TOML_START = '# llw-bridge:start (added by the Claude <-> Codex bridge setup)';
const TOML_END = '# llw-bridge:end';
const AUTO_ALLOWED = ['join_conversation', 'say_and_wait', 'wait_for_reply', 'end_conversation']
  .map((tool) => `mcp__${SERVER}__${tool}`);

const changed = [];

function write(file, content) {
  const before = fs.existsSync(file) ? fs.readFileSync(file, 'utf8') : null;
  if (before === content) return;
  if (before !== null && !fs.existsSync(`${file}.llw-backup`)) fs.writeFileSync(`${file}.llw-backup`, before);
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, content);
  changed.push(file);
}

function readJson(file) {
  if (!fs.existsSync(file)) return {};
  try {
    return JSON.parse(fs.readFileSync(file, 'utf8'));
  } catch {
    throw new Error(`${file} isn't valid JSON, so I left it alone. Fix or remove it and run setup again.`);
  }
}

function writeJson(file, data, removeIfEmpty) {
  if (removeIfEmpty && Object.keys(data).length === 0) {
    if (fs.existsSync(file)) {
      fs.rmSync(file);
      changed.push(`${file} (removed)`);
    }
    return;
  }
  write(file, `${JSON.stringify(data, null, 2)}\n`);
}

function withoutBlock(text, start, end) {
  const pattern = new RegExp(`\\n*${start.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}[\\s\\S]*?${end.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\n?`, 'g');
  return text.replace(pattern, '\n\n');
}

function setBlock(file, start, end, body, install) {
  const before = fs.existsSync(file) ? fs.readFileSync(file, 'utf8') : '';
  if (!install && !before.includes(start)) return;
  let text = withoutBlock(before, start, end).replace(/\n+$/, '');
  if (install) text = `${text ? `${text}\n\n` : ''}${start}\n${body.trim()}\n${end}`;
  if (!text.trim()) {
    if (before) {
      fs.rmSync(file);
      changed.push(`${file} (removed)`);
    }
    return;
  }
  write(file, `${text}\n`);
}

function claudeProject(project, install) {
  const mcpFile = path.join(project, '.mcp.json');
  const mcp = readJson(mcpFile);
  mcp.mcpServers = mcp.mcpServers || {};
  if (install) {
    mcp.mcpServers[SERVER] = { type: 'stdio', command: process.execPath, args: [BRIDGE, 'mcp', '--name', 'Claude'] };
  } else {
    delete mcp.mcpServers[SERVER];
    if (Object.keys(mcp.mcpServers).length === 0) delete mcp.mcpServers;
  }
  writeJson(mcpFile, mcp, !install);

  const settingsFile = path.join(project, '.claude', 'settings.local.json');
  const settings = readJson(settingsFile);
  settings.permissions = settings.permissions || {};
  const allow = (settings.permissions.allow || []).filter((rule) => !AUTO_ALLOWED.includes(rule));
  const servers = (settings.enabledMcpjsonServers || []).filter((name) => name !== SERVER);
  if (install) {
    allow.push(...AUTO_ALLOWED);
    servers.push(SERVER);
  }
  settings.permissions.allow = allow;
  settings.enabledMcpjsonServers = servers;
  if (!allow.length) delete settings.permissions.allow;
  if (!Object.keys(settings.permissions).length) delete settings.permissions;
  if (!servers.length) delete settings.enabledMcpjsonServers;
  writeJson(settingsFile, settings, !install);

  const guide = fs.readFileSync(path.join(__dirname, 'src', 'agent-guide.md'), 'utf8');
  setBlock(path.join(project, 'CLAUDE.md'), START, END, guide, install);
  setBlock(path.join(project, 'AGENTS.md'), START, END, guide, install);
}

function codex(install) {
  const codexHome = process.env.CODEX_HOME || path.join(os.homedir(), '.codex');
  const file = path.join(codexHome, 'config.toml');
  const block = [
    `[mcp_servers.${CODEX_SERVER}]`,
    `command = ${JSON.stringify(process.execPath)}`,
    `args = [${[BRIDGE, 'mcp', '--name', 'Codex'].map((a) => JSON.stringify(a)).join(', ')}]`,
    'startup_timeout_sec = 20',
    'tool_timeout_sec = 300',
  ].join('\n');
  if (install && fs.existsSync(file)) {
    const existing = withoutBlock(fs.readFileSync(file, 'utf8'), TOML_START, TOML_END);
    if (existing.includes(`[mcp_servers.${CODEX_SERVER}]`)) {
      throw new Error(`${file} already has an [mcp_servers.${CODEX_SERVER}] section that setup didn't add. Remove it and run setup again.`);
    }
  }
  setBlock(file, TOML_START, TOML_END, block, install);
}

async function stopRunningBridge() {
  try {
    const token = fs.readFileSync(path.join(config.home(), 'token'), 'utf8').trim();
    await fetch(`http://127.0.0.1:${config.port()}/api/panel/shutdown`, {
      method: 'POST',
      headers: { 'x-bridge-token': token },
      signal: AbortSignal.timeout(1500),
    });
  } catch {
    // Not running, which is fine.
  }
}

async function main() {
  const args = process.argv.slice(2);
  const install = !args.includes('--uninstall');
  const projects = args.filter((a) => !a.startsWith('--')).map((p) => path.resolve(p.replace(/^~(?=$|[\\/])/, os.homedir())));

  if (Number(process.versions.node.split('.')[0]) < 18) {
    console.error(`The bridge needs Node.js 18 or newer (you have ${process.versions.node}). Get it from https://nodejs.org`);
    process.exit(1);
  }
  if (!projects.length) {
    console.log('Usage: node setup.js "/path/to/your project folder" [more folders...]\n       node setup.js --uninstall "/path/to/your project folder"');
    process.exit(1);
  }
  for (const project of projects) {
    if (!fs.existsSync(project) || !fs.statSync(project).isDirectory()) {
      console.error(`Can't find the folder ${project}`);
      process.exit(1);
    }
  }

  try {
    for (const project of projects) claudeProject(project, install);
    codex(install);
  } catch (err) {
    console.error(err.message);
    process.exit(1);
  }
  // Restart the bridge so it runs the version that's installed now.
  await stopRunningBridge();

  console.log(changed.length ? `Updated:\n${changed.map((f) => `  ${f}`).join('\n')}` : 'Everything was already set up.');
  if (install) {
    console.log(`
All set. Next:
  1. Close and reopen the Claude and Codex apps (or start new sessions) in ${projects.length > 1 ? 'these folders' : 'that folder'}.
  2. If Claude or Codex asks whether to allow the "${SERVER}" / "${CODEX_SERVER}" server or its tools, say yes.
  3. Try it: in Claude, ask "Can you check this plan with Codex?"
The control panel lives at ${config.panelUrl()} (it opens by itself when a chat starts).`);
  } else {
    console.log('\nThe bridge has been removed from those folders and from Codex.');
  }
}

main();
