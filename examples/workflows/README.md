# Release and rollback YAML examples

- [release.yml](release.yml): select an exact source and API/web hashes, retrieve retained packages, preflight, publish without rebuilding, verify and record.
- [rollback.yml](rollback.yml): prepare a read-only candidate, make a separate exact-hash decision, revalidate under the publication lock, then use the same publication and verification adapter.

**These are integration templates, not commissioned cloud pipelines.** They are stored here rather than in `.github/workflows`, contain no live resource names and require an intentionally absent `scripts/cloud_release_adapter.py`. The `RELEASE_ADAPTER_COMMISSIONED` variable is an activation safeguard, not evidence of approval or of tested implementation. Copying these files alone cannot deploy a release.

## Build the adapter in your own project

Create `scripts/cloud_release_adapter.py` only after implementing and testing the following commands against your own isolated resources. Read inputs from the environment as the templates show; never insert untrusted expressions directly into shell commands or evaluate a request as code.

| Command | Required behavior |
| --- | --- |
| `retrieve-and-verify` | Download the selected archive records with Entra authentication. Verify API/web SHA-256, exact source, migration-set digest, successful trusted nonproduction workflow/run/attempt and matching publication acceptance; reject arbitrary ZIPs even if an operator supplies their hashes. |
| `preflight` | Compare current deployment bindings, resource IDs, subscription, schema ledger, runtime permissions, settings and power states with the approved target. Write a private rollback/cleanup journal before a temporary change. Do not apply migrations, open a firewall or activate workers. |
| `prepare-rollback` | Strictly parse `REQUEST_JSON`; identify exact current and target artifacts. Read the SQL/runtime compatibility contract, record the before-state and expiry, and write canonical `candidate.json` plus `candidate.sha256`; never publish here. |
| `resolve-and-revalidate` | Fetch only the expected candidate artifact from the successful main-branch preparation workflow in this repository, with exact run ID, workflow path and attempt. Verify bytes against `CANDIDATE_SHA256`, expiry, operator identity, request binding and unchanged current state under the lock; repeat compatibility and archive checks. |
| `publish` | Use only the verified package paths from this run, never a tag or new build. Publish the API with remote build disabled; unpack the retained web bundle safely, validate any deliberate runtime-config overlay and publish with frontend build skipped. Use this same command for release and rollback. |
| `verify` | Check selected package bindings, health response, anonymous denial on a protected endpoint, asset hashes, schema permissions and preserved settings/identity/schedules. Emit safe evidence on failure; never label a partial publication successful. |
| `record` | Write the active-release receipt only after verification succeeds, retaining source, package hashes, workflow/run identity and any runtime-config overlay hash. |
| `cleanup` | From this run's journal, restore only approved temporary service/settings/network changes. No journal means no changes to restore; do not invent defaults. Capture unresolved cleanup failures and preserve evidence rather than retrying business operations. Never start provider jobs or send messages. |

The cloud adapter is deliberately not replaced by a script that prints success: a sample cannot infer your SQL contract, deployment identities, private paths or approval authority. The complete local model in `lab/promotion.py` demonstrates the integrity and concurrency mechanics before you implement those service-specific boundaries.

## Map publication to Azure

For a Function App package, the platform pattern uses `Azure/functions-action@v1` with `package: release-api/release.zip` and `remote-build: false`. For a Static Web App, it uses `Azure/static-web-apps-deploy@v1` with `action: upload`, an extracted asset directory and `skip_app_build: true`; its deployment token must be masked and kept out of receipts.

Archive reads use `az storage blob download --auth-mode login`, followed by an independent SHA-256 check of the downloaded bytes. Blob metadata alone is not a package hash check. Do not expand archive access to public merely because a hosted runner lacks a private network path.

## Set up your own GitHub and Azure boundary

1. Create a nonproduction environment first and an Entra application/workload federation entry for your exact repository and environment. Give it archive-read and narrowly scoped publication access; keep runtime and deployment identities separate.
2. Configure `AZURE_CLIENT_ID`, `AZURE_TENANT_ID` and `AZURE_SUBSCRIPTION_ID` as environment variables, plus a reviewed `ROLLBACK_PRIVATE_RUNNER` label. Add `ROLLBACK_OPERATOR_ID` as the numeric GitHub account ID that may execute a candidate; names alone are not the account binding.
3. Configure environment branch restrictions and required reviewers where your repository plan supports them. If native reviewers are unavailable, implement and test exact-account, candidate-bound authorization in the adapter as the operational platform does; a workflow name, checkbox or commissioning flag is not an equivalent control.
4. Retain API/web packages and matching receipts before you need rollback. GitHub artifact expiry and Azure archive retention are different; preparation artifacts here last seven days while the actual retained package archive follows its own policy.
5. Implement the adapter, pin reviewed third-party action revisions and run fictional acceptance tests including wrong hashes, expired candidates, stale bindings, denied users and cleanup failure. The sample action tags other than checkout are readable version references, not immutable pins; review and resolve them before commissioning.
6. Move the adapted YAML into your own `.github/workflows` only after those checks pass. Enable `RELEASE_ADAPTER_COMMISSIONED` only after implementation review; this repository does not set it or dispatch either example.

## How to use the two decisions

For release, enter the exact archived source, API ZIP, web ZIP and migration-set hashes you have reviewed; the publisher must verify them against trusted evidence before any write. For rollback, first run `prepare`, inspect the candidate and its compatibility findings, then start a separate `execute` run with that preparation run ID and candidate hash, leaving the preparation request blank.

Do not rerun a timed-out publication blindly. Inspect actual package bindings, settings and receipts first; a transport failure can occur after the service accepted a deployment. Each new execution must repeat readiness and compatibility checks.

## Primary references

- [GitHub OIDC with Azure](https://docs.github.com/en/enterprise-cloud@latest/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-azure)
- [GitHub workflow concurrency](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency)
- [Azure Functions deployment action](https://github.com/Azure/functions-action)
- [Azure Static Web Apps deployment action](https://github.com/Azure/static-web-apps-deploy)
