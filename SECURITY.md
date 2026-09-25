# Security

## Reporting a vulnerability

Open a private GitHub security advisory:

https://github.com/Jayaram-Nambiar/Global_Context_Orchestration/security/advisories/new

Do not file a public issue for a vulnerability, a credential, or a private path that was committed by mistake.

This project is a local stdio process. It does not phone home. The realistic risks are a malicious repository being indexed (the parsers only read source as text) and editor config files being overwritten incorrectly. `ctx mcp --install` merges configs and skips files that are not valid JSON.

## Secrets in this repository

Do not commit `.env` files, keys, tokens, logs, or `.agent-context.json`. The index contains the absolute path of the machine that ran `ctx map`.
