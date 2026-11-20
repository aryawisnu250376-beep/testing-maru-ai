"""Offline contract tests; credentials, GitHub calls and Notion pages are fixtures only."""
import base64
import hashlib
import io
import json
import os
import tempfile
import unittest
import urllib.error
from email.message import Message
from pathlib import Path
from unittest.mock import patch

from scripts import publish_report_to_notion as p

REPO = "example/maru"
SHA = "a" * 40
PATH = "docs/reports/nested/example.md"
SOURCE = "11111111-2222-4333-8444-555555555555"
PAGE = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
RAW = b'---\ntitle: "MARU: audit report"\ndate: 2026-11-20\n---\n# Result\n\nAll fixture checks passed.'


class NotionFixture:
    def __init__(self):
        self.saved = {}
        self.creates = 0
        self.fail_lookup = False

    def __call__(self, method, path, data=None):
        if path.endswith("/query"):
            if self.fail_lookup:
                raise p.ReportError("Notion POST HTTP 403.")
            link = data["filter"]["url"]["equals"]
            return {"results": [{"id": PAGE}] if link in self.saved else [], "has_more": False}
        if method == "POST" and path == "/pages":
            self.creates += 1
            self.saved[data["properties"]["Source URL"]["url"]] = data
            return {"id": PAGE}
        if path == f"/pages/{PAGE}":
            doc = next(reversed(self.saved.values()))
            props = json.loads(json.dumps(doc["properties"]))
            for item in props["Name"]["title"]:
                item["plain_text"] = item["text"]["content"]
            return {"id": PAGE, "parent": doc["parent"], "properties": props}
        if path == f"/blocks/{PAGE}/children?page_size=100":
            doc = next(reversed(self.saved.values()))
            blocks = json.loads(json.dumps(doc["children"]))
            for block in blocks:
                for item in block[block["type"]]["rich_text"]:
                    item["plain_text"] = item["text"]["content"]
            return {"results": blocks, "has_more": False}
        raise AssertionError((method, path))


def github_fixture(mode="100644", actual_bytes=RAW):
    roots = [str(i) * 40 for i in range(1, 5)]
    blob = hashlib.sha1(f"blob {len(RAW)}\0".encode() + RAW).hexdigest()
    tree_api = {
        f"/repos/{REPO}/git/trees/{sha}": {"truncated": False, "sha": sha, "tree": [
            {"path": name, "type": "tree", "mode": "040000", "sha": roots[i+1]}
            if i < 3 else {"path": name, "type": "blob", "mode": mode, "sha": blob, "size": len(RAW)}]}
        for i, (name, sha) in enumerate(zip(PATH.split("/"), roots))
    }
    commit_data = {"sha": SHA, "commit": {"tree": {"sha": roots[0]}}, "files": [
        {"filename": PATH, "status": "added"}, {"filename": "src/no.md", "status": "added"},
        {"filename": "docs/reports/old.md", "status": "removed"},
        {"filename": "docs/reports/README.md", "status": "modified"}]}
    results = {**tree_api, f"/repos/{REPO}/commits/{SHA}?per_page=100": commit_data,
               f"/repos/{REPO}/git/blobs/{blob}": {"sha": blob, "encoding": "base64", "size": len(RAW),
                  "content": base64.b64encode(actual_bytes).decode()}}
    return lambda method, path: results[path]


