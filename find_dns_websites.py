from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import csv
import os
import re
import time
from urllib.parse import quote_plus, urlparse, parse_qs, unquote


# ============================================================
# SETTINGS
# ============================================================

BASE_FOLDER = r"C:\Users\ASUS\OneDrive\Desktop\Nagpur_Startup_Scraper"

INPUT_FILE = os.path.join(
    BASE_FOLDER,
    "Nagpur_DPIIT_Startups_Errors.csv"
)

OUTPUT_FILE = os.path.join(
    BASE_FOLDER,
    "Nagpur_DNS_Website_Candidates.csv"
)

# Number of search queries per company
SEARCH_QUERIES = [
    '"{company}" Nagpur',
    '"{company}" website',
    '"{company}" official website',
    '"{company}" India',
    '"{company}" founder',
    '"{company}" LinkedIn'
]

# Maximum candidates stored per company
MAX_CANDIDATES = 5

# Search timeout
SEARCH_TIMEOUT = 20000

# Time between searches
DELAY_BETWEEN_SEARCHES = 2

# Visible browser
HEADLESS = False


# ============================================================
# DOMAINS TO REJECT
# ============================================================

IGNORED_DOMAINS = [

    # Search engines
    "duckduckgo.com",
    "google.com",
    "google.co.in",
    "bing.com",
    "yahoo.com",

    # Social media
    "linkedin.com",
    "facebook.com",
    "instagram.com",
    "twitter.com",
    "x.com",
    "youtube.com",

    # Company information / directory sites
    "tracxn.com",
    "thecompanycheck.com",
    "zaubacorp.com",
    "tofler.in",
    "falconebiz.com",
    "planetexim.net",
    "quickcompany.in",
    "companydetails.in",
    "economictimes.indiatimes.com",
    "ambitionbox.com",
    "glassdoor.com",

    # Business directories
    "justdial.com",
    "indiamart.com",
    "tradeindia.com",
    "exportersindia.com",
    "sulekha.com",
    "asklaila.com",
    "yellowpages.in",

    # Government / registry pages
    "mca.gov.in",
    "startupindia.gov.in",

    # Job websites
    "naukri.com",
    "indeed.com",
    "foundit.in",
    "internshala.com",

]


# ============================================================
# OUTPUT COLUMNS
# ============================================================

OUTPUT_FIELDS = [

    "startupId",
    "startupName",
    "originalWebsite",
    "errorType",

    "searchStatus",
    "queriesAttempted",
    "queriesWithResults",

    "candidate1Title",
    "candidate1URL",
    "candidate1Domain",
    "candidate1Query",

    "candidate2Title",
    "candidate2URL",
    "candidate2Domain",
    "candidate2Query",

    "candidate3Title",
    "candidate3URL",
    "candidate3Domain",
    "candidate3Query",

    "candidate4Title",
    "candidate4URL",
    "candidate4Domain",
    "candidate4Query",

    "candidate5Title",
    "candidate5URL",
    "candidate5Domain",
    "candidate5Query",

]


# ============================================================
# CLEAN TEXT
# ============================================================

def clean_text(value):

    if not value:
        return ""

    value = value.replace("\n", " ")

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    return value.strip()


# ============================================================
# NORMALIZE DOMAIN
# ============================================================

def normalize_domain(url):

    try:

        parsed = urlparse(url)

        domain = parsed.netloc.lower()

        domain = re.sub(
            r"^www\.",
            "",
            domain
        )

        return domain

    except Exception:

        return ""


# ============================================================
# EXTRACT REAL URL FROM DUCKDUCKGO
# ============================================================

def extract_real_url(href):

    if not href:
        return ""

    href = href.strip()

    # DuckDuckGo often gives:
    #
    # //duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com
    #
    if href.startswith("//"):

        href = "https:" + href


    try:

        parsed = urlparse(href)

        domain = parsed.netloc.lower()


        # ----------------------------------------------------
        # DuckDuckGo redirect
        # ----------------------------------------------------

        if (
            "duckduckgo.com" in domain
            and "/l/" in parsed.path
        ):

            params = parse_qs(
                parsed.query
            )


            if "uddg" in params:

                real_url = params["uddg"][0]

                return unquote(
                    real_url
                )


    except Exception:

        pass


    # --------------------------------------------------------
    # Direct URL
    # --------------------------------------------------------

    if href.startswith(
        ("http://", "https://")
    ):

        return href


    return ""


