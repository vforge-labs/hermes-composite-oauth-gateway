# Migration and rollback

## Before migration

1. Create a complete, restricted rollback snapshot of the working proxy.
2. Verify archive checksums and extract it into a restricted temporary directory.
3. Verify the stored source revision or Git bundle.
4. Confirm the old proxy is healthy.
5. Run the new gateway on a different loopback port and complete `docs/ACCEPTANCE.md`.

## Migration

A safe cutover changes only the executable behind the existing loopback endpoint. Existing Grok consumers can retain `http://127.0.0.1:8645/v1`.

1. Install the package into the Hermes runtime environment.
2. Stage a new systemd unit or exact `ExecStart` replacement.
3. Save `systemctl --user cat` output and enablement state.
4. Stop the old service.
5. Start the composite gateway on `127.0.0.1:8645`.
6. Immediately check `/health`, `/v1/models`, one Grok stream, and one Codex stream.
7. Confirm with `ss` that no non-loopback listener exists.
8. Add logical Hermes provider entries only after the listener passes.

Do not copy canonical refresh tokens into profile-local auth files.

## Rollback trigger

Roll back immediately if:

- the listener is not loopback-only;
- either canonical credential pool fails to load;
- existing Grok inference regresses;
- Codex account headers do not match the selected token;
- refresh persistence fails;
- the process cannot recover after restart.

## Generic rollback

1. Stop the replacement service.
2. Restore the prior proxy source and exact systemd unit from the restricted snapshot.
3. Restore canonical OAuth state only if it was modified or damaged.
4. Run `systemctl --user daemon-reload`.
5. Restore the prior enablement state.
6. Start the old service.
7. Verify `/health`, `/v1/models`, a Grok inference, and loopback-only binding.

The private snapshot's restoration instructions are authoritative for the machine it captured. Never publish that snapshot or its credential-bearing contents.
