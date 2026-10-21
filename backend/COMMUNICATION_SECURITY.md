# Consultation privacy contract

The server accepts only client-encrypted `ciphertext` and `algorithm` values for
chat messages. A client must generate and retain its own private keys, verify the
other participant's public key, and encrypt before calling the API. The server
does not generate, receive, or persist message private keys.

Video calls use an encrypted WebRTC signalling payload. Clients must enable
WebRTC insertable-stream end-to-end encryption for media; transport encryption
alone is not sufficient.

An optional `safety_envelope` may be encrypted by the client for a separately
managed emergency safety key. It is not a copy of ordinary chat access. An admin
can request envelopes only with a recorded safety reason of at least 20
characters; the request is written to `data/safety_audit.json`. Normal encrypted
messages are never exposed through an admin endpoint.
