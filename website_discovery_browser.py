import asyncio
import re
from pathlib import Path
from urllib.parse import quote, urlparse

import pandas as pd
from playwright.async_api import async_playwright


INPUT_FILE = "Nagpur_DPIIT_Missing_Startups_Diagnostic.csv"
OUTPUT_FILE = "01_website_discovery_test_10.csv"

TEST_ROWS = 10

# Playwright will create this profile locally.
BROWSER_PROFILE = "search_browser_profile"


def clean_text(text):
    if not text:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip()


def get_domain(url):
    try:
        return urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return ""


async def search_google(page, startup_name):

    query = f'"{startup_name}" Nagpur official website'

    url = (
        "https://www.google.com/search?q="
        + quote(query)
    )

    print()
    print(f"Searching: {startup_name}")

    await page.goto(
        url,
        wait_until="domcontentloaded",
        timeout=30000
    )

    await page.wait_for_timeout(2000)

    # Detect Google's verification page.
    page_text = (await page.locator("body").inner_text()).lower()

    verification_words = [
        "i'm not a robot",
        "i am not a robot",
        "unusual traffic",
        "verify you are human",
        "captcha",
    ]

    if any(word in page_text for word in verification_words):

        print()
        print("=" * 65)
        print("GOOGLE VERIFICATION DETECTED")
        print("=" * 65)
        print()
        print("Please complete the verification normally in the browser.")
        print("Do NOT close the browser.")
        print()
        print("After you finish it, press ENTER here.")
        input()

        # Reload after verification.
        await page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=30000
        )

        await page.wait_for_timeout(2000)

    results = []

    # Google organic result blocks.
    blocks = page.locator("div.MjjYud")

    count = await blocks.count()

    print(f"Result blocks detected: {count}")

    for i in range(count):

        block = blocks.nth(i)

        try:

            title_locator = block.locator("h3").first

            if await title_locator.count() == 0:
                continue

            title = clean_text(
                await title_locator.inner_text()
            )

            link = title_locator.locator("xpath=ancestor::a")

            if await link.count() == 0:
                continue

            href = await link.get_attribute("href")

            if not href:
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

    return query, results


async def main():

    folder = Path(__file__).resolve().parent

    input_path = folder / INPUT_FILE
    output_path = folder / OUTPUT_FILE
    profile_path = folder / BROWSER_PROFILE

    if not input_path.exists():

        print("ERROR: CSV not found:")
        print(input_path)
        return

    df = pd.read_csv(input_path)

    # Only startups without websites.
    df = df[
        df["website"].isna()
        | (df["website"].astype(str).str.strip() == "")
    ].head(TEST_ROWS)

    print("=" * 65)
    print("NAGPUR DPIIT - BROWSER DISCOVERY TEST")
    print("=" * 65)
    print()
    print(f"Testing: {len(df)} startups")
    print()

    output = []

    async with async_playwright() as p:

        # Persistent profile.
        context = await p.chromium.launch_persistent_context(
            str(profile_path),
            headless=False,
            viewport={
                "width": 1366,
                "height": 900
            }
        )

        page = (
            context.pages[0]
            if context.pages
            else await context.new_page()
        )

        # Open Google once first.
        await page.goto(
            "https://www.google.com",
            wait_until="domcontentloaded"
        )

        print()
        print("A browser window should now be open.")
        print()
        print("If Google asks you to sign in, you may do so.")
        print("If Google asks for human verification, complete it normally.")
        print()
        input("When Google is ready, press ENTER here...")

        for number, (_, row) in enumerate(
            df.iterrows(),
            start=1
        ):

            startup_name = clean_text(
                row["startupName"]
            )

            print()
            print("-" * 65)
            print(f"{number}/{len(df)}")
            print(startup_name)

            try:

                query, results = await search_google(
                    page,
                    startup_name
                )

                if not results:

                    print("No results extracted.")

                    output.append({
                        "startupId": row.get(
                            "startupId", ""
                        ),
                        "startupName": startup_name,
                        "searchQuery": query,
                        "candidateRank": "",
                        "candidateTitle": "",
                        "candidateURL": "",
                        "candidateDomain": "",
                        "candidateSnippet": "",
                        "discoveryStatus": "NO_RESULTS_EXTRACTED",
                    })

                else:

                    print(
                        f"Extracted {len(results)} results."
                    )

                    for rank, result in enumerate(
                        results,
                        start=1
                    ):

                        print(
                            f"{rank}. "
                            f"{result['domain']}"
                        )

                        output.append({
                            "startupId": row.get(
                                "startupId", ""
                            ),
                            "startupName": startup_name,
                            "searchQuery": query,
                            "candidateRank": rank,
                            "candidateTitle": result["title"],
                            "candidateURL": result["url"],
                            "candidateDomain": result["domain"],
                            "candidateSnippet": result["snippet"],
                            "discoveryStatus": "SEARCH_RESULT",
                        })

            except Exception as e:

                print(f"ERROR: {e}")

                output.append({
                    "startupId": row.get(
                        "startupId", ""
                    ),
                    "startupName": startup_name,
                    "searchQuery": "",
                    "candidateRank": "",
                    "candidateTitle": "",
                    "candidateURL": "",
                    "candidateDomain": "",
                    "candidateSnippet": "",
                    "discoveryStatus": "ERROR",
                })

            # Short pause between searches.
            await asyncio.sleep(4)

        await context.close()

    result_df = pd.DataFrame(output)

    result_df.to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig"
    )

    print()
    print("=" * 65)
    print("TEST FINISHED")
    print("=" * 65)
    print()
    print(f"Created: {output_path}")
    print(f"Rows: {len(result_df)}")
    print()


if __name__ == "__main__":
    asyncio.run(main())