import csv
import time
import requests
import dns.resolver
from urllib.parse import urlparse, urlunparse
 
PUBLIC_RESOLVERS = ["8.8.8.8", "1.1.1.1", "9.9.9.9"]  # Google, Cloudflare, Quad9
TIMEOUT = 8
RESULTS = {"recovered": [], "needs_wayback": [], "dead": []}
 
 
def resolves(hostname: str) -> bool:
    """Try resolving hostname against several public DNS servers."""
    for resolver_ip in PUBLIC_RESOLVERS:
        try:
            r = dns.resolver.Resolver()
            r.nameservers = [resolver_ip]
            r.timeout = TIMEOUT
            r.lifetime = TIMEOUT
            r.resolve(hostname, "A")
            return True
        except Exception:
            continue
    return False
 
 
def url_variants(url: str):
    """Generate plausible URL variants to retry."""
    parsed = urlparse(url if "://" in url else f"http://{url}")
    host = parsed.netloc or parsed.path  # handles bare domains passed without scheme
    host = host.replace("www.", "")
    variants = set()
    for scheme in ("https", "http"):
        for prefix in ("", "www."):
            variants.add(f"{scheme}://{prefix}{host}")
    # common TLD swap seen in Indian startup listings
    if host.endswith(".com"):
        variants.add(f"https://{host[:-4]}.in")
    if host.endswith(".in"):
        variants.add(f"https://{host[:-3]}.com")
    return list(variants)
 
 
def check_live(url: str) -> bool:
    try:
        resp = requests.get(url, timeout=TIMEOUT, allow_redirects=True,
                             headers={"User-Agent": "Mozilla/5.0"})
        return resp.status_code < 400
    except Exception:
        return False
 
 
def wayback_last_snapshot(url: str):
    """Return the most recent archived snapshot URL, or None."""
    api = f"http://archive.org/wayback/available?url={url}"
    try:
        r = requests.get(api, timeout=TIMEOUT)
        data = r.json()
        snap = data.get("archived_snapshots", {}).get("closest")
        if snap and snap.get("available"):
            return snap["url"]
    except Exception:
        pass
    return None
 
 
def process_one(company: str, url: str):
    host = urlparse(url if "://" in url else f"http://{url}").netloc or url
 
    # Step 1: re-check DNS with public resolvers
    if resolves(host) and check_live(url if "://" in url else f"https://{url}"):
        RESULTS["recovered"].append((company, url, url, "public-dns"))
        return
 
    # Step 2: try variants
    for variant in url_variants(url):
        v_host = urlparse(variant).netloc
        if resolves(v_host) and check_live(variant):
            RESULTS["recovered"].append((company, url, variant, "url-variant"))
            return
 
    # Step 3: Wayback Machine fallback
    snap = wayback_last_snapshot(url)
    if snap:
        RESULTS["needs_wayback"].append((company, url, snap, "wayback"))
        return
 
    # Step 4: genuinely dead — flag for manual search (company name -> LinkedIn/Google)
    RESULTS["dead"].append((company, url, "", "manual-search-needed"))
 
 
def run(input_path: str):
    with open(input_path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = [row for row in reader if row]
 
    for row in rows:
        company, url = (row[0], row[1]) if len(row) > 1 else ("", row[0])
        print(f"Checking: {company or url}")
        process_one(company, url)
        time.sleep(0.5)  # be polite, avoid rate limits
 
    for bucket, rows_out in RESULTS.items():
        fname = f"{bucket}.csv"
        with open(fname, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["company", "original_url", "recovered_url", "method"])
            w.writerows(rows_out)
        print(f"{bucket}: {len(rows_out)} -> {fname}")
 
 
if __name__ == "__main__":
    import sys
    run(sys.argv[1] if len(sys.argv) > 1 else "dns_error_urls.csv")