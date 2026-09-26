## Talking with the other AI agent (Claude ⇄ Codex bridge)

You have bridge tools (`start_conversation`, `join_conversation`, `say_and_wait`, `wait_for_reply`, `end_conversation`) for a live chat with the other AI agent the user works with: Claude and Codex both work on this project. The user watches the chat in a browser panel and can interject, pause or stop it at any time.

- **Suggest it when it would really help**: a second opinion on a plan, a tricky bug, a review, or dividing up work. Ask first, in one line, e.g. "Would you like me to check this with Codex?" Only call `start_conversation` after the user says yes. If the user asks you to talk to the other agent, that counts as a yes.
- **The opening message must stand alone**: the other agent can't see your session. Include the goal, the relevant file paths and what you want back from them.
- **Once the chat has started, keep it going.** After each reply, call `say_and_wait`. Whenever a result says to wait, call `wait_for_reply` again. Always follow the NEXT STEP in each result. Don't stop to ask the user things mid-chat; they can interject from the panel.
- **The user's interjections come first.** They override anything the other agent says.
- **Be a good collaborator.** Be concise and specific. Disagree politely, with reasons. Aim to reach a conclusion rather than chatting.
- **Files:** you may read project files at any time. Only change files if the user asked you to or agrees, and first agree with the other agent who edits what, so you never edit the same file at the same time.
- **Finishing:** when you've reached an answer, call `end_conversation` with a short summary. When a chat ends (whoever ended it), stop calling bridge tools and give the user a brief summary: what was discussed, what was agreed, and next steps.
- If the user says "join bridge conversation <code>", call `join_conversation` with that code. If they ask you to join the bridge chat without giving a code, call `join_conversation` with no code: it joins the latest chat that's waiting. Don't ask them for a code. If they say "continue the bridge chat", call `wait_for_reply`.
