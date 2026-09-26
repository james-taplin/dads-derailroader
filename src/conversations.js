'use strict';

// Conversation state and turn-taking rules. Everything the agents and the
// control panel can do goes through the Store, which persists each
// conversation as a JSON file and emits 'change' so waiters and the panel
// can react.

const fs = require('fs');
const path = require('path');
const { EventEmitter } = require('events');

const ADJECTIVES = ['amber', 'blue', 'brave', 'calm', 'clever', 'cosy', 'gentle', 'golden', 'green',
  'happy', 'kind', 'lucky', 'mellow', 'quiet', 'rosy', 'silver', 'sunny', 'swift', 'tidy', 'warm'];
const ANIMALS = ['badger', 'beagle', 'crane', 'dolphin', 'finch', 'fox', 'hare', 'heron', 'koala',
  'lynx', 'marten', 'otter', 'owl', 'panda', 'puffin', 'robin', 'seal', 'swan', 'tiger', 'wren'];

const DEFAULT_MAX_TURNS = 20;
const EXTRA_TURNS = 10;

class BridgeError extends Error {}

function pick(list) {
  return list[Math.floor(Math.random() * list.length)];
}

function normalise(text) {
  return String(text).toLowerCase().replace(/\s+/g, ' ').trim();
}

class Store extends EventEmitter {
  constructor({ dataDir, idleLimitMs = 15 * 60 * 1000 }) {
    super();
    this.setMaxListeners(0);
    this.dataDir = dataDir;
    this.idleLimitMs = idleLimitMs;
    this.conversations = new Map();
    this.listening = new Map(); // `${id}:${role}` -> number of open waits
    fs.mkdirSync(dataDir, { recursive: true });
    this.load();
  }

  load() {
    for (const file of fs.readdirSync(this.dataDir)) {
      if (!file.endsWith('.json')) continue;
      try {
        const conv = JSON.parse(fs.readFileSync(path.join(this.dataDir, file), 'utf8'));
        this.conversations.set(conv.id, conv);
      } catch {
        // A damaged file shouldn't stop the bridge from starting.
      }
    }
  }

  save(conv) {
    conv.updatedAt = new Date().toISOString();
    const file = path.join(this.dataDir, `${conv.id}.json`);
    fs.writeFileSync(`${file}.tmp`, JSON.stringify(conv, null, 2));
    fs.renameSync(`${file}.tmp`, file);
    this.changed(conv.id);
  }

  // Emitted on the next tick so listeners never run in the middle of an update.
  changed(id) {
    process.nextTick(() => this.emit('change', id));
  }

  list() {
    return [...this.conversations.values()].sort((a, b) => b.createdAt.localeCompare(a.createdAt));
  }

  get(id) {
    const conv = this.conversations.get(normalise(id || ''));
    if (!conv) throw new BridgeError(`There's no bridge conversation called "${id}".`);
    return conv;
  }

  newId() {
    for (let i = 0; i < 1000; i++) {
      const id = `${pick(ADJECTIVES)}-${pick(ANIMALS)}`;
      if (!this.conversations.has(id)) return id;
    }
    return `chat-${Date.now()}`;
  }

  addMessage(conv, from, text) {
    const seq = conv.messages.length ? conv.messages[conv.messages.length - 1].seq + 1 : 1;
    const name = from === 'human' ? 'You' : from === 'system' ? 'Bridge' : this.participant(conv, from).name;
    const message = { seq, from, name, text: String(text).trim(), at: new Date().toISOString() };
    conv.messages.push(message);
    return message;
  }

  participant(conv, role) {
    return conv.participants.find((p) => p.role === role);
  }

  other(conv, me) {
    return conv.participants.find((p) => p.role !== me.role) || null;
  }

  lastSeq(conv) {
    return conv.messages.length ? conv.messages[conv.messages.length - 1].seq : 0;
  }

  // Messages this participant hasn't been shown yet (from the other agent or the user).
  unseen(conv, me) {
    return conv.messages.filter((m) => m.seq > me.lastSeen && m.from !== me.role && m.from !== 'system');
  }

  markSeen(conv, me) {
    me.lastSeen = this.lastSeq(conv);
  }

  // Works out which conversation and which participant an agent's request is about.
  resolve(who, id) {
    const all = this.list();
    // Prefer conversations still going; fall back to ended ones so the agent hears that it ended.
    const groups = id ? [[this.get(id)]] : [all.filter((c) => c.status !== 'ended'), all];
    for (const candidates of groups) {
      for (const conv of candidates) {
        const me = conv.participants.find((p) => p.session === who.session);
        if (me) return { conv, me };
      }
      // The agent's connector may have restarted with a new session id; fall back to its name.
      for (const conv of candidates) {
        const matches = conv.participants.filter((p) => p.name === who.name);
        if (matches.length === 1) {
          matches[0].session = who.session;
          return { conv, me: matches[0] };
        }
      }
    }
    if (id) throw new BridgeError(`You aren't part of bridge conversation "${id}". Use join_conversation to join it.`);
    throw new BridgeError("You aren't in an active bridge conversation. Use start_conversation or join_conversation first.");
  }

