import requests
def is_downloadable_file(url, sb=None, debug=False):
    try:
        session = requests.Session()
        headers = {
            "Accept": "application/pdf,text/html,*/*",
        }
        if sb is not None:
            ua = sb.execute_script("return navigator.userAgent;")
            headers["User-Agent"] = ua
            for c in sb.driver.get_cookies():
                session.cookies.set(c["name"], c["value"], domain=c.get("domain"))
        else:
            headers["User-Agent"] = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )

        resp = session.get(url, headers=headers, stream=True, timeout=10, allow_redirects=True)
        content_type = resp.headers.get('Content-Type', '').lower()
        content_disposition = resp.headers.get('Content-Disposition', '').lower()

        if debug:
            print(f"URL: {url} -> {resp.url} [{resp.status_code}] ct={content_type!r} cd={content_disposition!r}")

        resp.close()

        if content_disposition.split(';')[0].strip() == 'attachment':
            return True

        if any(content_type.startswith(t) for t in ('text/plain', 'text/html', 'image/', 'text/xml')):
            return False

        return True
    except requests.RequestException as e:
        if debug:
            print(f"  -> request failed: {e}")
        return False