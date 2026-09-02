import asyncio
import re
from pathlib import Path
from urllib.parse import quote, urlparse

import pandas as pd
from playwright.async_api import async_playwright


# ============================================================
# SETTINGS
# ============================================================

INPUT_FILE = "Nagpur_DPIIT_Missing_Startups_Diagnostic.csv"

OUTPUT_FILE = "01_discovery_25.csv"

# Number of startups for this test
TEST_ROWS = 25

# Number of Google results we keep per startup
RESULTS_PER_STARTUP = 8

# Seconds between searches
DELAY = 5


# ============================================================
# DOMAINS WE DON'T WANT TO TREAT AS OFFICIAL WEBSITES
# ============================================================

DIRECTORY_DOMAINS = {
    "indiamart.com",
    "justdial.com",
    "sulekha.com",
    "tradeindia.com",
    "exportersindia.com",
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "youtube.com",
    "twitter.com",
    "x.com",
    "crunchbase.com",
    "tracxn.com",
    "zaubacorp.com",
    "tofler.in",
    "thecompanycheck.com",
    "ambitionbox.com",
    "glassdoor.com",
    "glassdoor.co.in",
    "indeed.com",
    "startupindia.gov.in",
}


# ============================================================
# HELPERS
# ============================================================

def clean_text(value):
    if not value:
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(value)
    ).strip()


def get_domain(url):

    try:

        domain = urlparse(url).netloc.lower()

        return domain.replace(
            "www.",
            ""
        )

    except Exception:

        return ""


def is_directory(url):

    domain = get_domain(url)

    return any(
        domain == bad
        or domain.endswith("." + bad)
        for bad in DIRECTORY_DOMAINS
    )


def looks_like_search_verification(text):

    text = text.lower()

    phrases = [
        "i'm not a robot",
        "i am not a robot",
        "unusual traffic",
        "verify you are human",
        "captcha",
        "automated queries",
    ]

    return any(
        phrase in text
        for phrase in phrases
    )


# ============================================================
# GOOGLE SEARCH
# ============================================================

async def google_search(
    page,
    startup_name
):

    query = (
        f'"{startup_name}" '
        f'Nagpur company website'
    )

    search_url = (
        "https://www.google.com/search?q="
        + quote(query)
    )

    print()
    print(
        f"Searching: {startup_name}"
    )

    try:

        await page.goto(
            search_url,
            wait_until="domcontentloaded",
            timeout=30000
        )

        await page.wait_for_timeout(
            2500
        )

    except Exception as e:

        print(
            "Navigation error:",
            e
        )

        return query, [], "NAVIGATION_ERROR"

    # --------------------------------------------------------
    # CAPTCHA / verification detection
    # --------------------------------------------------------

    body_text = ""

    try:

        body_text = await page.locator(
            "body"
        ).inner_text()

    except Exception:

        pass

    if looks_like_search_verification(
        body_text
    ):

        print()
        print("=" * 70)
        print("GOOGLE VERIFICATION DETECTED")
        print("=" * 70)
        print()
        print(
            "Complete Google's normal verification "
            "in the browser."
        )
        print()
        print(
            "When finished, return to this CMD window "
            "and press ENTER."
        )
        print()

        input()

        # Reload search after verification

        try:

            await page.goto(
                search_url,
                wait_until="domcontentloaded",
                timeout=30000
            )

            await page.wait_for_timeout(
                2500
            )

        except Exception as e:

            print(
                "Reload error:",
                e
            )

            return (
                query,
                [],
                "VERIFICATION_RELOAD_ERROR"
            )

    # --------------------------------------------------------
    # Extract Google results
    # --------------------------------------------------------

    results = []

    blocks = page.locator(
        "div.MjjYud"
    )

    count = await blocks.count()

    print(
        f"Result blocks detected: {count}"
    )

    for i in range(count):

        block = blocks.nth(i)

        try:

            title_locator = block.locator(
                "h3"
            ).first

            if await title_locator.count() == 0:
                continue

            title = clean_text(
                await title_locator.inner_text()
            )

            # Find link containing the title
            link = title_locator.locator(
                "xpath=ancestor::a"
            )

            if await link.count() == 0:
                continue

            href = await link.get_attribute(
                "href"
            )

            if not href:
                continue

            # Ignore Google internal links
            if not href.startswith(
                "http"
            ):
                continue

            snippet = ""

            snippet_locator = block.locator(
                "div.VwiC3b"
            ).first

            if await snippet_locator.count():

                snippet = clean_text(
                    await snippet_locator.inner_text()
                )

            results.append({
                "title": title,
                "url": href,
                "domain": get_domain(href),
                "snippet": snippet,
            })

        except Exception:

            continue

    # --------------------------------------------------------
    # Remove duplicate URLs
    # --------------------------------------------------------

    unique = []

    seen = set()

    for result in results:

        url = result["url"].lower()

        if url in seen:
            continue

        seen.add(url)

        unique.append(result)

    return (
        query,
        unique[:RESULTS_PER_STARTUP],
        "SUCCESS"
    )


# ============================================================
# MAIN
# ============================================================

