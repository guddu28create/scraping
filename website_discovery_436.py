import csv
import os
import re
import time
from urllib.parse import quote_plus, urlparse, parse_qs, unquote

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


# ============================================================
# SETTINGS
# ============================================================

BASE_FOLDER = r"C:\Users\ASUS\OneDrive\Desktop\Nagpur_Startup_Scraper"

SCRAPLING_RESULTS = os.path.join(
    BASE_FOLDER,
    "Nagpur_Scrapling_451_Recovery.csv"
)

OUTPUT_FILE = os.path.join(
    BASE_FOLDER,
    "Nagpur_436_Website_Discovery.csv"
)

HEADLESS = False

SEARCH_TIMEOUT = 25000
VERIFY_TIMEOUT = 20000

# Wait between searches
SEARCH_DELAY = 4

# Maximum search results considered per query
MAX_RESULTS_PER_QUERY = 8

# ============================================================
# DOMAINS WE DO NOT ACCEPT AS OFFICIAL WEBSITES
# ============================================================

BAD_DOMAINS = {
    "google.com",
    "google.co.in",
    "bing.com",
    "duckduckgo.com",

    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "youtube.com",
    "twitter.com",
    "x.com",

    "tracxn.com",
    "thecompanycheck.com",
    "zaubacorp.com",
    "zauba.com",
    "tofler.in",
    "falconebiz.com",
    "planetexim.net",

    "companydetails.in",
    "companydetails.com",

    "dnb.com",
    "dnb.co.in",

    "indiafilings.com",
    "cleartax.in",

    "crunchbase.com",
    "wikipedia.org",

    "justdial.com",
    "sulekha.com",

    "indiamart.com",
    "tradeindia.com",

    "glassdoor.com",
    "ambitionbox.com",

    "economictimes.indiatimes.com",
    "moneycontrol.com",

    "bseindia.com",
    "nseindia.com",

    "youtube.com",
    "medium.com",

    "linkedin.com",
    "facebook.com",
    "instagram.com"
}


FIELDS = [
    "startupId",
    "startupName",
    "originalWebsite",

    "searchQueries",

    "candidateURLs",
    "candidateScores",

    "verifiedWebsite",

    "emails",
    "phones",
    "linkedin",

    "status",

    "searchEngine",
    "verificationMethod",

    "notes"
]


# ============================================================
# BASIC HELPERS
# ============================================================

def get_value(row, names):

    for name in names:

        if name in row:

            value = (
                row.get(name)
                or ""
            ).strip()

            if value:
                return value

    return ""


def normalize_text(text):

    text = (text or "").lower()

    text = re.sub(
        r"[^a-z0-9 ]",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


def normalize_company(name):

    text = normalize_text(name)

    remove = {
        "private",
        "limited",
        "pvt",
        "ltd",
        "llp",
        "opc",
        "one",
        "person",
        "company",
        "india"
    }

    words = [
        w
        for w in text.split()
        if w not in remove
    ]

    return " ".join(words)


def company_words(name):

    words = normalize_company(name).split()

    return [
        w
        for w in words
        if len(w) >= 4
    ]


def get_domain(url):

    try:

        domain = urlparse(
            url
        ).netloc.lower()

        domain = domain.split("@")[-1]
        domain = domain.split(":")[0]

        if domain.startswith("www."):
            domain = domain[4:]

        return domain

    except:

        return ""


def is_bad_domain(url):

    domain = get_domain(url)

    if not domain:
        return True

    for bad in BAD_DOMAINS:

        if (
            domain == bad
            or domain.endswith("." + bad)
        ):

            return True

    return False


def clean_url(url):

    if not url:
        return ""

    url = url.strip()

    if url.startswith("//"):
        url = "https:" + url

    return url


def decode_search_url(url):

    try:

        parsed = urlparse(url)

        params = parse_qs(
            parsed.query
        )

        if "uddg" in params:
            return unquote(
                params["uddg"][0]
            )

    except:
        pass

    return url


# ============================================================
# CONTACT EXTRACTION
# ============================================================

def clean_email(email):

    if not email:
        return None

    email = email.lower().strip()

    email = email.replace(
        "mailto:",
        "",
        1
    )

    email = email.split("?")[0]

    if "example.com" in email:
        return None

    if "xxxx" in email:
        return None

    if "****" in email:
        return None

    return email


def clean_phone(phone):

    if not phone:
        return None

    digits = re.sub(
        r"\D",
        "",
        phone
    )

    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]

    if len(digits) != 10:
        return None

    if digits[0] not in "6789":
        return None

    return phone.strip()


