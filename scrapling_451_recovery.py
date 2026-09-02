import csv
import os
import re
import socket
import time
from urllib.parse import urlparse

# ============================================================
# SCRAPLING IMPORTS
# ============================================================

try:
    from scrapling.fetchers import Fetcher, StealthyFetcher
except ImportError:
    print()
    print("=" * 70)
    print("SCRAPLING IMPORT ERROR")
    print("=" * 70)
    print()
    print("Try:")
    print("pip install -U scrapling")
    print()
    raise


# ============================================================
# PATHS
# ============================================================

BASE_FOLDER = (
    r"C:\Users\ASUS\OneDrive\Desktop\Nagpur_Startup_Scraper"
)

INPUT_FILE = os.path.join(
    BASE_FOLDER,
    "Nagpur_DPIIT_Startups_Cleaned.csv"
)

OUTPUT_FILE = os.path.join(
    BASE_FOLDER,
    "Nagpur_Scrapling_451_Recovery.csv"
)


# ============================================================
# SETTINGS
# ============================================================

REQUEST_TIMEOUT = 30

DELAY_BETWEEN_COMPANIES = 2

# Do not use browser/search-engine automation.
# This script only attempts the supplied website.


# ============================================================
# OUTPUT COLUMNS
# ============================================================

FIELDS = [
    "startupId",
    "startupName",
    "originalWebsite",

    "methodUsed",

    "verifiedWebsite",

    "emails",
    "phones",
    "linkedin",

    "status",
    "errorType",

    "httpStatus",
    "finalURL",

    "attempts",
    "notes"
]


# ============================================================
# HELPERS
# ============================================================

def get_value(row, possible_names):

    for name in possible_names:

        if name in row:

            value = (
                row.get(name)
                or ""
            ).strip()

            if value:
                return value

    return ""


def clean_website(value):

    if not value:
        return ""

    value = value.strip()

    if value.upper() in {
        "NA",
        "NIL",
        "NONE",
        "NULL",
        "N/A",
        "-",
        "NOT AVAILABLE"
    }:

        return ""

    if not value.startswith(
        "http://"
    ) and not value.startswith(
        "https://"
    ):

        value = (
            "https://"
            + value
        )

    return value


def get_domain(url):

    try:

        parsed = urlparse(url)

        domain = parsed.netloc.lower()

        if domain.startswith("www."):
            domain = domain[4:]

        domain = domain.split(":")[0]

        return domain

    except:

        return ""


def dns_check(url):

    try:

        domain = get_domain(url)

        if not domain:
            return False

        socket.gethostbyname(domain)

        return True

    except:

        return False


# ============================================================
# CONTACT CLEANING
# ============================================================

def clean_email(email):

    if not email:
        return None

    email = email.strip().lower()

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


# ============================================================
# EXTRACT CONTACT DATA
# ============================================================

def extract_data(page):

    emails = set()
    phones = set()
    linkedin = set()


    # --------------------------------------------------------
    # TEXT
    # --------------------------------------------------------

    try:

        text = page.get_text(
            separator=" "
        )

    except:

        try:
            text = page.text
        except:
            text = ""


    # --------------------------------------------------------
    # HTML
    # --------------------------------------------------------

    try:

        html = str(page)

    except:

        html = ""


    combined = (
        text
        + "\n"
        + html
    )


    # --------------------------------------------------------
    # EMAILS
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
    # PHONES
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
    # LINKEDIN
    # --------------------------------------------------------

    linkedin_matches = re.findall(
        r"https?://(?:www\.)?linkedin\.com/[^\s\"'<>]+",
        combined,
        flags=re.IGNORECASE
    )

    for link in linkedin_matches:

        link = link.rstrip(
            ".,);]"
        )

        linkedin.add(link)


    return (
        emails,
        phones,
        linkedin
    )


# ============================================================
# CONTACT PAGE DISCOVERY
# ============================================================

