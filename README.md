# Claude ⇄ Codex bridge

Lets your **Claude** session and your **Codex** session talk to each other directly, inside the sessions you already have open, while you watch from a simple page in your browser. You can **interject**, **pause**, **resume** or **stop** the chat at any time.

- Either agent can suggest a chat with the other. It always **asks you first**.
- They take turns, one message each, and you see every message live.
- When the chat ends, each agent gives you a short summary in its own window and carries on working with you as normal.
- Everything stays on your computer.

## How it works

```
  Claude app  ──┐                          ┌──  Codex app
                ├──►  bridge (runs on  ◄───┤
                │     your computer)       │
                          │
                  control panel in your browser
                  http://localhost:7777
```

Each app starts a small connector when it opens. The connectors share one bridge that holds the conversation and passes messages back and forth. The bridge starts by itself the first time it's needed, so there's nothing to launch.

## Install (the easy way)

You need **Node.js** (free) and these files on your computer. The simplest route is to ask Claude to do it. Open the Claude app, in any folder, and paste this, replacing the folder path at the end with your project's folder:

> Please install the Claude ⇄ Codex bridge for me:
> 1. Check that Node.js 18 or newer is installed (`node --version`). If it isn't, install the LTS version from https://nodejs.org (or with Homebrew on a Mac).
> 2. Download the repository https://github.com/james-taplin/llw-conversions into a permanent folder, `~/llw-bridge`.
> 3. Run `node setup.js "<PATH TO MY PROJECT FOLDER>"` from inside `~/llw-bridge` and tell me what it says.

Then **quit and reopen both the Claude and Codex apps**, or start new sessions in your project folder, so they pick up the bridge.

If either app asks whether to allow the **llw-bridge** (or **llw_bridge**) server or its tools, say **yes** / **always allow**.

> Keep the `~/llw-bridge` folder where it is. If you move it, run the setup command again.
> Have more than one project? Run `node setup.js "<folder 1>" "<folder 2>"`, or run it again later for a new folder.

## Using it

**Starting a chat.** In either app, ask something like:

- "Can you check this plan with Codex?"
- "Ask Claude what it thinks of this bug fix."

Agents may also offer on their own when a second opinion would help ("Would you like me to check this with Codex?"). They only start once you say yes. Claude also shows you a permission prompt the first time.

**Bringing in the other agent.** The first agent gives you a short code like `blue-otter`. Open the other app and say:

> join bridge conversation blue-otter

(Just "join the bridge chat" works too.) The control panel opens in your browser by itself. You can also visit **http://localhost:7777** at any time.

**The control panel**

| What you want | What to do |
|---|---|
| Say something to both | Type in the box at the bottom and press **Send to both**. The agents see it before their next message, and it takes priority over what the other agent says. |
| Take a breather | **Pause**. Both agents hold where they are. **Resume** lets them carry on. |
| End it | **Stop**. Both agents wrap up and give you a summary in their own window. |
| Let it run longer | Chats pause automatically after 20 messages. Press **Resume** (or "allow 10 more") to continue. |
| Keep a record | **Download transcript** (after it ends) saves the whole chat as a text file. |
| Stop instantly | Press **Esc** in the Claude or Codex app. The panel's buttons take effect between messages. Esc stops an agent right away. |

**Built-in safety**

- Nothing starts without your OK.
- Chats pause after 20 messages, and also if the agents start repeating themselves.
- If a chat stays paused for 15 minutes, the agents stop waiting. Tell either one "continue the bridge chat" to pick it back up.
- Agents may read your project's files freely. They only change files if you've asked them to or agreed, and they agree between themselves who edits what first.

## Troubleshooting

- **An agent doesn't seem to know about the bridge.** Quit and reopen the app, or start a new session in your project folder. In Claude you can type `/mcp` to see whether `llw-bridge` is connected. In Codex it's `/mcp` too (CLI) or the MCP settings (app).
- **The panel says "Bridge not running".** That's normal until an agent uses it. To start it by hand, run `node ~/llw-bridge/bridge.js open`.
- **An agent stopped mid-chat.** Tell it "continue the bridge chat".
- **Another program already uses port 7777.** Ask Claude to set the environment variable `LLW_BRIDGE_PORT` to another number (e.g. 7788) for both apps.
- **After updating the bridge**, run the setup command again. It restarts the bridge on the new version.

## Removing it

```
node ~/llw-bridge/setup.js --uninstall "<PATH TO MY PROJECT FOLDER>"
```

This removes everything setup added. Before changing any existing file, setup saved a copy next to it ending in `.llw-backup`.

## What setup changes

| File | Why |
|---|---|
| `<project>/.mcp.json` | Tells Claude how to start the bridge connector. |
| `<project>/.claude/settings.local.json` | Lets Claude use the bridge mid-chat without asking every message. Starting a chat still asks. |
| `<project>/CLAUDE.md` and `<project>/AGENTS.md` | A short section teaching Claude and Codex when and how to use the bridge. |
| `~/.codex/config.toml` | Tells Codex how to start the bridge connector. |

Conversations are saved in `~/.llw-bridge/conversations/`. The bridge only accepts connections from your own computer, and it needs a secret key (in `~/.llw-bridge/token`), so websites can't talk to it.

## For the curious

Plain JavaScript on Node.js with no extra packages.

- `bridge.js` is the command-line entry point.
- `src/mcp.js` is the connector each app runs. It speaks the Model Context Protocol (MCP), the standard way apps add tools for AI agents.
- `src/hub.js` is the shared bridge and web server.
- `src/conversations.js` holds the turn-taking rules.
- `src/panel.html` is the control panel.

Run the tests with `npm test`.
