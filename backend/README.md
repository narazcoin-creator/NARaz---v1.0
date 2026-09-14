# NARaz Network — v1.0 foundation

This is the first working network foundation built from the supplied NAR blockchain prototype and the 0.1 mobile application.

## v1.0 scope
- Server-side unique registration by username and email.
- Password hashing with PBKDF2-HMAC-SHA256.
- Per-user NARaz wallet address.
- Internet-facing HTTP API (binds to 0.0.0.0).
- Persistent SQLite database.
- NARaz blockchain ledger persisted in SQLite.
- 1,000,000,000 NARaz maximum supply.
- Testnet registration grant of 1,000 NARaz from TESTNET_FAUCET.
- Real server-side transfer: sender decreases, recipient increases, transaction is written into a block.
- Balance and transaction history endpoints.

## Important
This is a testnet foundation, not production financial software. Before real-money use, add audited cryptography/signatures, HTTPS/TLS, rate limits, secure key custody, multi-node consensus/P2P, backups, monitoring, migrations, tests and security audit.

## Run
`python server.py`

For internet deployment put the API behind HTTPS and set the Android `NARAZ_API_URL` to the public API origin.