  // ---- Agent actions ----

  start(who, { topic, message, withName, maxTurns }) {
    if (!topic || !String(topic).trim()) throw new BridgeError('Please give the conversation a short topic.');
    if (!message || !String(message).trim()) throw new BridgeError('Please include an opening message for the other agent.');
    const now = new Date().toISOString();
    const conv = {
      id: this.newId(),
      topic: String(topic).trim(),
      expecting: withName ? String(withName).trim() : null,
      status: 'waiting_for_join',
      pauseReason: null,
      endedBy: null,
      createdAt: now,
      updatedAt: now,
      participants: [{ role: 'A', name: who.name, session: who.session, lastSeen: 0, waitingSince: null }],
      turn: 'B',
      maxTurns: maxTurns || DEFAULT_MAX_TURNS,
      agentTurns: 1,
      messages: [],
    };
    this.conversations.set(conv.id, conv);
    this.addMessage(conv, 'A', message);
    this.markSeen(conv, conv.participants[0]);
    this.save(conv);
    return { kind: 'started', conv, me: conv.participants[0], messages: [] };
  }

  join(who, id) {
    let conv;
    if (id) {
      conv = this.get(id);
    } else {
      conv = this.list().find((c) => c.status === 'waiting_for_join' && c.participants[0].session !== who.session);
      if (!conv) throw new BridgeError('No bridge conversation is waiting to be joined. Ask the user for the conversation code.');
    }
    if (conv.status === 'ended') throw new BridgeError(`Bridge conversation "${conv.id}" has already ended.`);

    let me = conv.participants.find((p) => p.session === who.session);
    if (!me && conv.participants.length === 2) {
      me = conv.participants.find((p) => p.role === 'B' && p.name === who.name);
      if (me) me.session = who.session;
    }
    if (me && me.role === 'A') throw new BridgeError('You started this conversation, so the other agent needs to join it, not you. Call wait_for_reply to wait for them.');
    if (!me) {
      if (conv.participants.length === 2) throw new BridgeError(`Bridge conversation "${conv.id}" already has two participants.`);
      const taken = conv.participants[0].name;
      const name = who.name === taken ? `${who.name} 2` : who.name;
      me = { role: 'B', name, session: who.session, lastSeen: 0, waitingSince: null };
      conv.participants.push(me);
      if (conv.status === 'waiting_for_join') conv.status = 'active';
      if (conv.status === 'paused' && conv.resumeTo === 'waiting_for_join') conv.resumeTo = 'active';
      this.addMessage(conv, 'system', `${name} joined the conversation.`);
    }
    const messages = this.unseen(conv, me);
    this.markSeen(conv, me);
    this.save(conv);
    return { kind: 'joined', conv, me, messages };
  }

  say(who, id, text) {
    const { conv, me } = this.resolve(who, id);
    if (!text || !String(text).trim()) throw new BridgeError('Your message was empty.');
    if (conv.status === 'ended') return this.deliver(conv, me, 'ended');
    if (conv.status === 'waiting_for_join') return { kind: 'not_joined', conv, me, messages: [] };
    const unseen = this.unseen(conv, me);
    if (unseen.length) return this.deliver(conv, me, 'unseen');
    if (conv.turn !== me.role) return { kind: 'not_your_turn', conv, me, messages: [] };

    const previous = conv.messages.filter((m) => m.from === 'A' || m.from === 'B').slice(-4).map((m) => normalise(m.text));
    this.addMessage(conv, me.role, text);
    this.markSeen(conv, me);
    me.waitingSince = null;
    conv.agentTurns += 1;
    conv.turn = this.other(conv, me).role;

    let note = null;
    if (conv.status === 'active' && previous.includes(normalise(text))) {
      this.pause(conv, 'repeating');
      note = 'The conversation seems to be going round in circles, so the bridge has paused it for the user to decide what to do.';
    } else if (conv.status === 'active' && conv.agentTurns >= conv.maxTurns) {
      this.pause(conv, 'turn_limit');
      note = `The conversation has reached its limit of ${conv.maxTurns} messages, so it's paused until the user decides whether to continue.`;
    }
    this.save(conv);
    return { kind: 'sent', conv, me, messages: [], note };
  }

  // What an agent gets back from waiting right now, or null if it should keep waiting.
  check(conv, me) {
    if (conv.status === 'ended') return this.deliver(conv, me, 'ended');
    if (conv.status === 'active' && conv.turn === me.role) return this.deliver(conv, me, 'your_turn');
    return null;
  }

