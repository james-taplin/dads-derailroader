'use strict';

// The hub: one small local web server that holds every conversation. The
// agents' connectors (src/mcp.js) talk to it, and it serves the control panel.
// It only listens on 127.0.0.1, and every request needs the secret token from
// ~/.llw-bridge/token so other web pages can't poke at it.

const fs = require('fs');
const http = require('http');
const path = require('path');
const crypto = require('crypto');
const { spawn } = require('child_process');
const config = require('./config');
const { Store, BridgeError, formatResult } = require('./conversations');

const MAX_WAIT_SECONDS = 280;

function log(home, ...args) {
  try {
    fs.appendFileSync(path.join(home, 'hub.log'), `${new Date().toISOString()} ${args.join(' ')}\n`);
  } catch {
    // Logging is best-effort.
  }
}

function readOrCreateToken(home) {
  fs.mkdirSync(home, { recursive: true });
  const file = path.join(home, 'token');
  try {
    fs.writeFileSync(file, crypto.randomBytes(24).toString('hex'), { flag: 'wx', mode: 0o600 });
  } catch (err) {
    if (err.code !== 'EEXIST') throw err;
  }
  return fs.readFileSync(file, 'utf8').trim();
}

function openInBrowser(url) {
  const [cmd, args] = process.platform === 'darwin' ? ['open', [url]]
    : process.platform === 'win32' ? ['cmd', ['/c', 'start', '', url]]
      : ['xdg-open', [url]];
  try {
    spawn(cmd, args, { stdio: 'ignore', detached: true, windowsHide: true }).on('error', () => {}).unref();
  } catch {
    // No browser available; the agent also tells the user the address.
  }
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    let data = '';
    req.setEncoding('utf8');
    req.on('data', (chunk) => {
      data += chunk;
      if (data.length > 1_000_000) reject(new BridgeError('Request too large.'));
    });
    req.on('end', () => {
      try {
        resolve(data ? JSON.parse(data) : {});
      } catch {
        reject(new BridgeError('Request was not valid JSON.'));
      }
    });
    req.on('error', reject);
  });
}

function sendJson(res, status, body) {
  if (res.writableEnded || res.destroyed) return;
  res.writeHead(status, { 'content-type': 'application/json', 'cache-control': 'no-store' });
  res.end(JSON.stringify(body));
}

function startHub({ port = config.port(), home = config.home(), openBrowser = !process.env.LLW_NO_BROWSER } = {}) {
  const token = readOrCreateToken(home);
  const store = new Store({ dataDir: path.join(home, 'conversations') });
  const panelUrl = `http://localhost:${port}`;
  const panelHtml = fs.readFileSync(path.join(__dirname, 'panel.html'), 'utf8').replace('__TOKEN__', token);
  const panelClients = new Set();
  const allowedHosts = new Set([`127.0.0.1:${port}`, `localhost:${port}`]);

  let pushTimer = null;
  function pushState() {
    if (pushTimer) return;
    pushTimer = setTimeout(() => {
      pushTimer = null;
      const data = `event: state\ndata: ${JSON.stringify({ conversations: store.snapshot() })}\n\n`;
      for (const res of panelClients) res.write(data);
    }, 30);
  }
  store.on('change', pushState);

  async function agentAction(action, body, signal) {
    const who = { session: String(body.session || ''), name: String(body.name || 'Agent') };
    if (!who.session) throw new BridgeError('Missing session.');
    const waitMs = Math.min(Number(body.waitSeconds) || 50, MAX_WAIT_SECONDS) * 1000;
    const wait = () => store.wait(who, body.conversation, { timeoutMs: waitMs, signal });
    let result;
    switch (action) {
      case 'start':
        result = store.start(who, { topic: body.topic, message: body.message, withName: body.with });
        if (openBrowser && panelClients.size === 0) openInBrowser(panelUrl);
        break;
      case 'join':
        result = store.join(who, body.conversation);
        break;
      case 'say': {
        result = store.say(who, body.conversation, body.message);
        if (result.kind === 'sent') {
          const reply = await wait();
          return `${formatResult(result, { panelUrl })}\n\n${formatResult(reply, { panelUrl }).replace(/^\[[^\n]*\]\n\n/, '')}`;
        }
        break;
      }
      case 'wait':
        result = await wait();
        break;
      case 'end':
        result = store.end(who, body.conversation, body.summary);
        break;
      default:
        throw new BridgeError(`Unknown action "${action}".`);
    }
    return formatResult(result, { panelUrl });
  }

  const server = http.createServer(async (req, res) => {
    try {
      if (!allowedHosts.has(req.headers.host)) return sendJson(res, 403, { error: 'Forbidden host.' });
      const url = new URL(req.url, panelUrl);

      if (req.method === 'GET' && url.pathname === '/api/health') {
        return sendJson(res, 200, { app: 'llw-bridge', version: config.VERSION, pid: process.pid });
      }
      if (req.method === 'GET' && (url.pathname === '/' || url.pathname === '/index.html')) {
        res.writeHead(200, { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-store' });
        return res.end(panelHtml);
      }

      const supplied = req.headers['x-bridge-token'] || url.searchParams.get('token');
      if (supplied !== token) return sendJson(res, 401, { error: 'Missing or wrong bridge token.' });

      if (req.method === 'GET' && url.pathname === '/api/events') {
        res.writeHead(200, { 'content-type': 'text/event-stream', 'cache-control': 'no-store', connection: 'keep-alive' });
        res.write(`event: state\ndata: ${JSON.stringify({ conversations: store.snapshot() })}\n\n`);
        panelClients.add(res);
        const keepAlive = setInterval(() => res.write(': ping\n\n'), 20_000);
        res.on('close', () => {
          clearInterval(keepAlive);
          panelClients.delete(res);
        });
        return undefined;
      }

      const match = url.pathname.match(/^\/api\/(agent|panel)\/([a-z_]+)$/);
      if (req.method !== 'POST' || !match) return sendJson(res, 404, { error: 'Not found.' });
      const body = await readBody(req);

      if (match[1] === 'panel') {
        if (match[2] === 'shutdown') {
          sendJson(res, 200, { ok: true });
          log(home, 'shutting down on request');
          setTimeout(() => process.exit(0), 100);
          return undefined;
        }
        store.panel(match[2], body);
        return sendJson(res, 200, { ok: true });
      }

      const controller = new AbortController();
      res.on('close', () => {
        if (!res.writableFinished) controller.abort();
      });
      const text = await agentAction(match[2], body, controller.signal);
      return sendJson(res, 200, { text });
    } catch (err) {
      if (err instanceof BridgeError) return sendJson(res, 400, { error: err.message });
      log(home, 'error:', err && err.stack);
      return sendJson(res, 500, { error: `The bridge hit an unexpected error: ${err.message}` });
    }
  });
  server.requestTimeout = 0;
  server.headersTimeout = 60_000;

  return new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(port, '127.0.0.1', () => {
      log(home, `hub listening on ${panelUrl} (pid ${process.pid})`);
      resolve({ server, store, token, url: panelUrl, port: server.address().port });
    });
  });
}

module.exports = { startHub, openInBrowser, readOrCreateToken };
