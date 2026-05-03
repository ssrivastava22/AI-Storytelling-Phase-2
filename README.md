# Harper Museum Mystery Game

Small interactive text mystery game where the player investigates Evelyn Harper's murder.

## Run

From this folder:

```bash
python3 mystery_game.py
```

## Optional: Enable LLM Parser

If you want stronger natural-language input parsing:

```bash
export OPENAI_API_KEY="your_key_here"
export OPENAI_MODEL="gpt-4o-mini"  # optional
python3 mystery_game.py
```

If no API key is set, the game runs with the built-in rule parser.

## Basic Commands

- `go hall`, `go office`, `go coast`
- `take ledger`, `take key`
- `examine ledger`, `examine drawer`
- `talk linda`, `talk gregory`, `talk thomas`
- `debug` (show internal story/engine trace)
- `quit`

## Quick Demo

Try this flow:

`go shed -> take vial -> take business card -> go hall -> talk linda -> go office -> take ledger -> examine ledger`