def find_contact_pages(page):

    urls = set()

    keywords = [
        "contact",
        "contact us",
        "contact-us",
        "contactus",
        "about",
        "about us",
        "about-us",
        "reach us"
    ]


    try:

        links = page.css(
            "a"
        )

    except:

        return []


    base_domain = get_domain(
        getattr(
            page,
            "url",
            ""
        )
    )


    for link in links:

        try:

            href = link.attrib.get(
                "href",
                ""
            )

        except:

            continue


        if not href:
            continue


        if not href.startswith(
            "http"
        ):

            continue


        if get_domain(href) != base_domain:
            continue


        try:

            text = link.text or ""

        except:

            text = ""


        combined = (
            text
            + " "
            + href
        ).lower()


        if any(
            keyword in combined
            for keyword in keywords
        ):

            urls.add(href)


    return list(urls)[:3]


# ============================================================
# FETCH METHOD 1
# NORMAL SCRAPLING FETCHER
# ============================================================

def normal_fetch(url):

    print()
    print(
        "METHOD 1: Scrapling Fetcher"
    )

    try:

        page = Fetcher.get(
            url,
            timeout=REQUEST_TIMEOUT
        )

        print(
            "Fetcher returned a response."
        )

        return page

    except Exception as e:

        print(
            "Fetcher failed:"
        )

        print(
            str(e)[:500]
        )

        return None


# ============================================================
# FETCH METHOD 2
# STEALTHY SCRAPLING FETCHER
# ============================================================

def stealth_fetch(url):

    print()
    print(
        "METHOD 2: Scrapling StealthyFetcher"
    )

    try:

        page = StealthyFetcher.fetch(
            url,
            headless=True,
            timeout=REQUEST_TIMEOUT
        )

        print(
            "StealthyFetcher returned a response."
        )

        return page

    except Exception as e:

        print(
            "StealthyFetcher failed:"
        )

        print(
            str(e)[:500]
        )

        return None


# ============================================================
# INSPECT RESPONSE
# ============================================================

def inspect_page(
    page,
    startup_name,
    method
):

    if page is None:
        return None


    # --------------------------------------------------------
    # STATUS
    # --------------------------------------------------------

    status = None

    try:
        status = page.status
    except:
        pass


    print(
        "HTTP status:",
        status if status else "Unknown"
    )


    # --------------------------------------------------------
    # FINAL URL
    # --------------------------------------------------------

    final_url = ""

    try:
        final_url = page.url
    except:
        pass


    print(
        "Final URL:",
        final_url
        if final_url
        else "Unknown"
    )


    # --------------------------------------------------------
    # TITLE
    # --------------------------------------------------------

    title = ""

    try:

        title_nodes = page.css(
            "title"
        )

        if title_nodes:

            title = (
                title_nodes[0].text
                or ""
            ).strip()

    except:

        pass


    print(
        "Title:",
        title
        if title
        else "No title"
    )


    # --------------------------------------------------------
    # EXTRACT CONTACT DATA
    # --------------------------------------------------------

    emails, phones, linkedin = (
        extract_data(page)
    )


    print()
    print(
        "Emails:",
        emails
    )

    print(
        "Phones:",
        phones
    )

    print(
        "LinkedIn:",
        linkedin
    )


    # --------------------------------------------------------
    # CONTACT PAGES
    # --------------------------------------------------------

    contact_pages = (
        find_contact_pages(page)
    )


    print()
    print(
        "Contact/About pages found:",
        len(contact_pages)
    )


    # --------------------------------------------------------
    # CHECK CONTACT PAGES
    # --------------------------------------------------------

    pages_checked = 1


    for contact_url in contact_pages:

        print()
        print(
            "Checking contact page:"
        )

        print(
            contact_url
        )


        try:

            cp = Fetcher.get(
                contact_url,
                timeout=REQUEST_TIMEOUT
            )


            e, p, l = (
                extract_data(cp)
            )


            emails.update(e)
            phones.update(p)
            linkedin.update(l)


            pages_checked += 1


            print(
                "Emails:",
                e
            )

            print(
                "Phones:",
                p
            )

            print(
                "LinkedIn:",
                l
            )


        except Exception as e:

            print(
                "Contact page failed:"
            )

            print(
                str(e)[:300]
            )


    # --------------------------------------------------------
    # RESULT
    # --------------------------------------------------------

    if status is not None:

        if status >= 400:

            return {
                "success": False,
                "status": status,
                "final_url": final_url,
                "emails": emails,
                "phones": phones,
                "linkedin": linkedin,
                "pages_checked": pages_checked,
                "method": method,
                "error": "HTTP_ERROR"
            }


    return {
        "success": True,
        "status": status,
        "final_url": final_url,
        "emails": emails,
        "phones": phones,
        "linkedin": linkedin,
        "pages_checked": pages_checked,
        "method": method,
        "error": ""
    }


