# SelfBot Pro

SelfBot Pro is a modular Telegram user-account automation project based on Telethon.

## Core

- Python 3.11+
- Telethon MTProto
- SQLite with aiosqlite
- APScheduler
- Dot-prefixed commands
- Modular feature registry
- Persian-first interface
- Structured local logging
- Optional HTTP control plane

## Render storage

The free Render worker has an ephemeral filesystem. SQLite data, Telegram sessions, generated media and local logs are not durable across restarts. Durable local storage requires a paid Render service with a persistent disk, or an external data/session storage design.

## Security

Do not commit .env files, Telegram session files, API keys, or account exports. A Telegram session file is an account credential.

## Scope

The project provides account automation, scheduling, moderation, backups, media utilities, translation, AI-assisted chat and diagnostics. It does not provide access-control bypassing, hidden-content extraction, enforcement evasion, privacy-invasive surveillance, or manipulation of random game outcomes.
