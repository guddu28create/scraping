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
    "Nagpur_SSL_HTTP_Recovery.csv"
)

OUTPUT_FILE = os.path.join(
    BASE_FOLDER,
    "Nagpur_20_Web_Search_Recovery.csv"
)

HEADLESS = False

NAVIGATION_TIMEOUT = 25000

PAGE_TIMEOUT = 10000


# ============================================================
# OUTPUT COLUMNS
# ============================================================

OUTPUT_FIELDS = [
    "startupId",
    "startupName",
    "originalWebsite",
    "originalErrorType",

    "status",

    "candidateURLs",

    "verifiedWebsite",

    "searchQueries",

    "verifiedMethod",

    "emails",
    "phones",
    "linkedin",

    "pagesChecked",

    "errorMessage"
]


# ============================================================
# CLEANING
# ============================================================

def clean_email(email):

    if not email:
        return None

    email = email.strip().lower()

    if email.startswith("mailto:"):
        email = email[7:]

    email = email.split("?")[0].strip()

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

    phone = phone.strip()

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

    return phone


# ============================================================
# CSV HELPERS
# ============================================================

def get_value(row, columns):

    for column in columns:

        if column in row:

            value = (
                row.get(column)
                or ""
            ).strip()

            if value:
                return value

    return ""


def get_startup_id(row):

    return get_value(
        row,
        [
            "startupId",
            "Startup ID",
            "startupID",
            "id",
            "ID"
        ]
    )


def get_startup_name(row):

    return get_value(
        row,
        [
            "startupName",
            "Startup Name",
            "startup",
            "name",
            "Name"
        ]
    ) or "Unknown Startup"


def get_original_website(row):

    return get_value(
        row,
        [
            "originalWebsite",
            "originalWeb",
            "website",
            "Website",
            "Website URL",
            "websiteUrl",
            "url"
        ]
    )


# ============================================================
# EXTRACT CONTACT DATA
# ============================================================

def extract_data(page):

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


    combined = text + "\n" + html


    # --------------------------------------------------------
    # EMAIL
    # --------------------------------------------------------

    email_matches = re.findall(
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        combined
    )

    for email in email_matches:

        email = clean_email(email)

        if email:
            emails.add(email)


    # --------------------------------------------------------
    # MAILTO
    # --------------------------------------------------------

    try:

        links = page.locator(
            'a[href^="mailto:"]'
        ).evaluate_all(
            "links => links.map(a => a.href)"
        )

        for link in links:

            email = clean_email(link)

            if email:
                emails.add(email)

    except Exception:

        pass


    # --------------------------------------------------------
    # PHONE
    # --------------------------------------------------------

    phone_matches = re.findall(
        r"(?:\+91[\s.-]?)?[6-9]\d{9}",
        combined
    )

    for phone in phone_matches:

        phone = clean_phone(phone)

        if phone:
            phones.add(phone)


    # --------------------------------------------------------
    # TEL
    # --------------------------------------------------------

    try:

        links = page.locator(
            'a[href^="tel:"]'
        ).evaluate_all(
            "links => links.map(a => a.href)"
        )

        for link in links:

            phone = link.replace(
                "tel:",
                ""
            )

            phone = clean_phone(phone)

            if phone:
                phones.add(phone)

    except Exception:

        pass


    # --------------------------------------------------------
    # LINKEDIN
    # --------------------------------------------------------

    try:

        links = page.locator(
            'a[href*="linkedin.com"]'
        ).evaluate_all(
            "links => links.map(a => a.href)"
        )

        for link in links:

            if "linkedin.com" in link.lower():

                linkedin.add(link)

    except Exception:

        pass


    return (
        emails,
        phones,
        linkedin
    )


