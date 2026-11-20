# Arena AI → GitHub → Notion → Jo Audit

The pipeline is isolated from MARU runtime. It does not merge, deploy, use the skill/memory sync module, or write production state. Notion receives a page in the **existing private Agent Documents** data source. Jo reviews the commit and the page; this pipeline does not trigger or grant authority to Jo automatically.

## Trust boundaries

1. **Ingest** signals a non-`main` push touching a Markdown report. Its shipped job uses no checkout, scripts, artifacts, job environment or secret; its `GITHUB_TOKEN` permissions are empty.
2. **Publisher** is triggered by `workflow_run` from the default branch. It accepts only a successful push run at the expected ingest workflow path from the same repository, on a non-default branch. It checks out the default-branch event SHA and never checks out the source branch. There is no artifact to extract, script to source, or workflow-provided payload to trust.
3. The stage step uses read-only GitHub API access. It independently verifies changed paths, walks the Git tree at the **full source commit SHA**, checks file mode and blob content hash, then validates report bytes. Only file content from `docs/reports/` is eligible. Reports are never executed. The stage uses no Notion credential.
4. The publisher uses a dedicated environment secret and validates the existing Notion schema. It queries the exact `Source URL` (GitHub `/blob/<40-character SHA>/<report path>`) before creating. It then reads back the page and its blocks. Same SHA/path runs share a concurrency group; separate commits deliberately have separate permalinks. A failed lookup never falls through to create. For a timeout or uncertain create, inspect the destination first; there is no automatic retry of POST create. An exact match that was later manually edited can fail strict read-back, but is never recreated or overwritten.
5. API errors log HTTP status and allowlisted error codes only, not remote error messages, requests, credentials, or report text. Pattern checks help block accidental transfer to Notion; they do not catch every secret, and a public Git push itself exposes its contents. Always validate and review locally **before** push.

## Activation — owner action required

- Have the feature branch reviewed and land the workflows and script on the protected default branch only via an authorized, manual integration. These workflows cannot publish from an unmerged feature branch alone. If the default branch is renamed, update the ingest `branches-ignore` filter and the environment rule.
- In GitHub → **Settings → Environments**, create `arena-report-publisher`. Under deployment branch/tag rules use **Selected branches and tags**, allow the **exact default branch only**, and add **no tags**. Enable required reviewers where available during activation. Confirm feature branches cannot access this environment even if they declare its name. **Do not configure `NOTION_TOKEN` as a repository or organization secret**; the environment is the isolation boundary. If your repo plan cannot enforce the selected-branch rule, do not configure the secret or enable publication.
- In that environment, set `NOTION_TOKEN` as an **environment secret**, and `NOTION_DATA_SOURCE_ID` as an **environment variable** set to the verified data-source ID (not a page link or database-container ID). The supplied ZIP's ID is not assumed to be verified. In Notion, share only the existing Agent Documents database with the integration and grant read/insert capabilities. Do not add a database, change its schema, grant broad workspace access, or paste credentials into source or chat.
- Existing properties must match: **Name** (title), **Source URL** (URL), **Type** (select, existing `Document` option), **Status** (status or select, existing `Draft` option, and `Active` only if you intend to use it), **Date** (date). The publisher uses the Notion HTTP API version `2025-09-03`; this header is separate from the Notion MCP operating-guide protocol. This package does not use the MCP connector or bypass its access rules.

## Write a report

Use a unique filename such as `docs/reports/2026-11-20-example-scope.md`; a date plus scope and unique suffix avoids collisions. Reports are UTF-8, up to 64 KiB and 100 Notion blocks, with up to three safe subdirectories. Filenames use ASCII letters/digits/hyphens/underscores, and the extension is lowercase `.md`. The root `README.md` is not ingested. Frontmatter is a simple scalar format, not general YAML:

```markdown
---
title: "MARU — Implementation and Test Report"
date: "2026-11-20"
status: "Draft"
---

# Summary

Describe exact scope, changes, tests, evidence and what's unverified.
```

Before push: `python scripts/publish_report_to_notion.py validate docs/reports/<filename>.md`. The validator accepts common Markdown block constructs (headings, lists, quotes, fenced code and paragraphs); inline markup and complex structures remain plain text. Commit the report at the **tip** of its push, ideally in a separate small report commit after the code commit (the report can cite that earlier code SHA). Only the pushed head commit is inspected, at most 8 reports and fewer than 100 changed paths; earlier commits in a multi-commit push are not scanned. The `Source URL` is derived from the report commit and path, never taken from user frontmatter. Keep credentials, personal data and `.env` dumps out of reports.

## Verify end-to-end

1. Once activated on the default branch, push a fresh, harmless smoke report as the tip of a non-default branch. Confirm both workflow runs. A green ingest alone is not publication.
2. Check the publisher result (`published` or `already_published` with verified read-back), open the returned Notion page in Agent Documents, and confirm all five properties and the report body. Rerun the same publisher run, confirm `already_published`, and verify that the page ID is unchanged. Do not create another report commit for the idempotency test.
3. Record the actual Actions and Notion links in a handoff to Jo. Do not report PASS without a live created/read-back page. Pending jobs in the same GitHub concurrency group can be superseded; different report SHAs use different groups. Do not treat GitHub concurrency as a global Notion uniqueness constraint or use additional publishers writing the same Source URL.

## Offline checks

```sh
python -m unittest discover -s tests_report_pipeline -v
python -m unittest discover -s tests_github_sync -v
```

Fixture tests cover parse/conversion, Git blob integrity, report boundaries, common credential signatures, status/schema, redacted API errors, and replay with page/content read-back. These are not proof of an authenticated live Actions/Notion run.
