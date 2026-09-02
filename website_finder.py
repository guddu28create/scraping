import asyncio
import re
from pathlib import Path
from urllib.parse import quote, urlparse

import pandas as pd
from playwright.async_api import async_playwright


# ============================================================
# SETTINGS
# ============================================================

TEST_LIMIT = None
# None = process ALL startups
# For a test, change to 25

DELAY_SECONDS = 6

OUTPUT_FILE = "03_website_discovery.csv"

PROFILE_FOLDER = "website_discovery_browser"

MAX_RESULTS_PER_SEARCH = 10


# ============================================================
# DOMAINS THAT ARE NOT OFFICIAL COMPANY WEBSITES
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
    "companydetails.in",
    "quickcompany.in",
    "instafinancials.com",
    "indiafilings.com",
    "corporatedir.com",
    "fundoodata.com",
    "signalhire.com",
}


SEARCH_ENGINE_DOMAINS = {
    "google.com",
    "google.co.in",
    "googleusercontent.com",
    "gstatic.com",
    "bing.com",
    "bingj.com",
    "microsoft.com",
}


# ============================================================
# HELPERS
# ============================================================

def clean(value):
    if pd.isna(value):
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(value)
    ).strip()


def domain(url):

    try:
        return (
            urlparse(url)
            .netloc
            .lower()
            .replace("www.", "")
        )
    except Exception:
        return ""


def is_directory(url):

    d = domain(url)

    return any(
        d == bad
        or d.endswith("." + bad)
        for bad in DIRECTORY_DOMAINS
    )


def is_search_engine(url):

    d = domain(url)

    return any(
        d == bad
        or d.endswith("." + bad)
        for bad in SEARCH_ENGINE_DOMAINS
    )


def is_valid_url(url):

    if not url:
        return False

    return url.startswith(
        ("http://", "https://")
    )


def verification_page(text):

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


def company_tokens(name):

    # Remove legal/company suffixes.
    text = name.upper()

    suffixes = [
        " PRIVATE LIMITED",
        " PVT LTD",
        " PVT. LTD.",
        " LIMITED",
        " LTD",
        " LLP",
        " OPC",
        " COMPANY",
        " CO.",
        " & CO",
    ]

    for suffix in suffixes:
        text = text.replace(
            suffix,
            ""
        )

    # Keep meaningful words.
    words = re.findall(
        r"[A-Z0-9]+",
        text
    )

    ignored = {
        "THE",
        "AND",
        "OF",
        "FOR",
        "INDIA",
        "NAGPUR",
    }

    return [
        x.lower()
        for x in words
        if len(x) >= 3
        and x not in ignored
    ]


# ============================================================
# EXTRACT LINKS FROM RENDERED SEARCH PAGE
# ============================================================

async def collect_links(page):

    links = page.locator(
        "a[href]"
    )

    count = await links.count()

    found = []
    seen = set()

    for i in range(count):

        try:

            a = links.nth(i)

            href = await a.get_attribute(
                "href"
            )

            text = clean(
                await a.inner_text()
            )

            if not is_valid_url(href):
                continue

            if is_search_engine(href):
                continue

            if href in seen:
                continue

            seen.add(href)

            found.append({
                "title": text,
                "url": href,
                "domain": domain(href),
            })

        except Exception:
            continue

    return found


# ============================================================
# SEARCH GOOGLE
# ============================================================

async def google_search(
    page,
    startup_name
):

    query = (
        f'"{startup_name}" '
        f'Nagpur official website'
    )

    url = (
        "https://www.google.com/search?q="
        + quote(query)
    )

    try:

        await page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=30000
        )

        await page.wait_for_timeout(
            3000
        )

    except Exception as e:

        return query, [], "GOOGLE_NAV_ERROR"

    try:
        body = await page.locator(
            "body"
        ).inner_text()
    except:
        body = ""

    if verification_page(body):

        print()
        print("=" * 65)
        print("GOOGLE VERIFICATION")
        print("=" * 65)
        print(
            "Complete the normal verification "
            "in the browser."
        )
        print(
            "Do NOT close the browser."
        )
        input(
            "After completing it, press ENTER here: "
        )

        try:

            await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=30000
            )

            await page.wait_for_timeout(
                3000
            )

        except:
            return (
                query,
                [],
                "GOOGLE_RELOAD_ERROR"
            )

    links = await collect_links(
        page
    )

    return (
        query,
        links[:MAX_RESULTS_PER_SEARCH],
        "SUCCESS"
    )


# ============================================================
# SEARCH BING
# ============================================================

