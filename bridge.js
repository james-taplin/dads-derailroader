#!/usr/bin/env node
'use strict';

// Claude <-> Codex bridge.
//
//   node bridge.js mcp --name Claude   connector an app launches (set up by setup.js)
//   node bridge.js open                start the bridge if needed and open the control panel
//   node bridge.js stop                shut the bridge down (it restarts on next use)
//   node bridge.js hub                 run the bridge in the foreground

const config = require('./src/config');

const [command, ...rest] = process.argv.slice(2);

async function main() {
  const major = Number(process.versions.node.split('.')[0]);
  if (major < 18) {
    console.error(`The bridge needs Node.js 18 or newer (you have ${process.versions.node}). Get it from https://nodejs.org`);
    process.exit(1);
  }

  switch (command) {
    case 'mcp':
      require('./src/mcp').runMcp(rest);
      break;
    case 'hub': {
      const { startHub } = require('./src/hub');
      try {
        const hub = await startHub({ openBrowser: false });
        console.error(`Bridge running. Control panel: ${hub.url}`);
      } catch (err) {
        console.error(err.code === 'EADDRINUSE' ? `Port ${config.port()} is already in use (the bridge may already be running).` : err.message);
        process.exit(1);
      }
      break;
    }
    case 'open': {
      await require('./src/mcp').ensureHub(config.port());
      require('./src/hub').openInBrowser(config.panelUrl());
      console.log(`Control panel: ${config.panelUrl()}`);
      break;
    }
    case 'stop': {
      const fs = require('fs');
      const path = require('path');
      try {
        const token = fs.readFileSync(path.join(config.home(), 'token'), 'utf8').trim();
        await fetch(`http://127.0.0.1:${config.port()}/api/panel/shutdown`, {
          method: 'POST',
          headers: { 'x-bridge-token': token },
        });
        console.log('Bridge stopped.');
      } catch {
        console.log("The bridge wasn't running.");
      }
      break;
    }
    default:
      console.log('Usage: node bridge.js open | stop | hub | mcp --name <Name>\nTo set things up, run: node setup.js "<your project folder>"');
  }
}

main();