  deliver(conv, me, kind) {
    const messages = this.unseen(conv, me);
    this.markSeen(conv, me);
    if (kind !== 'unseen') me.waitingSince = null;
    this.save(conv);
    return { kind, conv, me, messages };
  }

  wait(who, id, { timeoutMs, signal } = {}) {
    const { conv, me } = this.resolve(who, id);
    const immediate = this.check(conv, me);
    if (immediate) return Promise.resolve(immediate);
    if (!me.waitingSince) me.waitingSince = Date.now();

    const key = `${conv.id}:${me.role}`;
    this.listening.set(key, (this.listening.get(key) || 0) + 1);
    this.changed(conv.id);

    return new Promise((resolve, reject) => {
      let done = false;
      const finish = (result, error) => {
        if (done) return;
        done = true;
        clearTimeout(timer);
        this.off('change', onChange);
        if (signal) signal.removeEventListener('abort', onAbort);
        this.listening.set(key, Math.max(0, (this.listening.get(key) || 1) - 1));
        this.changed(conv.id);
        if (error) reject(error);
        else resolve(result);
      };
      const onChange = (changedId) => {
        if (done || changedId !== conv.id) return;
        // The conversation may have been deleted from the panel.
        if (!this.conversations.has(conv.id)) return finish({ kind: 'ended', conv, me, messages: [] });
        const result = this.check(conv, me);
        if (result) finish(result);
      };
      const onAbort = () => finish(null, new BridgeError('Wait cancelled.'));
      const onTimeout = () => {
        if (Date.now() - me.waitingSince > this.idleLimitMs) {
          me.waitingSince = null;
          return finish(this.deliver(conv, me, 'idle_release'));
        }
        // Pass on anything the user said in the meantime so the agent isn't in the dark.
        finish(this.deliver(conv, me, 'timeout'));
      };
      const timer = setTimeout(onTimeout, timeoutMs || 50_000);
      this.on('change', onChange);
      if (signal) {
        if (signal.aborted) return onAbort();
        signal.addEventListener('abort', onAbort);
      }
    });
  }

  end(who, id, summary) {
    const { conv, me } = this.resolve(who, id);
    if (conv.status === 'ended') return this.deliver(conv, me, 'ended');
    const text = summary && String(summary).trim()
      ? `I'm ending the conversation here. Summary:\n\n${String(summary).trim()}`
      : "I'm ending the conversation here.";
    this.addMessage(conv, me.role, text);
    this.markSeen(conv, me);
    conv.status = 'ended';
    conv.endedBy = me.role;
    this.addMessage(conv, 'system', `${me.name} ended the conversation.`);
    this.save(conv);
    return { kind: 'ended', conv, me, messages: [] };
  }

  // ---- Control panel actions ----

  pause(conv, reason) {
    if (conv.status === 'ended' || conv.status === 'paused') return;
    conv.resumeTo = conv.status;
    conv.status = 'paused';
    conv.pauseReason = reason;
    const why = {
      user: 'You paused the conversation.',
      turn_limit: `Paused: the conversation reached its limit of ${conv.maxTurns} messages.`,
      repeating: 'Paused: the agents seem to be repeating themselves.',
    }[reason];
    this.addMessage(conv, 'system', why);
  }

  panel(action, { id, text } = {}) {
    const conv = this.get(id);
    switch (action) {
      case 'interject':
        if (conv.status === 'ended') throw new BridgeError('This conversation has already ended.');
        if (!text || !String(text).trim()) throw new BridgeError('Type a message first.');
        this.addMessage(conv, 'human', text);
        break;
      case 'pause':
        this.pause(conv, 'user');
        break;
      case 'resume':
        if (conv.status !== 'paused') return conv;
        if (conv.agentTurns >= conv.maxTurns) conv.maxTurns = conv.agentTurns + EXTRA_TURNS;
        conv.status = conv.resumeTo || 'active';
        conv.pauseReason = null;
        this.addMessage(conv, 'system', 'You resumed the conversation.');
        break;
      case 'more_turns':
        conv.maxTurns = Math.max(conv.maxTurns, conv.agentTurns) + EXTRA_TURNS;
        break;
      case 'stop':
        if (conv.status === 'ended') return conv;
        conv.status = 'ended';
        conv.endedBy = 'human';
        this.addMessage(conv, 'system', 'You ended the conversation.');
        break;
      case 'delete':
        if (conv.status !== 'ended') throw new BridgeError('Stop the conversation before deleting it.');
        this.conversations.delete(conv.id);
        fs.rmSync(path.join(this.dataDir, `${conv.id}.json`), { force: true });
        this.changed(conv.id);
        return null;
      default:
        throw new BridgeError(`Unknown action "${action}".`);
    }
    this.save(conv);
    return conv;
  }

