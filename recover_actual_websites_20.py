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
    "Nagpur_20_Web_Search_Recovery.csv"
)

OUTPUT_FILE = os.path.join(
    BASE_FOLDER,
    "Nagpur_20_Actual_Websites.csv"
)

HEADLESS = False

NAVIGATION_TIMEOUT = 25000
DEFAULT_TIMEOUT = 10000


# ============================================================
# DOMAINS THAT ARE NOT COMPANY WEBSITES
# ============================================================

BAD_DOMAINS = {
    "google.com",
    "google.co.in",

    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "youtube.com",
    "twitter.com",
    "x.com",

    "thecompanycheck.com",
    "zaubacorp.com",
    "tracxn.com",
    "tofler.in",
    "falconebiz.com",
    "planetexim.net",
    "zauba.co.in",

    "companydetails.in",
    "companydetails.com",

    "dnb.com",
    "indiafilings.com",
    "economictimes.indiatimes.com",
    "maharashtradirectory.com",

    "justdial.com",
    "sulekha.com",

    "crunchbase.com",
    "wikipedia.org",

    "instafinancials.com",
    "bseindia.com",
    "moneycontrol.com",
    "zauba.com",

    "indiamart.com",
    "tradeindia.com",
}


# ============================================================
# OUTPUT
# ============================================================

FIELDS = [
    "startupId",
    "startupName",
    "referenceURLs",
    "candidateURLs",
    "officialWebsite",
    "status",
    "searchQueries",
    "emails",
    "phones",
    "linkedin",
    "pagesChecked",
    "notes"
]


# ============================================================
# HELPERS
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


def clean_email(email):

    if not email:
        return None

    email = email.strip().lower()

    if email.startswith("mailto:"):
        email = email[7:]

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


def domain_of(url):

    try:

        domain = urlparse(
            url
        ).netloc.lower()

        return domain.replace(
            "www.",
            ""
        )

    except Exception:

        return ""


def is_bad_domain(url):

    domain = domain_of(url)

    if not domain:
        return True

    for bad in BAD_DOMAINS:

        if (
            domain == bad
            or domain.endswith("." + bad)
        ):
            return True

    return False


def decode_ddg_url(url):

    try:

        parsed = urlparse(url)

        query = parse_qs(
            parsed.query
        )

        if "uddg" in query:

            return unquote(
                query["uddg"][0]
            )

    except Exception:

        pass

    return url


# ============================================================
# COMPANY NAME WORDS
# ============================================================

def important_words(name):

    words = re.findall(
        r"[a-z0-9]+",
        name.lower()
    )

    ignore = {
        "private",
        "limited",
        "pvt",
        "ltd",
        "llp",
        "india",
        "company",
        "services",
        "solutions",
        "technologies",
        "technology",
        "enterprise",
        "enterprises",
        "institute",
        "global",
    }

    return [
        x
        for x in words
        if len(x) >= 4
        and x not in ignore
    ]


# ============================================================
# SEARCH
# ============================================================

def search_ddg(page, query):

    print()
    print("SEARCH:")
    print(query)

    url = (
        "https://html.duckduckgo.com/html/?q="
        + quote_plus(query)
    )

    try:

        page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=NAVIGATION_TIMEOUT
        )

        time.sleep(1.5)

    except Exception as e:

        print(
            "Search failed:",
            e
        )

        return []


    results = []

    try:

        links = page.locator(
            "a.result__a"
        ).evaluate_all(
            """
            links => links.map(a => ({
                text: a.innerText,
                href: a.href
            }))
            """
        )

    except Exception:

        links = []


    for item in links:

        href = (
            item.get("href")
            or ""
        ).strip()

        title = (
            item.get("text")
            or ""
        ).strip()


        href = decode_ddg_url(
            href
        )


        if not href.startswith(
            "http"
        ):
            continue


        if is_bad_domain(
            href
        ):
            continue


        if href not in [
            x[1] for x in results
        ]:

            results.append(
                (
                    title,
                    href
                )
            )


    return results


# ============================================================
# EXTRACT CONTACT DATA
# ============================================================

def extract_contact_data(page):

    emails = set()
    phones = set()
    linkedin = set()


    try:

        text = page.locator(
            "body"
        ).inner_text(
            timeout=5000
        )

    except Exception:

        text = ""


    try:

        html = page.content()

    except Exception:

        html = ""


    combined = (
        text
        + "\n"
        + html
    )


    # EMAIL

    matches = re.findall(
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        combined
    )

    for email in matches:

        email = clean_email(
            email
        )

        if email:
            emails.add(email)


    # PHONE

    matches = re.findall(
        r"(?:\+91[\s.-]?)?[6-9]\d{9}",
        combined
    )

    for phone in matches:

        phone = clean_phone(
            phone
        )

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

            linkedin.add(
                link
            )

    except Exception:

        pass


    return (
        emails,
        phones,
        linkedin
    )