# ============================================================
# CHECK WHETHER DOMAIN SHOULD BE REJECTED
# ============================================================

def is_ignored_domain(domain):

    domain = domain.lower()

    for ignored in IGNORED_DOMAINS:

        if (
            domain == ignored
            or domain.endswith(
                "." + ignored
            )
        ):

            return True

    return False


# ============================================================
# CHECK WHETHER URL IS VALID CANDIDATE
# ============================================================

def is_valid_candidate(url):

    if not url:
        return False

    if not url.startswith(
        ("http://", "https://")
    ):
        return False


    domain = normalize_domain(
        url
    )


    if not domain:
        return False


    if is_ignored_domain(
        domain
    ):
        return False


    # Ignore obvious files
    lower_url = url.lower()

    if lower_url.endswith(
        (
            ".pdf",
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".webp",
            ".doc",
            ".docx",
            ".xls",
            ".xlsx"
        )
    ):
        return False


    return True


# ============================================================
# SEARCH ONE QUERY
# ============================================================

def search_query(
    page,
    query
):

    search_url = (
        "https://html.duckduckgo.com/html/?q="
        + quote_plus(query)
    )


    try:

        page.goto(
            search_url,
            wait_until="domcontentloaded",
            timeout=SEARCH_TIMEOUT
        )


    except PlaywrightTimeoutError:

        print(
            "Search timed out."
        )


    except Exception as e:

        print(
            "Search error:",
            e
        )

        return []


    time.sleep(1.5)


    candidates = []


    try:

        result_links = page.locator(
            "a.result__a"
        )


        count = result_links.count()


        print(
            "  Results found:",
            count
        )


        for i in range(
            min(count, 10)
        ):

            try:

                link = result_links.nth(i)


                title = clean_text(
                    link.inner_text()
                )


                raw_href = (
                    link.get_attribute(
                        "href"
                    )
                    or ""
                )


                real_url = extract_real_url(
                    raw_href
                )


                if not is_valid_candidate(
                    real_url
                ):

                    continue


                domain = normalize_domain(
                    real_url
                )


                candidates.append({

                    "title": title,

                    "url": real_url,

                    "domain": domain,

                    "query": query

                })


            except Exception:

                continue


    except Exception as e:

        print(
            "Could not read search results:",
            e
        )


    return candidates


# ============================================================
# SEARCH ONE COMPANY USING MULTIPLE QUERIES
# ============================================================

def search_company(
    page,
    company_name
):

    all_candidates = []

    seen_domains = set()

    queries_attempted = 0

    queries_with_results = 0


    for template in SEARCH_QUERIES:

        query = template.format(
            company=company_name
        )


        queries_attempted += 1


        print()
        print(
            "  Query:",
            query
        )


        candidates = search_query(
            page,
            query
        )


        if candidates:

            queries_with_results += 1


        for candidate in candidates:

            domain = candidate[
                "domain"
            ]


            # ------------------------------------------------
            # One candidate per domain
            # ------------------------------------------------

            if domain in seen_domains:

                continue


            seen_domains.add(
                domain
            )


            all_candidates.append(
                candidate
            )


            print(
                "  Candidate:",
                candidate["url"]
            )


            if len(
                all_candidates
            ) >= MAX_CANDIDATES:

                break


        if len(
            all_candidates
        ) >= MAX_CANDIDATES:

            break


        time.sleep(
            DELAY_BETWEEN_SEARCHES
        )


    return (
        all_candidates[:MAX_CANDIDATES],
        queries_attempted,
        queries_with_results
    )


# ============================================================
# CREATE OUTPUT FILE
# ============================================================

def create_output_file():

    if os.path.exists(
        OUTPUT_FILE
    ):

        return


    with open(
        OUTPUT_FILE,
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=OUTPUT_FIELDS
        )

        writer.writeheader()


# ============================================================
# LOAD ALREADY PROCESSED STARTUPS
# ============================================================