class ReportTests(unittest.TestCase):
    def test_frontmatter_crlf_and_colon(self):
        meta, body = p.parse_frontmatter(RAW.decode().replace("\n", "\r\n"))
        self.assertEqual(meta, {"title": "MARU: audit report", "date": "2026-11-20", "status": "Draft"})
        self.assertTrue(body.startswith("# Result"))

    def test_frontmatter_rejects_bad_headers(self):
        for malformed in ["no header", "---\ntitle: ok\n---extra", RAW.decode().replace("---\n#", "title: twice\n---\n#"),
                          RAW.decode().replace("2026-11-20", "2026-02-30"), RAW.decode().replace("---\n#", "status: unsafe\n---\n#")]:
            with self.subTest(malformed=malformed), self.assertRaises(p.ReportError):
                p.parse_frontmatter(malformed)

    def test_native_markdown_blocks_and_unicode_size(self):
        text = '🧪' * 999
        blocks = p.markdown_to_blocks(f'# Heading\n\n{text}\n\n- Bullet\n2. Item\n> Quote\n```sh\n# in fence\n```')
        self.assertEqual([b['type'] for b in blocks], ['heading_1', 'paragraph', 'bulleted_list_item', 'numbered_list_item', 'quote', 'code'])
        spans = blocks[1]['paragraph']['rich_text']
        self.assertEqual(''.join(t['text']['content'] for t in spans), text)
        self.assertTrue(all(len(t['text']['content'].encode('utf-16-le')) <= 4000 for t in spans))
        self.assertEqual(blocks[-1]['code']['rich_text'][0]['text']['content'], '# in fence')

    def test_markdown_rejects_unclosed_and_over_limit(self):
        for value in ['```\nunterminated', '\n'.join('- item' for _ in range(101)), '\n']:
            with self.assertRaises(p.ReportError):
                p.markdown_to_blocks(value)

    def test_paths_are_constrained(self):
        self.assertEqual(p.validate_report_path(PATH), PATH)
        for value in ['README.md', 'docs/reports/README.md', '/docs/reports/x.md', 'docs/reports/../x.md',
                      'docs/reports/%2e/x.md', 'docs/reports/a\\b.md', 'docs/reports/x.py', 'docs/reports/sub/.git.md']:
            with self.subTest(value=value), self.assertRaises(p.ReportError):
                p.validate_report_path(value)

    def test_changed_paths_are_bound_to_regular_git_blobs(self):
        self.assertEqual(p.github_reports(REPO, SHA, github_fixture()), {PATH: RAW})
        with self.assertRaisesRegex(p.ReportError, 'regular non-executable'):
            p.github_reports(REPO, SHA, github_fixture(mode='120000'))
        with self.assertRaisesRegex(p.ReportError, 'integrity check'):
            p.github_reports(REPO, SHA, github_fixture(actual_bytes=RAW[:-1] + b'X'))

    def test_credentials_rejected_without_outputting_value(self):
        for token in ['ghp_' + 'x' * 25, 'ntn_' + 'A' * 32, 'password = ' + 'R' * 20,
                      '-----BEGIN OPENSSH PRIVATE KEY-----', 'Authorization: Bearer ' + 'J' * 28]:
            with self.assertRaises(p.ReportError) as caught:
                p.prepare(RAW + token.encode())
            self.assertNotIn(token, str(caught.exception))
        p.prepare(RAW + b'\nConfigure NOTION_TOKEN in GitHub Environment.')

    def test_only_full_sha_can_form_permalink(self):
        self.assertEqual(p.source_permalink(REPO, SHA, PATH), f'https://github.com/{REPO}/blob/{SHA}/{PATH}')
        for value in ['main', 'a'*7, 'a'*39, 'x'*40]:
            with self.assertRaises(p.ReportError):
                p.source_permalink(REPO, value, PATH)

    def test_idempotency_and_created_page_readback(self):
        meta, blocks = p.prepare(RAW)
        notion = NotionFixture()
        first = p.publish_report(notion, SOURCE, REPO, SHA, PATH, meta, blocks, 'status')
        second = p.publish_report(notion, SOURCE, REPO, SHA, PATH, meta, blocks, 'status')
        self.assertEqual((first['status'], second['status'], notion.creates), ('published', 'already_published', 1))
        self.assertEqual(first['page_url'], second['page_url'])
        self.assertEqual(notion.saved[first['source_url']]['properties']['Status'], {'status': {'name': 'Draft'}})
        p.publish_report(notion, SOURCE, REPO, 'b'*40, PATH, meta, blocks, 'status')
        self.assertEqual(notion.creates, 2)

    def test_offline_cli_stage_publish_and_wrong_commit_refusal(self):
        notion = NotionFixture()
        calls = []
        def api(service, method, path, token, data=None):
            calls.append(service)
            if service == 'GitHub':
                self.assertEqual(token, 'github-fixture')
                return github_fixture()(method, path)
            self.assertEqual(token, 'notion-fixture')
            if method == 'GET' and path == f'/data_sources/{SOURCE}':
                props = {key: {'type': kind} for key, kind in [('Name', 'title'), ('Source URL', 'url'), ('Type', 'select'), ('Date', 'date'), ('Status', 'select')]}
                props['Type']['select'] = {'options': [{'name': 'Document'}]}
                props['Status']['select'] = {'options': [{'name': 'Draft'}]}
                return {'id': SOURCE, 'properties': props}
            return notion(method, path, data)
        with tempfile.TemporaryDirectory() as tmp, patch.object(p, 'request_json', api), patch('sys.stdout', new_callable=io.StringIO) as output:
            env = {'RUNNER_TEMP': tmp, 'GITHUB_REPOSITORY': REPO, 'REPORT_SHA': SHA}
            with patch.dict(os.environ, {**env, 'REPORT_GITHUB_TOKEN': 'github-fixture'}, clear=True), patch('sys.argv', ['publisher', 'stage']):
                p.main()
            self.assertEqual(set(calls), {'GitHub'})
            self.assertTrue((Path(tmp) / 'maru-arena-reports' / 'reports.json').is_file())
            calls.clear()
            with patch.dict(os.environ, {**env, 'NOTION_TOKEN': 'notion-fixture', 'NOTION_DATA_SOURCE_ID': SOURCE}, clear=True), patch('sys.argv', ['publisher', 'publish']):
                with patch.dict(os.environ, {'REPORT_SHA': 'b' * 40}), self.assertRaisesRegex(p.ReportError, 'not bound'):
                    p.main()
                self.assertEqual(calls, [])
                p.main()
                p.main()
            self.assertEqual(set(calls), {'Notion'})
            self.assertEqual(notion.creates, 1)
            self.assertIn('already_published', output.getvalue())
            self.assertNotIn('notion-fixture', output.getvalue())
            self.assertNotIn('github-fixture', output.getvalue())

    def test_lookup_failure_blocks_any_create(self):
        notion = NotionFixture()
        notion.fail_lookup = True
        with self.assertRaisesRegex(p.ReportError, 'HTTP 403'):
            p.publish_report(notion, SOURCE, REPO, SHA, PATH, *p.prepare(RAW), 'select')
        self.assertEqual(notion.creates, 0)

    def test_api_errors_are_redacted_and_create_is_not_automatically_replayed(self):
        bad = 'fixture-value-not-for-output'
        calls = []
        def fail(req, timeout):
            calls.append((req.method, req.full_url))
            body = json.dumps({'code': 'rate_limited', 'message': bad}).encode()
            raise urllib.error.HTTPError(req.full_url, 429, bad, Message(), io.BytesIO(body))
        with self.assertRaises(p.ReportError) as caught:
            p.request_json('Notion', 'POST', '/pages', bad, {}, opener=fail)
        self.assertIn('HTTP 429 (rate_limited)', str(caught.exception))
        self.assertIn('do not retry blindly', str(caught.exception))
        self.assertNotIn(bad, str(caught.exception))
        self.assertEqual(calls, [('POST', p.API_NOTION + '/pages')])

    def test_api_transport_error_hides_reason(self):
        def fail(req, timeout):
            raise urllib.error.URLError('sensitive-error-cause')
        with self.assertRaises(p.ReportError) as caught:
            p.request_json('Notion', 'GET', '/data_sources/' + SOURCE, 'fixture', opener=fail)
        self.assertIn('transport error', str(caught.exception))
        self.assertNotIn('sensitive-error-cause', str(caught.exception))

    def test_verify_detects_content_mismatch_without_duplicate(self):
        meta, blocks = p.prepare(RAW)
        notion = NotionFixture()
        p.publish_report(notion, SOURCE, REPO, SHA, PATH, meta, blocks, 'select')
        with self.assertRaisesRegex(p.ReportError, 'verification failed'):
            p.publish_report(notion, SOURCE, REPO, SHA, PATH, meta, p.markdown_to_blocks('different'), 'select')
        self.assertEqual(notion.creates, 1)

    def test_schema_is_verified_without_modifying_options(self):
        props = {key: {'type': kind} for key, kind in [('Name', 'title'), ('Source URL', 'url'), ('Type', 'select'), ('Date', 'date'), ('Status', 'status')]}
        props['Type']['select'] = {'options': [{'name': 'Document'}]}
        props['Status']['status'] = {'options': [{'name': 'Draft'}]}
        self.assertEqual(p.schema_status_kind({'properties': props}, {'Draft'}), 'status')
        with self.assertRaises(p.ReportError):
            p.schema_status_kind({'properties': props}, {'Active'})


if __name__ == '__main__':
    unittest.main()
