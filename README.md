# Telegram bot integration for OpenAI ChatGPT

---
This repository contains a Telegram bot written in Python and 
integrated with the ChatGPT API. It allows users to interact with a virtual 
assistant by generating natural language responses. The bot is fully 
configurable, allowing users to customize the assistant to their preferences. 

# Installation
1. Rename the .env.example file to .env and add your own data `TG_API_KEY`, `OPENAI_API_KEY` and `ALLOWED_USERS`
2. Install all the necessary components: 
```bash
python3 -m pip install --user virtualenv
python3 -m venv env
source env/bin/activate
python3 -m pip install -r req.txt
```

The bot in operation uses a SQLite database as a cold store of submitted data, to provide context for 
ChatGPT's queries, and to make these queries more relaxed.