# ============================================================
# FIND CONTACT / ABOUT PAGES
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


    base_domain = urlparse(
        page.url
    ).netloc.lower()


    keywords = [
        "contact",
        "contact us",
        "contact-us",
        "about",
        "about us",
        "about-us",
        "reach us",
        "reach-us"
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


        if not href:
            continue

        if href.startswith("mailto:"):
            continue

        if href.startswith("tel:"):
            continue


        if not href.startswith("http"):

            continue


        try:

            domain = urlparse(
                href
            ).netloc.lower()

        except Exception:

            continue


        if domain != base_domain:
            continue


        href_lower = href.lower()


        if any(
            keyword in text
            or keyword in href_lower
            for keyword in keywords
        ):

            urls.add(href)


    return list(urls)[:3]


# ============================================================
# DOMAIN FILTER
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
    "indiamart.com",
    "tradeindia.com",

    "justdial.com",
    "sulekha.com",

    "crunchbase.com",

    "wikipedia.org"
}


def is_bad_domain(url):

    try:

        domain = urlparse(
            url
        ).netloc.lower()

        domain = domain.replace(
            "www.",
            ""
        )

        for bad in BAD_DOMAINS:

            if (
                domain == bad
                or domain.endswith(
                    "." + bad
                )
            ):

                return True

    except Exception:

        return True


    return False


# ============================================================
# DECODE DUCKDUCKGO RESULT
# ============================================================

def decode_ddg_url(href):

    if not href:
        return None

    try:

        parsed = urlparse(
            href
        )

        query = parse_qs(
            parsed.query
        )

        if "uddg" in query:

            return unquote(
                query["uddg"][0]
            )

    except Exception:

        pass

    return href


# ============================================================
# SEARCH DUCKDUCKGO
# ============================================================

def search_duckduckgo(
    page,
    query
):

    print()
    print(
        "Searching:"
    )

    print(
        query
    )


    search_url = (
        "https://html.duckduckgo.com/html/?q="
        + quote_plus(query)
    )


    try:

        page.goto(
            search_url,
            wait_until="domcontentloaded",
            timeout=NAVIGATION_TIMEOUT
        )

        time.sleep(1.5)

    except Exception as e:

        print(
            "Search error:",
            e
        )

        return []


    results = []


    try:

        links = page.locator(
            "a.result__a"
        ).evaluate_all(
            "links => links.map(a => ({text: a.innerText, href: a.href}))"
        )

    except Exception:

        links = []


    for link in links:

        href = (
            link.get("href")
            or ""
        ).strip()


        title = (
            link.get("text")
            or ""
        ).strip()


        href = decode_ddg_url(
            href
        )


        if not href:
            continue


        if not href.startswith(
            "http"
        ):
            continue


        if is_bad_domain(
            href
        ):

            continue


        results.append(
            (
                title,
                href
            )
        )


    return results


# ============================================================
# EXTRACT DOMAIN
# ============================================================

def get_domain(url):

    try:

        domain = urlparse(
            url
        ).netloc.lower()

        domain = domain.replace(
            "www.",
            ""
        )

        return domain

    except Exception:

        return ""


# ============================================================
# VERIFY WEBSITE
# ============================================================