async def main():

    folder = Path(
        __file__
    ).resolve().parent

    input_path = (
        folder / INPUT_FILE
    )

    output_path = (
        folder / OUTPUT_FILE
    )

    if not input_path.exists():

        print()
        print(
            "ERROR: Diagnostic CSV not found."
        )
        print()
        print(input_path)
        print()

        return

    # --------------------------------------------------------
    # Read diagnostic file
    # --------------------------------------------------------

    df = pd.read_csv(
        input_path
    )

    if "startupName" not in df.columns:

        print(
            "ERROR: startupName column "
            "was not found."
        )

        print(
            df.columns.tolist()
        )

        return

    # Only startups without website
    df = df[
        df["website"].isna()
        |
        (
            df["website"]
            .astype(str)
            .str.strip()
            == ""
        )
    ]

    df = df.head(
        TEST_ROWS
    )

    print()
    print("=" * 70)
    print("NAGPUR DPIIT — 25 STARTUP DISCOVERY TEST")
    print("=" * 70)
    print()
    print(
        f"Startups to process: {len(df)}"
    )
    print()

    # --------------------------------------------------------
    # Existing progress
    # --------------------------------------------------------

    existing = []

    if output_path.exists():

        try:

            previous = pd.read_csv(
                output_path
            )

            existing = previous.to_dict(
                "records"
            )

            print(
                f"Existing saved results: "
                f"{len(existing)}"
            )

        except Exception:

            existing = []

    processed_ids = {
        str(row.get("startupId", ""))
        for row in existing
    }

    # --------------------------------------------------------
    # Start browser
    # --------------------------------------------------------

    profile_path = (
        folder /
        "discovery_browser_profile"
    )

    async with async_playwright() as p:

        context = (
            await p.chromium
            .launch_persistent_context(
                str(profile_path),
                headless=False,
                viewport={
                    "width": 1366,
                    "height": 900,
                },
            )
        )

        if context.pages:

            page = context.pages[0]

        else:

            page = await context.new_page()

        # ----------------------------------------------------
        # Open Google first
        # ----------------------------------------------------

        await page.goto(
            "https://www.google.com",
            wait_until="domcontentloaded"
        )

        await page.wait_for_timeout(
            2000
        )

        print()
        print(
            "A browser window is open."
        )
        print(
            "Make sure Google loads normally."
        )
        print()

        input(
            "Press ENTER to begin the 25-startup test..."
        )

        # ----------------------------------------------------
        # Process startups
        # ----------------------------------------------------

        for number, (_, row) in enumerate(
            df.iterrows(),
            start=1
        ):

            startup_id = str(
                row.get(
                    "startupId",
                    ""
                )
            ).strip()

            startup_name = clean_text(
                row["startupName"]
            )

            # Skip if already completed
            if startup_id in processed_ids:

                print(
                    f"Skipping already processed: "
                    f"{startup_name}"
                )

                continue

            print()
            print("=" * 70)
            print(
                f"{number}/{len(df)}"
            )
            print(
                startup_name
            )
            print("=" * 70)

            query, results, status = (
                await google_search(
                    page,
                    startup_name
                )
            )

            if not results:

                existing.append({

                    "startupId":
                        startup_id,

                    "startupName":
                        startup_name,

                    "searchQuery":
                        query,

                    "candidateRank":
                        "",

                    "candidateTitle":
                        "",

                    "candidateURL":
                        "",

                    "candidateDomain":
                        "",

                    "candidateSnippet":
                        "",

                    "sourceType":
                        "",

                    "searchStatus":
                        status,

                    "needsManualReview":
                        "YES",

                })

            else:

                for rank, result in enumerate(
                    results,
                    start=1
                ):

                    if is_directory(
                        result["url"]
                    ):

                        source_type = (
                            "DIRECTORY_SOCIAL"
                        )

                    else:

                        source_type = (
                            "POSSIBLE_COMPANY_SITE"
                        )

                    existing.append({

                        "startupId":
                            startup_id,

                        "startupName":
                            startup_name,

                        "searchQuery":
                            query,

                        "candidateRank":
                            rank,

                        "candidateTitle":
                            result["title"],

                        "candidateURL":
                            result["url"],

                        "candidateDomain":
                            result["domain"],

                        "candidateSnippet":
                            result["snippet"],

                        "sourceType":
                            source_type,

                        "searchStatus":
                            status,

                        "needsManualReview":
                            "YES",

                    })

                    print(
                        f"{rank}. "
                        f"{result['domain']} "
                        f"({source_type})"
                    )

            # ------------------------------------------------
            # SAVE AFTER EVERY STARTUP
            # ------------------------------------------------

            output_df = pd.DataFrame(
                existing
            )

            output_df.to_csv(
                output_path,
                index=False,
                encoding="utf-8-sig"
            )

            print()
            print(
                "Progress saved."
            )

            await asyncio.sleep(
                DELAY
            )

        await context.close()

    print()
    print("=" * 70)
    print("25-STARTUP DISCOVERY TEST COMPLETE")
    print("=" * 70)
    print()
    print(
        f"Output: {output_path}"
    )
    print()


if __name__ == "__main__":

    asyncio.run(main())