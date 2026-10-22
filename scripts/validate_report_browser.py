"""Optional developer check using installed Playwright and Chromium, not runtime dependencies.

Run from the repository root with a Python that has Playwright installed:
python scripts/validate_report_browser.py --report results/demo/report.html
A temporary loopback server is used only for this automated check because the
cloud browser policy may block file:// navigation. The generated report itself
is self-contained and can be opened directly in an ordinary local browser.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import threading
from urllib.parse import quote


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


@contextmanager
def _serve_local(directory):
    handler = partial(_QuietHandler, directory=str(directory))
    with ThreadingHTTPServer(("127.0.0.1", 0), handler) as server:
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            yield f"http://127.0.0.1:{server.server_port}"
        finally:
            server.shutdown()
            worker.join(timeout=5)


def main():
    from playwright.sync_api import sync_playwright
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, default=Path('demo-output/report.html'))
    parser.add_argument('--browser', default='/usr/bin/chromium')
    parser.add_argument('--evidence', type=Path, default=Path('results/browser_validation.json'))
    parser.add_argument('--screenshot', type=Path, default=Path('docs/assets/report.png'))
    args = parser.parse_args()
    report = args.report.resolve()
    expected = json.loads(report.with_name('report.json').read_text(encoding='utf-8'))
    args.screenshot.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    with _serve_local(report.parent) as origin, sync_playwright() as p:
        browser = p.chromium.launch(executable_path=args.browser, headless=True)
        page = browser.new_page(viewport={'width': 1440, 'height': 1100}, device_scale_factor=1)
        errors, requests = [], []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('request', lambda request: requests.append(request.url))
        page.goto(origin + "/" + quote(report.name))
        page.wait_for_selector('#chart')
        assert page.locator('#gap-list button').count() == len(expected['gaps'])
        checks = ['Local report loads through temporary loopback HTTP and gap count matches audit JSON']
        if expected['gaps']:
            last = expected['gaps'][-1]
            page.locator('#gap-list button').last.click()
            assert page.locator('#chart-title').inner_text() == f"Gap {last['id']} · {last['length']} missing samples"
            if last['neighbors']:
                assert page.locator('#neighbors').inner_text().count('reference row') == len(last['neighbors'])
            checks.append('Gap selection and historical neighbor provenance render')
        # Controlled rendering regression: a polygon with one x coordinate has
        # zero area. Exercise the real chart function with one uncertain sample
        # and assert that its interval and both caps have visible geometry.
        singleton = page.evaluate("""() => {
            const p = D.overview.find(p => p.lo !== null && p.hi > p.lo);
            if (!p) return null;
            chart([{i:p.i-1,t:p.t,o:p.y,y:p.y,lo:null,hi:null},p,
                   {i:p.i+1,t:p.t,o:p.y,y:p.y,lo:null,hi:null}],
                  {start_index:p.i,end_index_exclusive:p.i+1});
            const interval = document.querySelector('[data-role=singleton-interval]');
            const caps = [...document.querySelectorAll('[data-role=singleton-cap]')];
            return {vertical:interval && interval.getAttribute('x1')===interval.getAttribute('x2')
                && Number(interval.getAttribute('y1')) < Number(interval.getAttribute('y2')),
                caps:caps.length===2 && caps.every(c=>Number(c.getAttribute('x2'))>Number(c.getAttribute('x1')))};
        }""")
        if any(any(hi > lo for lo, hi in zip(g['lower'], g['upper'])) for g in expected['gaps']):
            assert singleton and singleton['vertical'] and singleton['caps'], singleton
            checks.append('Single-sample uncertainty renders a visible interval with two caps')
        page.locator('#overview').click()
        assert page.locator('#chart-title').inner_text() == 'Full input series'
        checks.append('Overview control changes the chart')
        for status in ('unresolved', 'reconstructed'):
            page.select_option('#filter', status)
            assert page.locator('#gap-list button').count() == sum(g['status'] == status for g in expected['gaps'])
        checks.append('Both gap-status filters match measured results')
        page.select_option('#filter', 'all')
        if expected['gaps']:
            page.locator('#gap-list button').first.click()
        with tempfile.TemporaryDirectory(prefix='gaplens-browser-') as tmp:
            with page.expect_download() as event:
                page.locator('a[href="repaired.csv"]').click()
            download = event.value
            downloaded = Path(tmp) / 'download.csv'
            download.save_as(downloaded)
            assert downloaded.read_bytes() == report.with_name('repaired.csv').read_bytes()
        checks.append('CSV download preserves the actual exported bytes')
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
        page.screenshot(path=str(args.screenshot), full_page=True)
        page.set_viewport_size({'width': 390, 'height': 844})
        assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
        page.screenshot(path=str(args.screenshot.with_name('report-mobile.png')), full_page=True)
        checks.append('Desktop 1440px and mobile 390px layouts have no horizontal overflow')
        assert errors == [], errors
        remote_requests = [url for url in requests if not url.startswith(origin + '/') ]
        assert remote_requests == [], remote_requests
        checks.extend(['No JavaScript exceptions', 'No remote resource requests'])
        evidence = {'status': 'passed', 'checked_at': datetime.now(timezone.utc).isoformat(),
                    'browser': 'Chromium', 'browser_version': browser.version,
                    'transport': 'Temporary loopback HTTP; no browser policy was altered',
                    'remote_resource_requests': remote_requests,
                    'report': str(args.report), 'report_sha256': hashlib.sha256(report.read_bytes()).hexdigest(),
                    'checks': checks, 'javascript_errors': errors, 'requested_urls': requests,
                    'screenshots': [str(args.screenshot), str(args.screenshot.with_name('report-mobile.png'))]}
        args.evidence.write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
        browser.close()
    print(json.dumps(evidence, indent=2))


if __name__ == '__main__':
    main()