  // What the control panel shows (no session ids).
  snapshot() {
    return this.list().map((conv) => ({
      id: conv.id,
      topic: conv.topic,
      expecting: conv.expecting,
      status: conv.status,
      pauseReason: conv.pauseReason,
      endedBy: conv.endedBy,
      turn: conv.turn,
      agentTurns: conv.agentTurns,
      maxTurns: conv.maxTurns,
      createdAt: conv.createdAt,
      updatedAt: conv.updatedAt,
      participants: conv.participants.map((p) => ({
        role: p.role,
        name: p.name,
        listening: (this.listening.get(`${conv.id}:${p.role}`) || 0) > 0,
      })),
      messages: conv.messages,
    }));
  }
}

// ---- Turning results into plain-English text for the agents ----

function formatMessages(messages) {
  return messages.map((m) => {
    const label = m.from === 'human' ? 'The user (the human you both work for) interjected' : `${m.name} said`;
    return `----- ${label}: -----\n${m.text}`;
  }).join('\n\n');
}

function formatResult(result, { panelUrl }) {
  const { kind, conv, me, messages, note } = result;
  const other = conv.participants.find((p) => p.role !== me.role);
  const otherName = other ? other.name : conv.expecting || 'the other agent';
  const parts = [`[Bridge conversation "${conv.id}" — topic: ${conv.topic}. You are ${me.name}; you're talking with ${otherName}.]`];
  if (note) parts.push(note);
  if (messages.length) parts.push(formatMessages(messages));
  const humanSpoke = messages.some((m) => m.from === 'human');
  const summariseForUser = 'Stop calling bridge tools now. Give the user a brief summary in your own session: what was discussed, what you agreed, and any next steps you suggest.';

  switch (kind) {
    case 'started':
      parts.push(`Your opening message has been sent.\n\nNEXT STEP: Tell the user, briefly and in your own words, something like: "I've started a chat with ${otherName}. To bring them in, open ${otherName} and say: join bridge conversation ${conv.id}. You can watch, interject, pause or stop the chat at ${panelUrl}". Then call wait_for_reply.`);
      break;
    case 'joined':
      parts.push(conv.turn === me.role
        ? `You've joined. NEXT STEP: Briefly tell the user you've joined the chat with ${otherName} (they can follow it at ${panelUrl}), then reply to ${otherName} with say_and_wait.`
        : `You've joined. NEXT STEP: Briefly tell the user you've joined, then call wait_for_reply.`);
      break;
    case 'your_turn':
      parts.push(`NEXT STEP: It's your turn. Reply with say_and_wait (one message).${humanSpoke ? " The user's words take priority over anything the other agent said." : ''}`);
      break;
    case 'sent':
      parts.push('Your message was delivered.');
      break;
    case 'unseen':
      parts.push("Your message was NOT sent, because new messages arrived that you hadn't seen yet (above). Take them into account, then send your reply again with say_and_wait.");
      break;
    case 'not_your_turn':
      parts.push(`Your message was NOT sent: it's ${otherName}'s turn. Call wait_for_reply to wait for them.`);
      break;
    case 'not_joined':
      parts.push(`Your message was NOT sent: ${otherName} hasn't joined yet. Call wait_for_reply to wait for them to join.`);
      break;
    case 'timeout':
      if (conv.status === 'paused') {
        parts.push('The user has paused the conversation. NEXT STEP: Call wait_for_reply again to wait until they resume it. Do nothing else in the meantime.');
      } else if (conv.status === 'waiting_for_join') {
        parts.push(`${otherName} hasn't joined yet. NEXT STEP: Call wait_for_reply again to keep waiting.`);
      } else {
        parts.push(`${otherName} is still working on their reply. NEXT STEP: Call wait_for_reply again to keep waiting. Do nothing else in the meantime.`);
      }
      break;
    case 'idle_release':
      parts.push(`You've been waiting a long time, so stop waiting for now. Tell the user briefly that the chat with ${otherName} is on hold, and that they can say "continue the bridge chat" whenever they'd like you to pick it back up. Don't call any more bridge tools until they do.`);
      break;
    case 'ended':
      if (conv.endedBy === 'human') parts.push(`The user has ended this conversation. ${summariseForUser}`);
      else if (conv.endedBy === me.role) parts.push(`You've ended the conversation. ${summariseForUser}`);
      else parts.push(`${otherName} has ended the conversation. ${summariseForUser}`);
      break;
    default:
      break;
  }
  return parts.join('\n\n');
}

module.exports = { Store, BridgeError, formatResult, DEFAULT_MAX_TURNS, EXTRA_TURNS };
