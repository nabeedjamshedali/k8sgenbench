# How to relay prompts (DeepSeek + GPT web)

38 replies needed per model (76 total).

## Each prompt

1. Open a NEW chat (never reuse a chat).
   - DeepSeek (chat.deepseek.com): DeepThink OFF, Search OFF.
   - ChatGPT: default model, no browsing / tools / file search.
2. Paste the WHOLE content of a file from `prompts/` and send. Nothing else.
   No follow-up messages, no "continue", no corrections.
3. Copy the model's whole reply (use the chat's copy button) into a new
   text file in `inbox/deepseek/` or `inbox/gpt/`, named:

       <prompt file name without .txt>__s<1|2|3>.txt
       e.g.  P02_n8n__neutral__s1.txt

   Samples s1, s2, s3 = the same prompt pasted in 3 separate new chats.

## Rules

- If the reply is cut off, save it as it is. Do not ask it to continue
  (a truncated answer is a valid result).
- If the site refuses or errors before replying, try again in a new chat
  and note it in `inbox/<model>/NOTES.txt`.
- P03_grafana prompts are large (~140k chars). If the site turns the paste
  into an attachment, that is fine; note it in NOTES.txt.
- P05 and P07 s1 already exist from the pilot: only s2 and s3 are needed
  for those.

## Which files are still missing

    python generation/relay.py status

Send me the files (or just drop them in the inbox folders) and I will
import and evaluate them.