def verify_candidate(
    context,
    candidate,
    startup_name
):

    if is_bad_domain(
        candidate
    ):

        return None


    try:

        parsed = urlparse(
            candidate
        )

        domain = parsed.netloc.lower()

        if not domain:
            return None

    except Exception:

        return None


    page = None


    try:

        print()
        print(
            "VERIFYING:"
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


        status = response.status


        print(
            "HTTP:",
            status
        )


        if status >= 400:

            print(
                "Rejected — HTTP error"
            )

            return None


        time.sleep(1)


        title = ""

        try:
            title = page.title()
        except:
            pass


        body_text = ""

        try:

            body_text = page.locator(
                "body"
            ).inner_text(
                timeout=5000
            )

        except:

            pass


        combined = (
            startup_name.lower()
            + " "
            + title.lower()
            + " "
            + body_text[:15000].lower()
        )


        # ----------------------------------------------------
        # Company-name matching
        # ----------------------------------------------------

        name_words = re.findall(
            r"[a-z0-9]+",
            startup_name.lower()
        )


        important_words = [

            word

            for word in name_words

            if len(word) >= 4

            and word not in {
                "private",
                "limited",
                "llp",
                "pvt",
                "ltd",
                "company",
                "india"
            }

        ]


        matches = 0


        for word in important_words:

            if word in combined:

                matches += 1


        # ----------------------------------------------------
        # Contact data
        # ----------------------------------------------------

        (
            emails,
            phones,
            linkedin
        ) = extract_data(page)


        # ----------------------------------------------------
        # Contact/About
        # ----------------------------------------------------

        contact_urls = (
            find_contact_pages(page)
        )


        pages_checked = 1


        for contact_url in contact_urls:

            try:

                contact_page = (
                    context.new_page()
                )


                contact_page.goto(
                    contact_url,
                    wait_until="domcontentloaded",
                    timeout=NAVIGATION_TIMEOUT
                )


                pages_checked += 1


                time.sleep(0.8)


                (
                    p_emails,
                    p_phones,
                    p_linkedin
                ) = extract_data(
                    contact_page
                )


                emails.update(
                    p_emails
                )

                phones.update(
                    p_phones
                )

                linkedin.update(
                    p_linkedin
                )


                contact_page.close()


            except Exception:

                pass


        # ----------------------------------------------------
        # Verification logic
        # ----------------------------------------------------

        domain_name = domain.split(".")[0]


        domain_match = False


        for word in important_words:

            if len(word) >= 5:

                if word in domain_name:

                    domain_match = True

                    break


        # Strong verification:
        # company name appears on site
        # OR domain strongly resembles company name
        # OR contact information matches company context
        #
        # We deliberately don't automatically accept every
        # search result.

        if (
            matches >= 1
            or domain_match
        ):

            print(
                "VERIFIED ✓"
            )

            print(
                "Title:",
                title
            )

            print(
                "Domain:",
                domain
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
            "Verification timeout"
        )

        return None


    except Exception as e:

        print(
            "Verification error:",
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
# SAVE RESULT
# ============================================================

def save_result(
    row,
    status,
    candidate_urls,
    verified_website,
    queries,
    verified_method,
    emails,
    phones,
    linkedin,
    pages_checked,
    error_message
):

    output = {

        "startupId":
            get_startup_id(row),

        "startupName":
            get_startup_name(row),

        "originalWebsite":
            get_original_website(row),

        "originalErrorType":
            row.get(
                "originalErrorType",
                ""
            ),

        "status":
            status,

        "candidateURLs":
            " | ".join(
                candidate_urls
            ),

        "verifiedWebsite":
            verified_website,

        "searchQueries":
            " | ".join(
                queries
            ),

        "verifiedMethod":
            verified_method,

        "emails":
            ", ".join(
                sorted(emails)
            ),

        "phones":
            ", ".join(
                sorted(phones)
            ),

        "linkedin":
            ", ".join(
                sorted(linkedin)
            ),

        "pagesChecked":
            pages_checked,

        "errorMessage":
            error_message
    }


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
            output
        )


# ============================================================
# CREATE OUTPUT
# ============================================================

def create_output():

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
                or ""
            ).strip()


            startup_name = (
                row.get(
                    "startupName",
                    ""
                )
                or ""
            ).strip().lower()


            if startup_id:

                processed.add(
                    "ID:" + startup_id
                )

            elif startup_name:

                processed.add(
                    "NAME:" + startup_name
                )


    return processed


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 75)
    print(
        "WEB SEARCH RECOVERY — 20 FAILED WEBSITES"
    )
    print("=" * 75)


    # --------------------------------------------------------
    # Check input
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
    # Read CSV
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

        all_rows = list(
            reader
        )


    # --------------------------------------------------------
    # ONLY NEEDS_WEB_SEARCH
    # --------------------------------------------------------

    rows = [

        row

        for row in all_rows

        if row.get(
            "status",
            ""
        ).strip().upper()
        == "NEEDS_WEB_SEARCH"

    ]


    print()
    print(
        "Companies needing web search:",
        len(rows)
    )


    if not rows:

        print(
            "No companies need web search."
        )

        return


    create_output()


    processed = load_processed()


    print(
        "Already processed:",
        len(processed)
    )


    # ========================================================
    # PLAYWRIGHT
    # ========================================================

    with sync_playwright() as p:

        print()
        print(
            "Launching Chromium..."
        )


        browser = p.chromium.launch(
            headless=HEADLESS
        )


        # Ignore certificate problems during verification
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
            PAGE_TIMEOUT
        )


        context.set_default_navigation_timeout(
            NAVIGATION_TIMEOUT
        )


        # Search page
        search_page = context.new_page()


        total = len(
            rows
        )


        for number, row in enumerate(
            rows,
            start=1
        ):

            startup_id = get_startup_id(
                row
            )

            startup_name = get_startup_name(
                row
            )


            # ------------------------------------------------
            # Resume
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


            if resume_key in processed:

                print()
                print(
                    f"[{number}/{total}] "
                    "SKIPPING — already processed"
                )

                print(
                    startup_name
                )

                continue


            print()
            print("=" * 75)

            print(
                f"SEARCH {number}/{total}"
            )

            print(
                "Startup:",
                startup_name
            )

            print("=" * 75)


            # =================================================
            # MULTIPLE SEARCH QUERIES
            # =================================================

            queries = [

                f'"{startup_name}"',

                f'"{startup_name}" Nagpur',

                f'"{startup_name}" Maharashtra',

                f'"{startup_name}" website',

                f'"{startup_name}" official website',

                f'"{startup_name}" contact',

            ]


            candidate_urls = []


            # =================================================
            # SEARCH
            # =================================================

            for query in queries:

                results = search_duckduckgo(
                    search_page,
                    query
                )


                print(
                    "Results:",
                    len(results)
                )


                for title, url in results:

                    if url not in candidate_urls:

                        candidate_urls.append(
                            url
                        )


                # Don't let the candidate list
                # grow unnecessarily large.

                if len(candidate_urls) >= 15:

                    break


                time.sleep(1)


            # ------------------------------------------------
            # Candidate summary
            # ------------------------------------------------

            print()
            print(
                "Candidate URLs found:",
                len(candidate_urls)
            )


            for i, url in enumerate(
                candidate_urls,
                start=1
            ):

                print(
                    f"{i}. {url}"
                )


            # =================================================
            # VERIFY CANDIDATES
            # =================================================

            verified = None


            for candidate in candidate_urls:

                verified = verify_candidate(
                    context,
                    candidate,
                    startup_name
                )


                if verified:

                    break


            # =================================================
            # SUCCESS
            # =================================================

            if verified:

                save_result(

                    row,

                    "VERIFIED_WEBSITE",

                    candidate_urls,

                    verified["url"],

                    queries,

                    "WEB_SEARCH",

                    verified["emails"],

                    verified["phones"],

                    verified["linkedin"],

                    verified["pagesChecked"],

                    ""

                )


                print()
                print(
                    "RESULT SAVED ✓"
                )

                print(
                    "Verified website:",
                    verified["url"]
                )


            # =================================================
            # NO VERIFIED WEBSITE
            # =================================================

            else:

                save_result(

                    row,

                    "NO_VERIFIED_WEBSITE",

                    candidate_urls,

                    "",

                    queries,

                    "",

                    set(),

                    set(),

                    set(),

                    0,

                    "Search candidates found but none could be verified"

                )


                print()
                print(
                    "RESULT SAVED ✓"
                )

                print(
                    "NO VERIFIED WEBSITE"
                )


            processed.add(
                resume_key
            )


            print()
            print(
                "Saved. Moving to next company..."
            )


            time.sleep(1)


        # ----------------------------------------------------
        # CLOSE
        # ----------------------------------------------------

        search_page.close()

        context.close()

        browser.close()


    # ========================================================
    # COMPLETE
    # ========================================================

    print()
    print("=" * 75)

    print(
        "20-COMPANY WEB SEARCH COMPLETE"
    )

    print("=" * 75)

    print()
    print(
        "Output file:"
    )

    print(
        OUTPUT_FILE
    )

    print()

    print(
        "VERIFIED_WEBSITE = verified company website"
    )

    print(
        "NO_VERIFIED_WEBSITE = no candidate could be verified"
    )

    print()

    print(
        "Candidate URLs are stored separately."
    )

    print("=" * 75)


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    main()