def extract_contacts(page):

    emails = set()
    phones = set()
    linkedin = set()

    try:

        text = page.locator(
            "body"
        ).inner_text(
            timeout=5000
        )

    except:

        text = ""


    try:

        html = page.content()

    except:

        html = ""


    combined = (
        text
        + "\n"
        + html
    )


    # EMAILS

    matches = re.findall(
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        combined
    )

    for email in matches:

        email = clean_email(email)

        if email:
            emails.add(email)


    # PHONES

    matches = re.findall(
        r"(?:\+91[\s.-]?)?[6-9]\d{9}",
        combined
    )

    for phone in matches:

        phone = clean_phone(phone)

        if phone:
            phones.add(phone)


    # LINKEDIN

    try:

        links = page.locator(
            'a[href*="linkedin.com"]'
        ).evaluate_all(
            "links => links.map(a => a.href)"
        )

        for link in links:

            linkedin.add(link)

    except:

        pass


    return emails, phones, linkedin


# ============================================================
# SEARCH QUERIES
# ============================================================

def make_queries(name):

    return [

        f'"{name}" official website',

        f'"{name}" website',

        f'"{name}" Nagpur website',

        f'"{name}" Maharashtra website',

        f'"{name}" contact',

        f'"{name}" "www"'

    ]


# ============================================================
# SEARCH GOOGLE
# ============================================================

def search_google(page, query):

    print()
    print("GOOGLE SEARCH:")
    print(query)

    url = (
        "https://www.google.com/search?q="
        + quote_plus(query)
    )

    try:

        page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=SEARCH_TIMEOUT
        )

        time.sleep(2)

    except Exception as e:

        print(
            "Google error:",
            str(e)[:200]
        )

        return []


    results = []

    try:

        links = page.locator(
            "a"
        ).evaluate_all(
            """
            links => links.map(a => ({
                text: (a.innerText || "").trim(),
                href: a.href
            }))
            """
        )

    except:

        links = []


    for item in links:

        title = (
            item.get("text")
            or ""
        ).strip()

        href = (
            item.get("href")
            or ""
        ).strip()


        if not href.startswith("http"):
            continue

        href = clean_url(href)

        if is_bad_domain(href):
            continue

        if href not in [
            x["url"]
            for x in results
        ]:

            results.append({
                "title": title,
                "url": href
            })


        if len(results) >= MAX_RESULTS_PER_QUERY:
            break


    return results


# ============================================================
# SEARCH BING
# ============================================================

def search_bing(page, query):

    print()
    print("BING SEARCH:")
    print(query)

    url = (
        "https://www.bing.com/search?q="
        + quote_plus(query)
    )

    try:

        page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=SEARCH_TIMEOUT
        )

        time.sleep(2)

    except Exception as e:

        print(
            "Bing error:",
            str(e)[:200]
        )

        return []


    results = []

    try:

        links = page.locator(
            "li.b_algo h2 a"
        ).evaluate_all(
            """
            links => links.map(a => ({
                text: (a.innerText || "").trim(),
                href: a.href
            }))
            """
        )

    except:

        links = []


    for item in links:

        title = (
            item.get("text")
            or ""
        ).strip()

        href = (
            item.get("href")
            or ""
        ).strip()


        if not href.startswith("http"):
            continue

        if is_bad_domain(href):
            continue

        results.append({
            "title": title,
            "url": href
        })


    return results[:MAX_RESULTS_PER_QUERY]


# ============================================================
# SCORE CANDIDATE
# ============================================================

def score_candidate(
    startup_name,
    title,
    url
):

    score = 0

    words = company_words(
        startup_name
    )

    title_text = normalize_text(
        title
    )

    domain = normalize_text(
        get_domain(url)
    )


    # Company words in title

    for word in words:

        if word in title_text:
            score += 3


    # Company words in domain

    for word in words:

        if len(word) >= 5:

            if word in domain:

                score += 5


    # Generic website TLDs

    if (
        domain.endswith(".com")
        or domain.endswith(".in")
        or domain.endswith(".co.in")
        or domain.endswith(".org")
    ):

        score += 1


    # Penalize obvious directories

    if any(
        x in domain
        for x in [
            "directory",
            "listing",
            "business"
        ]
    ):

        score -= 3


    return score


# ============================================================
# VERIFY WEBSITE
# ============================================================

