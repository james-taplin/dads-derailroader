'use strict';

const os = require('os');
const path = require('path');

const VERSION = '0.1.0';

function port() {
  return Number(process.env.LLW_BRIDGE_PORT) || 7777;
}

function home() {
  return process.env.LLW_BRIDGE_HOME || path.join(os.homedir(), '.llw-bridge');
}

function panelUrl() {
  return `http://localhost:${port()}`;
}

module.exports = { VERSION, port, home, panelUrl };