# ============================================================
# SAVE RESULT
# ============================================================

def save_result(result):

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
            result
        )


        f.flush()


# ============================================================
# LOAD COMPLETED COMPANIES
# ============================================================

def load_completed():

    completed = set()


    if not os.path.exists(
        OUTPUT_FILE
    ):

        return completed


    try:

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
                    completed.add(name)


    except Exception as e:

        print(
            "Could not read previous checkpoint:"
        )

        print(e)


    return completed


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 75)

    print(
        "SCRAPLING — 451 DNS RECOVERY"
    )

    print("=" * 75)


    # --------------------------------------------------------
    # INPUT CHECK
    # --------------------------------------------------------

    if not os.path.exists(
        INPUT_FILE
    ):

        print()
        print(
            "INPUT FILE NOT FOUND:"
        )

        print(
            INPUT_FILE
        )

        return


    # --------------------------------------------------------
    # READ CSV
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


    # --------------------------------------------------------
    # GET DNS ERRORS ONLY
    # --------------------------------------------------------

    dns_rows = []


    for row in rows:

        error_type = (
            get_value(
                row,
                [
                    "ERROR_TYPE",
                    "errorType",
                    "Error Type"
                ]
            )
            .upper()
        )


        status = (
            get_value(
                row,
                [
                    "STATUS",
                    "status",
                    "Status"
                ]
            )
            .upper()
        )


        if (
            error_type == "DNS_ERROR"
            or status == "DNS_ERROR"
        ):

            dns_rows.append(row)


    print()
    print(
        "Total DNS errors:",
        len(dns_rows)
    )


    # --------------------------------------------------------
    # CHECKPOINT
    # --------------------------------------------------------

    completed = load_completed()


    print(
        "Already completed:",
        len(completed)
    )


    # --------------------------------------------------------
    # PROCESS
    # --------------------------------------------------------

    for number, row in enumerate(
        dns_rows,
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


        # ----------------------------------------------------
        # SKIP COMPLETED
        # ----------------------------------------------------

        if (
            startup_name.lower()
            in completed
        ):

            print()
            print(
                f"[{number}/{len(dns_rows)}] "
                "ALREADY COMPLETED — SKIPPING"
            )

            print(
                startup_name
            )

            continue


        # ----------------------------------------------------
        # WEBSITE
        # ----------------------------------------------------

        original_website = (
            clean_website(
                get_value(
                    row,
                    [
                        "WEBSITE",
                        "Website",
                        "website",
                        "Original Website",
                        "originalWebsite"
                    ]
                )
            )
        )


        print()
        print("=" * 75)

        print(
            f"STARTUP {number}/{len(dns_rows)}"
        )

        print(
            "Startup:",
            startup_name
        )

        print(
            "Website:",
            original_website
            if original_website
            else "NO WEBSITE"
        )

        print("=" * 75)


        # ----------------------------------------------------
        # NO WEBSITE
        # ----------------------------------------------------

        if not original_website:

            save_result({

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
                    "",

                "methodUsed":
                    "NONE",

                "verifiedWebsite":
                    "",

                "emails":
                    "",

                "phones":
                    "",

                "linkedin":
                    "",

                "status":
                    "NO_WEBSITE",

                "errorType":
                    "NO_ORIGINAL_URL",

                "httpStatus":
                    "",

                "finalURL":
                    "",

                "attempts":
                    0,

                "notes":
                    "No usable website was present in the source CSV"

            })


            completed.add(
                startup_name.lower()
            )


            print()
            print(
                "NO ORIGINAL WEBSITE — SAVED ✓"
            )


            continue


        # ----------------------------------------------------
        # DNS CHECK
        # ----------------------------------------------------

        print()
        print(
            "Checking DNS..."
        )


        dns_ok = dns_check(
            original_website
        )


        print(
            "DNS resolves:",
            dns_ok
        )


        # ----------------------------------------------------
        # ATTEMPT 1
        # ----------------------------------------------------

        page = normal_fetch(
            original_website
        )


        result = inspect_page(
            page,
            startup_name,
            "Scrapling Fetcher"
        )


        # ----------------------------------------------------
        # SUCCESS
        # ----------------------------------------------------

        if result and result["success"]:

            save_result({

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

                "methodUsed":
                    result["method"],

                "verifiedWebsite":
                    result["final_url"],

                "emails":
                    ", ".join(
                        sorted(
                            result["emails"]
                        )
                    ),

                "phones":
                    ", ".join(
                        sorted(
                            result["phones"]
                        )
                    ),

                "linkedin":
                    ", ".join(
                        sorted(
                            result["linkedin"]
                        )
                    ),

                "status":
                    "SUCCESS",

                "errorType":
                    "",

                "httpStatus":
                    result["status"]
                    or "",

                "finalURL":
                    result["final_url"],

                "attempts":
                    1,

                "notes":
                    "Website successfully retrieved using Scrapling"

            })


            completed.add(
                startup_name.lower()
            )


            print()
            print(
                "SUCCESS ✓"
            )

            print(
                "RESULT SAVED ✓"
            )


            time.sleep(
                DELAY_BETWEEN_COMPANIES
            )

            continue


        # ----------------------------------------------------
        # ATTEMPT 2
        # ----------------------------------------------------

        print()
        print(
            "Normal Fetcher failed."
        )

        print(
            "Trying StealthyFetcher..."
        )


        page = stealth_fetch(
            original_website
        )


        result = inspect_page(
            page,
            startup_name,
            "Scrapling StealthyFetcher"
        )


        # ----------------------------------------------------
        # SUCCESS
        # ----------------------------------------------------

        if result and result["success"]:

            save_result({

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

                "methodUsed":
                    result["method"],

                "verifiedWebsite":
                    result["final_url"],

                "emails":
                    ", ".join(
                        sorted(
                            result["emails"]
                        )
                    ),

                "phones":
                    ", ".join(
                        sorted(
                            result["phones"]
                        )
                    ),

                "linkedin":
                    ", ".join(
                        sorted(
                            result["linkedin"]
                        )
                    ),

                "status":
                    "SUCCESS",

                "errorType":
                    "",

                "httpStatus":
                    result["status"]
                    or "",

                "finalURL":
                    result["final_url"],

                "attempts":
                    2,

                "notes":
                    "Website successfully retrieved using Scrapling StealthyFetcher"

            })


            completed.add(
                startup_name.lower()
            )


            print()
            print(
                "SUCCESS ✓"
            )

            print(
                "RESULT SAVED ✓"
            )


            time.sleep(
                DELAY_BETWEEN_COMPANIES
            )

            continue


        # ----------------------------------------------------
        # BOTH FAILED
        # ----------------------------------------------------

        if not dns_ok:

            error_type = (
                "DNS_UNRESOLVED"
            )

            notes = (
                "Domain does not currently resolve through DNS; "
                "Scrapling cannot retrieve a domain with no DNS record."
            )

        else:

            error_type = (
                "SCRAPLING_FAILED"
            )

            notes = (
                "DNS resolves but both Scrapling methods failed "
                "to retrieve the website."
            )


        save_result({

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

            "methodUsed":
                "Fetcher + StealthyFetcher",

            "verifiedWebsite":
                "",

            "emails":
                "",

            "phones":
                "",

            "linkedin":
                "",

            "status":
                "ERROR",

            "errorType":
                error_type,

            "httpStatus":
                "",

            "finalURL":
                "",

            "attempts":
                2,

            "notes":
                notes

        })


        completed.add(
            startup_name.lower()
        )


        print()
        print(
            "BOTH SCRAPLING METHODS FAILED"
        )

        print(
            "RESULT SAVED ✓"
        )


        time.sleep(
            DELAY_BETWEEN_COMPANIES
        )


    # --------------------------------------------------------
    # FINISHED
    # --------------------------------------------------------

    print()
    print("=" * 75)

    print(
        "SCRAPLING 451 RECOVERY FINISHED"
    )

    print("=" * 75)

    print()
    print(
        "Output file:"
    )

    print(
        OUTPUT_FILE
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()