async def bing_search(
    page,
    startup_name
):

    query = (
        f'"{startup_name}" '
        f'Nagpur official website'
    )

    url = (
        "https://www.bing.com/search?q="
        + quote(query)
    )

    try:

        await page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=30000
        )

        await page.wait_for_timeout(
            3000
        )

    except Exception:

        return query, [], "BING_NAV_ERROR"

    try:
        body = await page.locator(
            "body"
        ).inner_text()
    except:
        body = ""

    if verification_page(body):

        print()
        print(
            "Bing verification detected."
        )
        print(
            "Complete it normally in the browser."
        )

        input(
            "Press ENTER after completion: "
        )

        try:

            await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=30000
            )

            await page.wait_for_timeout(
                3000
            )

        except:
            return (
                query,
                [],
                "BING_RELOAD_ERROR"
            )

    links = await collect_links(
        page
    )

    return (
        query,
        links[:MAX_RESULTS_PER_SEARCH],
        "SUCCESS"
    )


# ============================================================
# SCORE WEBSITE CANDIDATES
# ============================================================

def score_candidate(
    startup_name,
    candidate
):

    url = candidate["url"]

    if is_directory(url):

        return 0, "DIRECTORY"

    tokens = company_tokens(
        startup_name
    )

    title = candidate["title"].lower()
    d = candidate["domain"].lower()

    score = 0
    reasons = []

    # Company words in domain
    matched_domain = [
        t for t in tokens
        if t in d
    ]

    if matched_domain:

        score += min(
            len(matched_domain) * 25,
            60
        )

        reasons.append(
            "company_name_in_domain"
        )

    # Company words in result title
    matched_title = [
        t for t in tokens
        if t in title
    ]

    if matched_title:

        score += min(
            len(matched_title) * 15,
            30
        )

        reasons.append(
            "company_name_in_title"
        )

    # Very short generic domains are less trustworthy.
    if len(d.split(".")[0]) >= 4:
        score += 5

    if score >= 60:

        status = "STRONG_CANDIDATE"

    elif score >= 30:

        status = "POSSIBLE_CANDIDATE"

    else:

        status = "WEAK_CANDIDATE"

    return score, status + "|" + ",".join(
        reasons
    )


# ============================================================
# MAIN
# ============================================================

