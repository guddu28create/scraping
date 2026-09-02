import asyncio
import re
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError


# ============================================================
# SETTINGS
# ============================================================

INPUT_FILE = "Nagpur_DPIIT_Missing_Startups_Diagnostic.csv"
OUTPUT_FILE = "01_website_discovery_test_10.csv"

TEST_ROWS = 10

# Google search results to collect per startup
RESULTS_PER_STARTUP = 8

# Delay between searches (seconds)
DELAY_BETWEEN_SEARCHES = 2


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def clean_text(text):
    if not text:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip()


def normalize_url(url):
    """Make a URL easier to compare."""
    if not url:
        return ""

    url = url.strip()

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    return url


def get_domain(url):
    """Extract the domain from a URL."""
    try:
        domain = urlparse(url).netloc.lower()
        domain = domain.replace("www.", "")
        return domain
    except Exception:
        return ""


def is_bad_domain(url):
    """
    Domains we don't want to treat as the startup's official website.
    They can still appear as useful search results, but aren't
    candidate official websites.
    """
    domain = get_domain(url)

    bad_domains = {
        "google.com",
        "google.co.in",
        "youtube.com",
        "facebook.com",
        "instagram.com",
        "linkedin.com",
        "x.com",
        "twitter.com",
        "crunchbase.com",
        "tracxn.com",
        "zaubacorp.com",
        "tofler.in",
        "thecompanycheck.com",
        "indiamart.com",
        "justdial.com",
        "sulekha.com",
        "tradeindia.com",
        "exportersindia.com",
        "ambitionbox.com",
        "glassdoor.co.in",
        "glassdoor.com",
        "indeed.com",
        "startupindia.gov.in",
        "dpiit.gov.in",
    }

    return any(
        domain == bad or domain.endswith("." + bad)
        for bad in bad_domains
    )


def score_candidate(startup_name, title, url, snippet):
    """
    Give each candidate a rough score.

    This is intentionally conservative. The score is only for
    prioritization; it does NOT prove that the website is official.
    """

    score = 0
    reasons = []

    name = clean_text(startup_name).lower()
    title_lower = clean_text(title).lower()
    snippet_lower = clean_text(snippet).lower()

    # Remove common legal/company words for comparison
    generic_words = {
        "private",
        "limited",
        "pvt",
        "ltd",
        "llp",
        "opc",
        "company",
        "co",
        "and",
        "&",
        "the",
    }

    name_words = {
        w for w in re.findall(r"[a-z0-9]+", name)
        if w not in generic_words and len(w) > 2
    }

    domain = get_domain(url)
    domain_text = domain.replace("-", " ").replace(".", " ").lower()

    # Name words appearing in domain
    domain_matches = sum(
        1 for word in name_words
        if word in domain_text
    )

    if domain_matches >= 3:
        score += 45
        reasons.append("strong name-domain match")
    elif domain_matches == 2:
        score += 30
        reasons.append("good name-domain match")
    elif domain_matches == 1:
        score += 12
        reasons.append("partial name-domain match")

    # Startup name appearing in title
    title_matches = sum(
        1 for word in name_words
        if word in title_lower
    )

    if title_matches >= 3:
        score += 25
        reasons.append("strong name-title match")
    elif title_matches >= 2:
        score += 15
        reasons.append("name-title match")

    # Company/business terminology in result
    business_terms = [
        "private limited",
        "pvt ltd",
        "llp",
        "company",
        "official",
        "about us",
        "contact us",
        "services",
    ]

    term_matches = sum(
        1 for term in business_terms
        if term in (title_lower + " " + snippet_lower)
    )

    score += min(term_matches * 3, 12)

    if term_matches:
        reasons.append("business context")

    # Penalize known directory/social domains
    if is_bad_domain(url):
        score -= 60
        reasons.append("directory/social domain")

    return max(score, 0), "; ".join(reasons)


# ============================================================
# GOOGLE SEARCH
# ============================================================

async def google_search(page, query):
    """
    Search Google and collect organic result links.

    We use Playwright here because it avoids needing a Google API
    for this small initial test.
    """

    search_url = (
        "https://www.google.com/search?q="
        + query.replace(" ", "+")
    )

    try:
        await page.goto(
            search_url,
            wait_until="domcontentloaded",
            timeout=30000
        )

        await page.wait_for_timeout(1500)

    except PlaywrightTimeoutError:
        print("    Search page timed out.")
        return []

    except Exception as e:
        print(f"    Search error: {e}")
        return []

    results = []

    # Google result blocks
    blocks = await page.locator("div.MjjYud").all()

    for block in blocks:

        try:
            link = block.locator("a").first

            if not await link.count():
                continue

            href = await link.get_attribute("href")

            if not href:
                continue

            # We only want real external URLs
            if not href.startswith("http"):
                continue

            title_locator = block.locator("h3").first

            title = ""
            if await title_locator.count():
                title = await title_locator.inner_text()

            snippet = ""

            # Try to find common snippet containers
            snippet_selectors = [
                "div.VwiC3b",
                "div[data-sncf]",
                "span.aCOpRe",
            ]

            for selector in snippet_selectors:
                locator = block.locator(selector).first

                if await locator.count():
                    snippet = await locator.inner_text()
                    break

            results.append({
                "title": clean_text(title),
                "url": normalize_url(href),
                "snippet": clean_text(snippet),
            })

        except Exception:
            continue

    # Remove duplicates
    unique = []
    seen = set()

    for result in results:
        key = result["url"].lower()

        if key not in seen:
            seen.add(key)
            unique.append(result)

    return unique[:RESULTS_PER_STARTUP]


