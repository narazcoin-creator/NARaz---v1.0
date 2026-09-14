# NARaz v1.0

First working foundation based on the supplied NARaz 0.1 mobile app and the supplied NAR blockchain prototype.

## Architecture
Android/WebView UI → NARaz Network HTTP API → persistent SQLite account/ledger store → NARaz blockchain blocks.

## First working features
- Registration and login.
- Unique username and unique email enforced server-side.
- Per-user wallet address.
- NARaz Testnet registration grant: 1,000 NARaz.
- Internet-facing API (0.0.0.0:8080).
- Persistent blockchain ledger.
- Real server-side transfer between registered users.
- Sender and recipient balances update from blockchain state.
- Transaction history.
- Network status.
- 1,000,000,000 NARaz maximum supply.

## Network URL
Before building/releasing the APK, set the API URL in the app's `localStorage` or replace the `YOUR_SERVER` placeholder in `index.html` with the public HTTPS NARaz Network endpoint.

For production use, HTTPS/TLS is mandatory. This v1 is a testnet foundation.