def verify_candidate(
    context,
    startup_name,
    candidate
):

    url = candidate["url"]

    if is_bad_domain(url):
        return None


    page = None


    try:

        page = context.new_page()

        response = page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=VERIFY_TIMEOUT
        )


        if not response:
            return None


        if response.status >= 400:
            return None


        time.sleep(1)


        final_url = page.url

        if is_bad_domain(final_url):
            return None


        try:
            title = page.title()
        except:
            title = ""


        try:

            body = page.locator(
                "body"
            ).inner_text(
                timeout=5000
            )

        except:

            body = ""


        combined = (
            title
            + " "
            + body[:30000]
        ).lower()


        words = company_words(
            startup_name
        )


        matches = 0

        for word in words:

            if word in combined:
                matches += 1


        domain = get_domain(
            final_url
        )

        domain_root = domain.split(
            "."
        )[0]


        domain_match = False

        for word in words:

            if len(word) >= 5:

                if word in domain_root:

                    domain_match = True
                    break


        # ----------------------------------------------------
        # Verification threshold
        # ----------------------------------------------------

        if not (
            domain_match
            or matches >= 2
        ):

            print(
                "Rejected — weak company match:"
            )

            print(
                final_url
            )

            return None


        emails, phones, linkedin = (
            extract_contacts(page)
        )


        print()
        print(
            "VERIFIED WEBSITE ✓"
        )

        print(
            final_url
        )


        return {
            "url": final_url,
            "emails": emails,
            "phones": phones,
            "linkedin": linkedin
        }


    except PlaywrightTimeoutError:

        print(
            "Candidate timed out."
        )

        return None


    except Exception as e:

        print(
            "Candidate failed:",
            str(e)[:200]
        )

        return None


    finally:

        if page:

            try:
                page.close()
            except:
                pass


# ============================================================
# SAVE
# ============================================================

def save_row(row):

    exists = os.path.exists(
        OUTPUT_FILE
    )

    with open(
        OUTPUT_FILE,
        "a",
        newline="",
        encoding="utf-8-sig"
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=FIELDS
        )

        if not exists:
            writer.writeheader()

        writer.writerow(row)

        f.flush()


# ============================================================
# LOAD CHECKPOINT
# ============================================================