async def main():

    folder = Path(
        __file__
    ).resolve().parent

    # --------------------------------------------------------
    # Find diagnostic CSV automatically
    # --------------------------------------------------------

    files = list(
        folder.glob(
            "Nagpur_DPIIT_Missing_Startups_Diagnostic*.csv"
        )
    )

    if not files:

        print()
        print(
            "ERROR: Could not find the diagnostic CSV."
        )
        print(
            "Put Nagpur_DPIIT_Missing_Startups_Diagnostic.csv "
            "in this folder:"
        )
        print(folder)
        return

    input_path = files[0]

    print()
    print(
        "Using input:"
    )
    print(input_path)

    df = pd.read_csv(
        input_path
    )

    # --------------------------------------------------------
    # Check startup column
    # --------------------------------------------------------

    possible_name_columns = [
        "startupName",
        "Startup Name",
        "startup_name",
        "name",
        "Name",
    ]

    name_column = None

    for col in possible_name_columns:

        if col in df.columns:

            name_column = col
            break

    if not name_column:

        print()
        print(
            "ERROR: Could not find startup name column."
        )
        print(
            "Columns found:"
        )
        print(
            df.columns.tolist()
        )
        return

    # --------------------------------------------------------
    # Filter missing websites
    # --------------------------------------------------------

    if "website" in df.columns:

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

    if TEST_LIMIT is not None:

        df = df.head(
            TEST_LIMIT
        )

    print()
    print("=" * 65)
    print("WEBSITE DISCOVERY")
    print("=" * 65)
    print()
    print(
        f"Startups to process: {len(df)}"
    )

    # --------------------------------------------------------
    # Resume previous results
    # --------------------------------------------------------

    output_path = (
        folder / OUTPUT_FILE
    )

    if output_path.exists():

        previous = pd.read_csv(
            output_path
        )

        results = previous.to_dict(
            "records"
        )

        completed = set(
            previous[
                "startupId"
            ].astype(str)
        ) if "startupId" in previous.columns else set()

        print(
            f"Existing saved rows: "
            f"{len(results)}"
        )

    else:

        results = []
        completed = set()

    # --------------------------------------------------------
    # Browser
    # --------------------------------------------------------

    async with async_playwright() as p:

        profile = (
            folder /
            PROFILE_FOLDER
        )

        context = (
            await p.chromium
            .launch_persistent_context(
                str(profile),
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

        # Open Google
        await page.goto(
            "https://www.google.com",
            wait_until="domcontentloaded"
        )

        await page.wait_for_timeout(
            2000
        )

        print()
        print(
            "Browser opened."
        )
        print(
            "Complete any normal Google verification "
            "if it appears."
        )
        print()

        input(
            "Press ENTER to start: "
        )

        # ----------------------------------------------------
        # Process startups
        # ----------------------------------------------------

        for number, (_, row) in enumerate(
            df.iterrows(),
            start=1
        ):

            startup_id = clean(
                row.get(
                    "startupId",
                    number
                )
            )

            startup_name = clean(
                row[name_column]
            )

            if startup_id in completed:

                continue

            print()
            print("=" * 65)
            print(
                f"{number}/{len(df)}"
            )
            print(
                startup_name
            )
            print("=" * 65)

            # ------------------------------------------------
            # Google
            # ------------------------------------------------

            (
                google_query,
                google_links,
                google_status
            ) = await google_search(
                page,
                startup_name
            )

            candidates = []

            for item in google_links:

                score, score_status = (
                    score_candidate(
                        startup_name,
                        item
                    )
                )

                candidates.append({
                    "startupId":
                        startup_id,

                    "startupName":
                        startup_name,

                    "searchEngine":
                        "Google",

                    "searchQuery":
                        google_query,

                    "candidateURL":
                        item["url"],

                    "candidateDomain":
                        item["domain"],

                    "candidateTitle":
                        item["title"],

                    "candidateType":
                        (
                            "DIRECTORY"
                            if is_directory(
                                item["url"]
                            )
                            else "WEBSITE"
                        ),

                    "score":
                        score,

                    "scoreStatus":
                        score_status,

                    "searchStatus":
                        google_status,

                    "manualDecision":
                        "",

                    "notes":
                        "",
                })

            # ------------------------------------------------
            # Bing fallback
            # ------------------------------------------------

            non_directory = [
                x for x in candidates
                if x["candidateType"] == "WEBSITE"
            ]

            if not non_directory:

                (
                    bing_query,
                    bing_links,
                    bing_status
                ) = await bing_search(
                    page,
                    startup_name
                )

                for item in bing_links:

                    # Don't duplicate domains
                    if any(
                        x["candidateDomain"]
                        == item["domain"]
                        for x in candidates
                    ):
                        continue

                    score, score_status = (
                        score_candidate(
                            startup_name,
                            item
                        )
                    )

                    candidates.append({
                        "startupId":
                            startup_id,

                        "startupName":
                            startup_name,

                        "searchEngine":
                            "Bing",

                        "searchQuery":
                            bing_query,

                        "candidateURL":
                            item["url"],

                        "candidateDomain":
                            item["domain"],

                        "candidateTitle":
                            item["title"],

                        "candidateType":
                            (
                                "DIRECTORY"
                                if is_directory(
                                    item["url"]
                                )
                                else "WEBSITE"
                            ),

                        "score":
                            score,

                        "scoreStatus":
                            score_status,

                        "searchStatus":
                            bing_status,

                        "manualDecision":
                            "",

                        "notes":
                            "",
                    })

            # ------------------------------------------------
            # If nothing found
            # ------------------------------------------------

            if not candidates:

                candidates.append({
                    "startupId":
                        startup_id,

                    "startupName":
                        startup_name,

                    "searchEngine":
                        "",

                    "searchQuery":
                        google_query,

                    "candidateURL":
                        "",

                    "candidateDomain":
                        "",

                    "candidateTitle":
                        "",

                    "candidateType":
                        "NO_RESULT",

                    "score":
                        0,

                    "scoreStatus":
                        "NO_RESULT",

                    "searchStatus":
                        google_status,

                    "manualDecision":
                        "NEEDS_REVIEW",

                    "notes":
                        "No candidate URL found",
                })

            # ------------------------------------------------
            # Add results
            # ------------------------------------------------

            results.extend(
                candidates
            )

            # ------------------------------------------------
            # SAVE IMMEDIATELY
            # ------------------------------------------------

            pd.DataFrame(
                results
            ).to_csv(
                output_path,
                index=False,
                encoding="utf-8-sig"
            )

            print()
            print(
                f"Candidates found: "
                f"{len(candidates)}"
            )

            for candidate in sorted(
                candidates,
                key=lambda x: x["score"],
                reverse=True
            )[:5]:

                print(
                    f"  {candidate['score']:>3} | "
                    f"{candidate['candidateType']:<10} | "
                    f"{candidate['candidateDomain']}"
                )

            print(
                "Progress saved."
            )

            await asyncio.sleep(
                DELAY_SECONDS
            )

        await context.close()

    print()
    print("=" * 65)
    print("DISCOVERY COMPLETE")
    print("=" * 65)
    print()
    print(
        f"Output: {output_path}"
    )


if __name__ == "__main__":
    asyncio.run(main())