# ============================================================
# FIND CONTACT / ABOUT
# ============================================================

def find_contact_pages(page):

    urls = set()

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

    except Exception:

        return []


    base_domain = domain_of(
        page.url
    )


    keywords = [
        "contact",
        "contact us",
        "contact-us",
        "about",
        "about us",
        "about-us"
    ]


    for link in links:

        text = (
            link.get("text")
            or ""
        ).lower()

        href = (
            link.get("href")
            or ""
        ).strip()


        if not href.startswith(
            "http"
        ):
            continue


        if domain_of(href) != base_domain:
            continue


        href_lower = href.lower()


        if any(
            k in text
            or k in href_lower
            for k in keywords
        ):

            urls.add(
                href
            )


    return list(urls)[:3]


# ============================================================
# VERIFY
# ============================================================

def verify_website(
    context,
    candidate,
    startup_name
):

    if is_bad_domain(
        candidate
    ):
        return None


    page = None


    try:

        print()
        print(
            "TESTING CANDIDATE:"
        )

        print(
            candidate
        )


        page = context.new_page()


        response = page.goto(
            candidate,
            wait_until="domcontentloaded",
            timeout=NAVIGATION_TIMEOUT
        )


        if not response:
            return None


        if response.status >= 400:

            print(
                "HTTP error:",
                response.status
            )

            return None


        time.sleep(1)


        title = ""

        try:
            title = page.title()
        except:
            pass


        try:

            body = page.locator(
                "body"
            ).inner_text(
                timeout=5000
            )

        except:

            body = ""


        text = (
            title
            + " "
            + body[:20000]
        ).lower()


        words = important_words(
            startup_name
        )


        matches = 0

        for word in words:

            if word in text:

                matches += 1


        domain = domain_of(
            candidate
        )

        domain_root = (
            domain.split(".")[0]
        )


        domain_match = False

        for word in words:

            if len(word) >= 5:

                if word in domain_root:

                    domain_match = True

                    break


        emails, phones, linkedin = (
            extract_contact_data(page)
        )


        pages_checked = 1


        # ----------------------------------------------------
        # Contact/about pages
        # ----------------------------------------------------

        contact_pages = (
            find_contact_pages(page)
        )


        for contact_url in contact_pages:

            try:

                cp = context.new_page()

                cp.goto(
                    contact_url,
                    wait_until="domcontentloaded",
                    timeout=15000
                )

                time.sleep(0.7)

                pages_checked += 1


                e, p, l = (
                    extract_contact_data(cp)
                )


                emails.update(e)
                phones.update(p)
                linkedin.update(l)


                cp.close()

            except:

                pass


        # ----------------------------------------------------
        # Verification
        # ----------------------------------------------------

        if (
            matches >= 2
            or (
                matches >= 1
                and domain_match
            )
            or domain_match
        ):

            print(
                "✓ POSSIBLE OFFICIAL WEBSITE"
            )

            return {
                "url": candidate,
                "emails": emails,
                "phones": phones,
                "linkedin": linkedin,
                "pagesChecked": pages_checked
            }


        print(
            "Rejected — weak company match"
        )

        return None


    except PlaywrightTimeoutError:

        print(
            "Timeout"
        )

        return None


    except Exception as e:

        print(
            "Error:",
            e
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

def save_row(data):

    file_exists = os.path.exists(
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


        if not file_exists:

            writer.writeheader()


        writer.writerow(
            data
        )


# ============================================================
# LOAD PROCESSED
# ============================================================

def load_processed():

    processed = set()


    if not os.path.exists(
        OUTPUT_FILE
    ):

        return processed


    with open(
        OUTPUT_FILE,
        "r",
        newline="",
        encoding="utf-8-sig"
    ) as f:

        reader = csv.DictReader(
            f
        )


        for row in reader:

            name = (
                row.get(
                    "startupName",
                    ""
                )
                or ""
            ).strip().lower()


            if name:

                processed.add(
                    name
                )


    return processed


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 75)
    print(
        "RECOVER ACTUAL OFFICIAL WEBSITES"
    )
    print("=" * 75)


    if not os.path.exists(
        INPUT_FILE
    ):

        print(
            "ERROR: Input file not found:"
        )

        print(
            INPUT_FILE
        )

        return


    # --------------------------------------------------------
    # Read input
    # --------------------------------------------------------

    with open(
        INPUT_FILE,
        "r",
        newline="",
        encoding="utf-8-sig"
    ) as f:

        rows = list(
            csv.DictReader(f)
        )


    processed = load_processed()


    print()
    print(
        "Total companies:",
        len(rows)
    )

    print(
        "Already processed:",
        len(processed)
    )


    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=HEADLESS
        )


        context = browser.new_context(
            ignore_https_errors=True,

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
            DEFAULT_TIMEOUT
        )

        context.set_default_navigation_timeout(
            NAVIGATION_TIMEOUT
        )


        search_page = context.new_page()


        for number, row in enumerate(
            rows,
            start=1
        ):

            startup_name = get_value(
                row,
                [
                    "startupName",
                    "Startup Name",
                    "name",
                    "Name"
                ]
            )


            if not startup_name:

                continue


            # ------------------------------------------------
            # RESUME
            # ------------------------------------------------

            if startup_name.lower() in processed:

                print()
                print(
                    f"[{number}/{len(rows)}] "
                    "SKIPPING — already processed"
                )

                print(
                    startup_name
                )

                continue


            print()
            print("=" * 75)

            print(
                f"COMPANY {number}/{len(rows)}"
            )

            print(
                "Startup:",
                startup_name
            )

            print("=" * 75)


            # ------------------------------------------------
            # Existing reference URLs
            # ------------------------------------------------

            reference_urls = []


            old_candidates = get_value(
                row,
                [
                    "candidateURLs"
                ]
            )


            if old_candidates:

                for url in old_candidates.split(
                    " | "
                ):

                    if url:

                        reference_urls.append(
                            url
                        )


            # ------------------------------------------------
            # Multiple targeted searches
            # ------------------------------------------------

            queries = [

                f'"{startup_name}" "official website"',

                f'"{startup_name}" website',

                f'"{startup_name}" Nagpur website',

                f'"{startup_name}" Maharashtra website',

                f'"{startup_name}" contact',

                f'"{startup_name}" "www."',

                f'"{startup_name}" "https://"'

            ]


            candidates = []


            for query in queries:

                results = search_ddg(
                    search_page,
                    query
                )


                for title, url in results:

                    if url not in candidates:

                        candidates.append(
                            url
                        )


                if len(candidates) >= 20:

                    break


                time.sleep(1)


            print()
            print(
                "Candidate websites:",
                len(candidates)
            )


            for i, url in enumerate(
                candidates,
                start=1
            ):

                print(
                    f"{i}. {url}"
                )


            # ------------------------------------------------
            # Verify
            # ------------------------------------------------

            verified = None


            for candidate in candidates:

                verified = verify_website(
                    context,
                    candidate,
                    startup_name
                )


                if verified:

                    break


            # ------------------------------------------------
            # Save
            # ------------------------------------------------

            if verified:

                save_row({

                    "startupId":
                        get_value(
                            row,
                            ["startupId"]
                        ),

                    "startupName":
                        startup_name,

                    "referenceURLs":
                        " | ".join(
                            reference_urls
                        ),

                    "candidateURLs":
                        " | ".join(
                            candidates
                        ),

                    "officialWebsite":
                        verified["url"],

                    "status":
                        "OFFICIAL_WEBSITE_FOUND",

                    "searchQueries":
                        " | ".join(
                            queries
                        ),

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

                    "pagesChecked":
                        verified["pagesChecked"],

                    "notes":
                        "Website found through targeted web search"

                })


                print()
                print(
                    "✓ RESULT SAVED"
                )

                print(
                    "Official website:",
                    verified["url"]
                )


            else:

                save_row({

                    "startupId":
                        get_value(
                            row,
                            ["startupId"]
                        ),

                    "startupName":
                        startup_name,

                    "referenceURLs":
                        " | ".join(
                            reference_urls
                        ),

                    "candidateURLs":
                        " | ".join(
                            candidates
                        ),

                    "officialWebsite":
                        "",

                    "status":
                        "NO_OFFICIAL_WEBSITE_FOUND",

                    "searchQueries":
                        " | ".join(
                            queries
                        ),

                    "emails":
                        "",

                    "phones":
                        "",

                    "linkedin":
                        "",

                    "pagesChecked":
                        0,

                    "notes":
                        "Search completed but no official website could be confidently verified"

                })


                print()
                print(
                    "NO OFFICIAL WEBSITE FOUND"
                )


            # ------------------------------------------------
            # CHECKPOINT
            # ------------------------------------------------

            processed.add(
                startup_name.lower()
            )


            print()
            print(
                "CHECKPOINT SAVED ✓"
            )


            time.sleep(1)


        search_page.close()

        context.close()

        browser.close()


    print()
    print("=" * 75)

    print(
        "PROCESS COMPLETE"
    )

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