# ============================================================
# MAIN
# ============================================================

async def main():

    project_folder = Path(__file__).resolve().parent

    input_path = project_folder / INPUT_FILE
    output_path = project_folder / OUTPUT_FILE

    if not input_path.exists():
        print()
        print("ERROR: Input CSV was not found.")
        print()
        print(f"Expected:")
        print(input_path)
        print()
        return

    print("=" * 70)
    print("NAGPUR DPIIT - WEBSITE DISCOVERY TEST")
    print("=" * 70)

    print()
    print(f"Input:  {input_path}")
    print(f"Output: {output_path}")
    print()

    # Read data
    df = pd.read_csv(input_path)

    if "startupName" not in df.columns:
        print("ERROR: startupName column was not found.")
        print("Available columns:")
        print(df.columns.tolist())
        return

    # Only test startups with no existing website
    df = df[
        df["website"].isna()
        | (df["website"].astype(str).str.strip() == "")
    ].copy()

    df = df.head(TEST_ROWS)

    print(f"Testing {len(df)} startups.")
    print()

    output_rows = []

    async with async_playwright() as p:

        browser = await p.chromium.launch(
            headless=False
        )

        context = await browser.new_context(
            viewport={
                "width": 1280,
                "height": 900
            },
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            )
        )

        page = await context.new_page()

        for index, row in df.iterrows():

            startup_name = clean_text(row["startupName"])

            print("-" * 70)
            print(f"Startup {len(output_rows) + 1}/{len(df)}")
            print(f"Name: {startup_name}")

            # Search query
            query = f'"{startup_name}" Nagpur official website'

            print(f"Search: {query}")

            results = await google_search(page, query)

            print(f"Results found: {len(results)}")

            if not results:
                output_rows.append({
                    "startupId": row.get("startupId", ""),
                    "startupName": startup_name,
                    "searchQuery": query,
                    "candidateRank": "",
                    "candidateTitle": "",
                    "candidateURL": "",
                    "candidateDomain": "",
                    "candidateSnippet": "",
                    "candidateScore": 0,
                    "scoreReason": "",
                    "discoveryStatus": "NO_SEARCH_RESULTS",
                })

                await asyncio.sleep(DELAY_BETWEEN_SEARCHES)
                continue

            # Score each candidate
            for rank, result in enumerate(results, start=1):

                score, reason = score_candidate(
                    startup_name,
                    result["title"],
                    result["url"],
                    result["snippet"],
                )

                domain = get_domain(result["url"])

                # Don't include obviously bad results as official candidates,
                # but keep them in the CSV for inspection.
                if is_bad_domain(result["url"]):
                    status = "NON_OFFICIAL_DOMAIN"
                elif score >= 60:
                    status = "HIGH_PRIORITY_CANDIDATE"
                elif score >= 30:
                    status = "MEDIUM_PRIORITY_CANDIDATE"
                else:
                    status = "LOW_PRIORITY_CANDIDATE"

                output_rows.append({
                    "startupId": row.get("startupId", ""),
                    "startupName": startup_name,
                    "searchQuery": query,
                    "candidateRank": rank,
                    "candidateTitle": result["title"],
                    "candidateURL": result["url"],
                    "candidateDomain": domain,
                    "candidateSnippet": result["snippet"],
                    "candidateScore": score,
                    "scoreReason": reason,
                    "discoveryStatus": status,
                })

                print(
                    f"  {rank}. {result['url']} "
                    f"[score={score}]"
                )

            await asyncio.sleep(DELAY_BETWEEN_SEARCHES)

        await browser.close()

    # Save
    results_df = pd.DataFrame(output_rows)

    results_df.to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig"
    )

    print()
    print("=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)
    print()
    print(f"Rows written: {len(results_df):,}")
    print(f"File created:")
    print(output_path)
    print()
    print("IMPORTANT:")
    print("The candidateScore does NOT mean the website is confirmed.")
    print("We will manually inspect these 10 startups before scaling.")
    print()


if __name__ == "__main__":
    asyncio.run(main())