def load_completed():

    completed = set()

    if not os.path.exists(
        OUTPUT_FILE
    ):
        return completed


    with open(
        OUTPUT_FILE,
        "r",
        newline="",
        encoding="utf-8-sig"
    ) as f:

        reader = csv.DictReader(f)

        for row in reader:

            name = (
                row.get(
                    "startupName",
                    ""
                )
                or ""
            ).strip().lower()

            if name:
                completed.add(name)


    return completed


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 75)
    print("WEBSITE DISCOVERY — DNS UNRESOLVED COMPANIES")
    print("=" * 75)


    # --------------------------------------------------------
    # READ SCRAPLING RESULTS
    # --------------------------------------------------------

    if not os.path.exists(
        SCRAPLING_RESULTS
    ):

        print()
        print(
            "Scrapling result file not found:"
        )

        print(
            SCRAPLING_RESULTS
        )

        return


    with open(
        SCRAPLING_RESULTS,
        "r",
        newline="",
        encoding="utf-8-sig"
    ) as f:

        rows = list(
            csv.DictReader(f)
        )


    # --------------------------------------------------------
    # ONLY DNS UNRESOLVED
    # --------------------------------------------------------

    targets = []

    for row in rows:

        error = (
            row.get(
                "errorType",
                ""
            )
            or ""
        ).upper().strip()


        if error == "DNS_UNRESOLVED":

            targets.append(row)


    print()
    print(
        "DNS-UNRESOLVED COMPANIES:",
        len(targets)
    )


    # --------------------------------------------------------
    # RESUME
    # --------------------------------------------------------

    completed = load_completed()

    print(
        "Already processed:",
        len(completed)
    )


    # --------------------------------------------------------
    # PLAYWRIGHT
    # --------------------------------------------------------

    with sync_playwright() as p:

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

        context.set_default_navigation_timeout(
            VERIFY_TIMEOUT
        )


        search_page = context.new_page()


        # ====================================================
        # PROCESS
        # ====================================================

        for number, row in enumerate(
            targets,
            start=1
        ):

            startup_name = get_value(
                row,
                [
                    "startupName",
                    "Startup Name",
                    "name"
                ]
            )


            if not startup_name:
                continue


            # ------------------------------------------------
            # CHECKPOINT
            # ------------------------------------------------

            if startup_name.lower() in completed:

                print()
                print(
                    f"[{number}/{len(targets)}] "
                    "ALREADY DONE — SKIPPING"
                )

                print(
                    startup_name
                )

                continue


            original_website = (
                get_value(
                    row,
                    [
                        "originalWebsite",
                        "originalWebsite"
                    ]
                )
            )


            print()
            print("=" * 75)

            print(
                f"COMPANY {number}/{len(targets)}"
            )

            print(
                "Startup:",
                startup_name
            )

            print("=" * 75)


            # ------------------------------------------------
            # SEARCH
            # ------------------------------------------------

            queries = make_queries(
                startup_name
            )


            candidates = []


            # Use Google first, then Bing.
            # If Google starts showing CAPTCHA,
            # Bing can still be used.

            for engine_name, search_function in [
                ("Google", search_google),
                ("Bing", search_bing)
            ]:


                for query in queries[:4]:

                    results = search_function(
                        search_page,
                        query
                    )


                    for result in results:

                        url = result["url"]

                        if is_bad_domain(url):
                            continue


                        existing = None

                        for c in candidates:

                            if get_domain(
                                c["url"]
                            ) == get_domain(url):

                                existing = c
                                break


                        score = score_candidate(
                            startup_name,
                            result["title"],
                            url
                        )


                        if existing:

                            if score > existing["score"]:
                                existing["score"] = score

                        else:

                            candidates.append({

                                "title":
                                    result["title"],

                                "url":
                                    url,

                                "score":
                                    score,

                                "engine":
                                    engine_name

                            })


                    time.sleep(
                        SEARCH_DELAY
                    )


                # If we have good candidates,
                # don't hammer the search engines.

                good_candidates = [
                    c for c in candidates
                    if c["score"] >= 5
                ]


                if good_candidates:
                    break


            # ------------------------------------------------
            # SORT
            # ------------------------------------------------

            candidates.sort(
                key=lambda x: x["score"],
                reverse=True
            )


            # Keep top 15

            candidates = candidates[:15]


            print()
            print(
                "CANDIDATES FOUND:",
                len(candidates)
            )


            for i, c in enumerate(
                candidates,
                start=1
            ):

                print(
                    f"{i}. "
                    f"[{c['score']}] "
                    f"{c['url']}"
                )


            candidate_urls = " | ".join(
                c["url"]
                for c in candidates
            )


            candidate_scores = " | ".join(
                f"{c['url']}={c['score']}"
                for c in candidates
            )


            # ------------------------------------------------
            # VERIFY
            # ------------------------------------------------

            verified = None

            for candidate in candidates:

                # Only verify reasonably strong candidates

                if candidate["score"] < 3:
                    continue


                print()
                print(
                    "Trying candidate:"
                )

                print(
                    candidate["url"]
                )


                verified = verify_candidate(
                    context,
                    startup_name,
                    candidate
                )


                if verified:
                    break


            # ------------------------------------------------
            # SAVE
            # ------------------------------------------------

            if verified:

                save_row({

                    "startupId":
                        get_value(
                            row,
                            [
                                "startupId",
                                "Startup ID",
                                "id"
                            ]
                        ),

                    "startupName":
                        startup_name,

                    "originalWebsite":
                        original_website,

                    "searchQueries":
                        " | ".join(
                            queries[:4]
                        ),

                    "candidateURLs":
                        candidate_urls,

                    "candidateScores":
                        candidate_scores,

                    "verifiedWebsite":
                        verified["url"],

                    "emails":
                        ", ".join(
                            sorted(
                                verified["emails"]
                            )
                        ),

                    "phones":
                        ", ".join(
                            sorted(
                                verified["phones"]
                            )
                        ),

                    "linkedin":
                        ", ".join(
                            sorted(
                                verified["linkedin"]
                            )
                        ),

                    "status":
                        "VERIFIED",

                    "searchEngine":
                        "Google/Bing",

                    "verificationMethod":
                        "Live website verification",

                    "notes":
                        "Website discovered through web search and verified against company name"

                })


                print()
                print(
                    "✓ VERIFIED WEBSITE"
                )


            else:

                save_row({

                    "startupId":
                        get_value(
                            row,
                            [
                                "startupId",
                                "Startup ID",
                                "id"
                            ]
                        ),

                    "startupName":
                        startup_name,

                    "originalWebsite":
                        original_website,

                    "searchQueries":
                        " | ".join(
                            queries[:4]
                        ),

                    "candidateURLs":
                        candidate_urls,

                    "candidateScores":
                        candidate_scores,

                    "verifiedWebsite":
                        "",

                    "emails":
                        "",

                    "phones":
                        "",

                    "linkedin":
                        "",

                    "status":
                        "NO_CONFIDENT_WEBSITE",

                    "searchEngine":
                        "Google/Bing",

                    "verificationMethod":
                        "",

                    "notes":
                        "Search candidates were not strong enough to confidently identify the official website"

                })


                print()
                print(
                    "NO CONFIDENT WEBSITE FOUND"
                )


            completed.add(
                startup_name.lower()
            )


            print()
            print(
                "CHECKPOINT SAVED ✓"
            )


            time.sleep(2)


        # ----------------------------------------------------
        # CLOSE
        # ----------------------------------------------------

        search_page.close()
        context.close()
        browser.close()


    print()
    print("=" * 75)
    print("WEBSITE DISCOVERY FINISHED")
    print("=" * 75)

    print()
    print(
        "Output:"
    )

    print(
        OUTPUT_FILE
    )


if __name__ == "__main__":
    main()