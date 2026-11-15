# Operations, recovery and limits

## Normal release

Review exact source and package hashes, confirm trusted nonproduction acceptance and retain the archives. Run target/schema/access preflight, make the release decision, publish those packages without rebuilding, verify health/access/assets/settings and record the active release.

## Rollback

Choose a retained known-good release; being old does not make it compatible. Prepare a fresh candidate from exact current/target identities, query live schema/runtime compatibility, approve that candidate's bytes and recheck under the publication lock before using the same publisher.

## Troubleshoot in this order

| Observation | Next action |
| --- | --- |
| Archive missing or artifact expired | Locate the retained approved archive and matching receipt; do not rebuild and call it the same package. |
| Hash/source mismatch | Stop selection and identify the wrong artifact or corrupt download. Never edit the expected hash to make it pass. |
| Azure sign-in fails | Check the exact repository/environment OIDC subject, tenant, identity and scope. Do not substitute a broad long-lived credential. |
| Private host unreachable | Separate DNS, routes, endpoint state and caller permissions. A paused resource or removed private path can explain the failure without invalidating the ZIP. |
| Candidate expired or current state changed | Prepare a new candidate and review it again. The old decision cannot silently authorize new state. |
| Schema incompatibility | Stop; a package rollback cannot undo database changes. Review a separate recovery/migration plan. |
| Upload timed out | Read current service bindings and receipts before retrying; the outcome may be unknown. |
| Health passes but protected route is open | Treat verification as failed; health is not an access-control check. |
| One package changed and the other did not | Record partial publication, inspect both bindings and take a deliberate recovery decision. |
| Local `.publication.lock` remains | Confirm no process is publishing, inspect runtime.json and reconcile the previous outcome before removing only that local lock. |
| Local `runtime.json.new` remains | Inspect the prior interrupted write and current runtime state. Do not treat deleting the temporary file as proof the prior publication failed. |

## Strengths, tradeoffs and scaling

Build-once promotion makes the release identity inspectable; it does not prove every application behavior. Preserved archives support deliberate recovery, but they consume storage and can retain known vulnerabilities, so retention, access and periodic eligibility review matter.

One publication lock prevents overlapping writes, at the cost of serializing releases. GitHub concurrency is not a guaranteed unlimited FIFO queue: pending runs can be displaced, so inspect run outcomes rather than assume every request eventually ran.

For more applications, use independent per-target locks and a central release inventory, while retaining one shared lock for components that form a coupled release. Expand acceptance and contract testing before adding parallelism; paired cloud publication remains non-atomic.

Version your manifests and compatibility contracts, keep package retention separate from short-lived preparation receipts, and use a scoped, ephemeral private runner when needed. Record package sizes, archive storage costs, runner minutes, verification latency and rollback readiness; avoid storing credentials or source records in evidence.

## Validation boundary

The standard-library model reads/writes fictional local files only. It demonstrates content fingerprints, exact-candidate matching, expiry, stale-state rejection, shared locking and preservation of local settings; it does not authenticate operators, cryptographically sign acceptance evidence, query Azure or SQL, run a real app, prove browser behavior or deploy a package.

The workflow templates document the cloud integration contract and deliberately have no commissioned adapter. Hosted release acceptance, real SQL compatibility, Azure role scope, environment approval and private networking must be tested separately in your own environment.