def load_processed_ids():

    processed = set()


    if not os.path.exists(
        OUTPUT_FILE
    ):

        return processed


    try:

        with open(
            OUTPUT_FILE,
            "r",
            newline="",
            encoding="utf-8-sig"
        ) as file:

            reader = csv.DictReader(
                file
            )


            for row in reader:

                startup_id = (
                    row.get(
                        "startupId",
                        ""
                    )
                    .strip()
                )


                startup_name = (
                    row.get(
                        "startupName",
                        ""
                    )
                    .strip()
                )


                # ------------------------------------------------
                # Prefer ID
                # ------------------------------------------------

                if startup_id:

                    processed.add(
                        "ID:" + startup_id
                    )


                elif startup_name:

                    processed.add(
                        "NAME:" + startup_name.lower()
                    )


    except Exception as e:

        print(
            "Could not read existing output:",
            e
        )


    return processed


# ============================================================
# SAVE ONE COMPANY
# ============================================================

def save_company(
    row,
    candidates,
    queries_attempted,
    queries_with_results,
    status
):

    result = {

        "startupId":
            row.get(
                "startupId",
                ""
            ),

        "startupName":
            row.get(
                "startupName",
                ""
            ),

        "originalWebsite":
            row.get(
                "website",
                ""
            ),

        "errorType":
            row.get(
                "errorType",
                ""
            ),

        "searchStatus":
            status,

        "queriesAttempted":
            queries_attempted,

        "queriesWithResults":
            queries_with_results,

    }


    # --------------------------------------------------------
    # Candidate columns
    # --------------------------------------------------------

    for i in range(
        1,
        MAX_CANDIDATES + 1
    ):

        if i <= len(
            candidates
        ):

            candidate = candidates[
                i - 1
            ]


            result[
                f"candidate{i}Title"
            ] = candidate[
                "title"
            ]


            result[
                f"candidate{i}URL"
            ] = candidate[
                "url"
            ]


            result[
                f"candidate{i}Domain"
            ] = candidate[
                "domain"
            ]


            result[
                f"candidate{i}Query"
            ] = candidate[
                "query"
            ]


        else:

            result[
                f"candidate{i}Title"
            ] = ""

            result[
                f"candidate{i}URL"
            ] = ""

            result[
                f"candidate{i}Domain"
            ] = ""

            result[
                f"candidate{i}Query"
            ] = ""


    # --------------------------------------------------------
    # Append immediately
    # --------------------------------------------------------

    with open(
        OUTPUT_FILE,
        "a",
        newline="",
        encoding="utf-8-sig"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=OUTPUT_FIELDS
        )

        writer.writerow(
            result
        )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 75)
    print(
        "451 DNS WEBSITE RECOVERY"
    )
    print("=" * 75)


    # --------------------------------------------------------
    # CHECK INPUT
    # --------------------------------------------------------

    if not os.path.exists(
        INPUT_FILE
    ):

        print()
        print(
            "ERROR: Input file not found:"
        )

        print(
            INPUT_FILE
        )

        return


    # --------------------------------------------------------
    # LOAD INPUT
    # --------------------------------------------------------

    with open(
        INPUT_FILE,
        "r",
        newline="",
        encoding="utf-8-sig"
    ) as file:

        reader = csv.DictReader(
            file
        )

        rows = list(reader)


    # --------------------------------------------------------
    # GET DNS ERRORS
    # --------------------------------------------------------

    dns_rows = [

        row

        for row in rows

        if row.get(
            "errorType",
            ""
        ).strip().upper()
        == "DNS_ERROR"

    ]


    print()
    print(
        "DNS error rows:",
        len(dns_rows)
    )


    # --------------------------------------------------------
    # CREATE OUTPUT
    # --------------------------------------------------------

    create_output_file()


    # --------------------------------------------------------
    # RESUME
    # --------------------------------------------------------

    processed = load_processed_ids()


    print(
        "Already processed:",
        len(processed)
    )


    # --------------------------------------------------------
    # PLAYWRIGHT
    # --------------------------------------------------------

    with sync_playwright() as p:

        print()
        print(
            "Launching Chromium..."
        )


        browser = p.chromium.launch(
            headless=HEADLESS
        )


        context = browser.new_context(

            viewport={
                "width": 1366,
                "height": 768
            },

            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/151.0.0.0 Safari/537.36"
            )

        )


        context.set_default_timeout(
            10000
        )


        page = context.new_page()


        # ----------------------------------------------------
        # PROCESS DNS STARTUPS
        # ----------------------------------------------------

        total = len(
            dns_rows
        )


        completed_this_run = 0


        for position, row in enumerate(
            dns_rows,
            start=1
        ):

            startup_id = (
                row.get(
                    "startupId",
                    ""
                ).strip()
            )


            startup_name = (
                row.get(
                    "startupName",
                    ""
                )
                or "Unknown Startup"
            ).strip()


            # ------------------------------------------------
            # RESUME KEY
            # ------------------------------------------------

            if startup_id:

                resume_key = (
                    "ID:" + startup_id
                )

            else:

                resume_key = (
                    "NAME:"
                    + startup_name.lower()
                )


            # ------------------------------------------------
            # SKIP ALREADY PROCESSED
            # ------------------------------------------------

            if resume_key in processed:

                print()

                print(
                    f"[{position}/{total}] "
                    f"SKIPPING — already processed:"
                )

                print(
                    startup_name
                )

                continue


            # ------------------------------------------------
            # START COMPANY
            # ------------------------------------------------

            print()
            print("=" * 75)

            print(
                f"STARTUP {position}/{total}"
            )

            print(
                "Startup:",
                startup_name
            )

            print("=" * 75)


            # ------------------------------------------------
            # SEARCH
            # ------------------------------------------------

            try:

                (
                    candidates,
                    queries_attempted,
                    queries_with_results

                ) = search_company(
                    page,
                    startup_name
                )


            except Exception as e:

                print()
                print(
                    "Unexpected error:"
                )

                print(e)


                candidates = []

                queries_attempted = 0

                queries_with_results = 0


                status = (
                    "SEARCH_ERROR"
                )


            else:

                if candidates:

                    status = (
                        "CANDIDATES_FOUND"
                    )

                else:

                    status = (
                        "NO_CANDIDATES"
                    )


            # ------------------------------------------------
            # DISPLAY RESULTS
            # ------------------------------------------------

            print()
            print(
                "-" * 60
            )

            print(
                "SEARCH RESULT"
            )

            print(
                "-" * 60
            )


            print(
                "Queries attempted:",
                queries_attempted
            )


            print(
                "Queries with results:",
                queries_with_results
            )


            print(
                "Candidates:",
                len(candidates)
            )


            if candidates:

                for number, candidate in enumerate(
                    candidates,
                    start=1
                ):

                    print()

                    print(
                        f"{number}. "
                        f"{candidate['title']}"
                    )

                    print(
                        "   Domain:",
                        candidate["domain"]
                    )

                    print(
                        "   URL:",
                        candidate["url"]
                    )

                    print(
                        "   Query:",
                        candidate["query"]
                    )


            else:

                print()
                print(
                    "No usable candidate found."
                )


            # ------------------------------------------------
            # SAVE IMMEDIATELY
            # ------------------------------------------------

            save_company(

                row,

                candidates,

                queries_attempted,

                queries_with_results,

                status

            )


            completed_this_run += 1


            print()
            print(
                "RESULT SAVED ✓"
            )


            print(
                "Status:",
                status
            )


            print(
                "Progress:",
                f"{position}/{total}"
            )


            # ------------------------------------------------
            # UPDATE PROCESSED SET
            # ------------------------------------------------

            processed.add(
                resume_key
            )


            time.sleep(
                2
            )


        # ----------------------------------------------------
        # CLOSE BROWSER
        # ----------------------------------------------------

        page.close()

        context.close()

        browser.close()


    # ========================================================
    # FINISHED
    # ========================================================

    print()
    print("=" * 75)

    print(
        "DNS WEBSITE SEARCH FINISHED"
    )

    print("=" * 75)

    print()

    print(
        "DNS errors:",
        total
    )

    print(
        "Processed this run:",
        completed_this_run
    )

    print(
        "Already processed:",
        len(processed)
        - completed_this_run
    )

    print()

    print(
        "Candidate file:"
    )

    print(
        OUTPUT_FILE
    )

    print()

    print(
        "IMPORTANT:"
    )

    print(
        "Candidate URLs are NOT verified official websites."
    )

    print(
        "They must be verified before entering the final dataset."
    )

    print("=" * 75)


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    main()