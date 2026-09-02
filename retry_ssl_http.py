from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import csv
import os
import re
import time
from urllib.parse import urljoin, urlparse


# ============================================================
# SETTINGS
# ============================================================

BASE_FOLDER = r"C:\Users\ASUS\OneDrive\Desktop\Nagpur_Startup_Scraper"

INPUT_FILE = os.path.join(
    BASE_FOLDER,
    "Nagpur_57_Error_Retry.csv"
)

OUTPUT_FILE = os.path.join(
    BASE_FOLDER,
    "Nagpur_SSL_HTTP_Recovery.csv"
)

MAX_ATTEMPTS_PER_METHOD = 2

NAVIGATION_TIMEOUT = 30000

PAGE_TIMEOUT = 10000

HEADLESS = False


# ============================================================
# CONTACT PAGE KEYWORDS
# ============================================================

CONTACT_KEYWORDS = [
    "contact",
    "contact us",
    "contact-us",
    "contactus",
    "reach us",
    "reach-us",
    "about",
    "about us",
    "about-us",
]


# ============================================================
# OUTPUT COLUMNS
# ============================================================

OUTPUT_FIELDS = [
    "startupId",
    "startupName",
    "originalWebsite",
    "originalErrorType",

    "status",
    "successfulURL",
    "method",
    "attempts",

    "emails",
    "phones",
    "linkedin",

    "pagesChecked",

    "errorMessage",
]


# ============================================================
# CLEAN EMAIL
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


# ============================================================
# CLEAN PHONE
# ============================================================

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

    if digits in [
        "0000000000",
        "1111111111",
        "9999999999",
    ]:
        return None

    return phone


# ============================================================
# EXTRACT DATA
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
    # TEL LINKS
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

    contact_urls = set()

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

            href = urljoin(
                page.url,
                href
            )


        if urlparse(
            href
        ).netloc.lower() != base_domain:

            continue


        href_lower = href.lower()


        if any(
            keyword in text
            or keyword in href_lower
            for keyword in CONTACT_KEYWORDS
        ):

            contact_urls.add(href)


    return list(
        contact_urls
    )[:3]


# ============================================================
# GET VALUES FROM CSV
# ============================================================

def get_value(row, possible_columns):

    for column in possible_columns:

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
            "ID",
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
            "Name",
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
            "original_url",
            "url",
        ]
    )


# ============================================================
# NORMALIZE URL
# ============================================================

def normalize_url(url):

    if not url:
        return ""

    url = url.strip()

    # --------------------------------------------------------
    # Remove obvious malformed prefixes
    # --------------------------------------------------------

    url = re.sub(
        r"^https?://\s*https?://",
        "https://",
        url,
        flags=re.IGNORECASE
    )

    # Remove spaces
    url = url.replace(
        " ",
        ""
    )

    # --------------------------------------------------------
    # Reject obviously invalid URLs
    # --------------------------------------------------------

    if url in [
        "https://0.0.0.0/",
        "http://0.0.0.0/",
    ]:
        return ""

    if "://:" in url:
        return ""

    if not url.startswith(
        ("http://", "https://")
    ):

        url = (
            "https://"
            + url
        )

    try:

        parsed = urlparse(url)

        if not parsed.netloc:
            return ""

    except Exception:

        return ""

    return url


# ============================================================
# SAVE RESULT
# ============================================================

def save_result(
    row,
    status,
    successful_url,
    method,
    attempts,
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

        "successfulURL":
            successful_url,

        "method":
            method,

        "attempts":
            attempts,

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
            error_message,
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

        writer.writerow(output)


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
# TRY ONE URL
# ============================================================

def try_url(
    context,
    url,
    ignore_https_errors,
    method_name
):

    emails = set()
    phones = set()
    linkedin = set()

    pages_checked = 0

    last_error = ""

    # --------------------------------------------------------
    # Attempt twice
    # --------------------------------------------------------

    for attempt in range(
        1,
        MAX_ATTEMPTS_PER_METHOD + 1
    ):

        page = None

        try:

            print()
            print(
                f"Method: {method_name}"
            )

            print(
                f"Attempt: {attempt}/{MAX_ATTEMPTS_PER_METHOD}"
            )

            print(
                "Opening:",
                url
            )


            page = context.new_page()


            # ------------------------------------------------
            # Open URL
            # ------------------------------------------------

            response = page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=NAVIGATION_TIMEOUT
            )


            pages_checked += 1


            status_code = (
                response.status
                if response
                else None
            )


            print(
                "HTTP status:",
                status_code
            )

            print(
                "Final URL:",
                page.url
            )


            # ------------------------------------------------
            # HTTP errors
            # ------------------------------------------------

            if (
                status_code
                and status_code >= 400
            ):

                last_error = (
                    f"HTTP {status_code}"
                )

                print(
                    last_error
                )

                page.close()

                continue


            time.sleep(1.5)


            # =================================================
            # HOMEPAGE
            # =================================================

            page_emails, page_phones, page_linkedin = (
                extract_data(page)
            )


            emails.update(
                page_emails
            )

            phones.update(
                page_phones
            )

            linkedin.update(
                page_linkedin
            )


            print(
                "Emails:",
                page_emails
            )

            print(
                "Phones:",
                page_phones
            )

            print(
                "LinkedIn:",
                page_linkedin
            )


            # =================================================
            # CONTACT / ABOUT
            # =================================================

            contact_urls = (
                find_contact_pages(page)
            )


            print(
                "Contact/About pages:",
                len(contact_urls)
            )


            for contact_url in contact_urls:

                contact_page = None

                try:

                    print(
                        "Checking:",
                        contact_url
                    )


                    contact_page = (
                        context.new_page()
                    )


                    contact_page.goto(
                        contact_url,
                        wait_until="domcontentloaded",
                        timeout=NAVIGATION_TIMEOUT
                    )


                    pages_checked += 1


                    time.sleep(1)


                    (
                        page_emails,
                        page_phones,
                        page_linkedin
                    ) = extract_data(
                        contact_page
                    )


                    emails.update(
                        page_emails
                    )

                    phones.update(
                        page_phones
                    )

                    linkedin.update(
                        page_linkedin
                    )


                    print(
                        "Emails found:",
                        page_emails
                    )

                    print(
                        "Phones found:",
                        page_phones
                    )

                    print(
                        "LinkedIn found:",
                        page_linkedin
                    )


                except Exception as e:

                    print(
                        "Contact page error:",
                        e
                    )


                finally:

                    if contact_page:

                        try:
                            contact_page.close()
                        except:
                            pass


            # ------------------------------------------------
            # Close
            # ------------------------------------------------

            try:
                page.close()
            except:
                pass


            # =================================================
            # SUCCESS
            # =================================================

            return (
                True,
                emails,
                phones,
                linkedin,
                pages_checked,
                attempt,
                ""
            )


        except PlaywrightTimeoutError as e:

            last_error = (
                "Playwright timeout"
            )

            print(
                "TIMEOUT:",
                e
            )


        except Exception as e:

            last_error = str(e)

            print(
                "ERROR:",
                e
            )


        finally:

            if page:

                try:
                    page.close()
                except:
                    pass


        if attempt < MAX_ATTEMPTS_PER_METHOD:

            time.sleep(2)


    return (
        False,
        emails,
        phones,
        linkedin,
        pages_checked,
        MAX_ATTEMPTS_PER_METHOD,
        last_error
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 75)
    print(
        "SSL / HTTP WEBSITE RECOVERY"
    )
    print("=" * 75)


    # --------------------------------------------------------
    # Input
    # --------------------------------------------------------

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
    # Only RETRY_FAILED
    # --------------------------------------------------------

    failed_rows = [

        row

        for row in rows

        if row.get(
            "status",
            ""
        ).strip().upper()
        == "RETRY_FAILED"

    ]


    print()
    print(
        "Retry-failed rows:",
        len(failed_rows)
    )


    if not failed_rows:

        print(
            "Nothing to recover."
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


        # ----------------------------------------------------
        # IMPORTANT:
        # ignore HTTPS certificate errors
        # ----------------------------------------------------

        context = p.chromium.launch(
            headless=HEADLESS
        )


        browser_context = context.new_context(
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


        browser_context.set_default_timeout(
            PAGE_TIMEOUT
        )


        browser_context.set_default_navigation_timeout(
            NAVIGATION_TIMEOUT
        )


        total = len(
            failed_rows
        )

        processed_this_run = 0


        # ====================================================
        # PROCESS
        # ====================================================

        for position, row in enumerate(
            failed_rows,
            start=1
        ):

            startup_id = get_startup_id(
                row
            )

            startup_name = get_startup_name(
                row
            )

            original_url = (
                get_original_website(
                    row
                )
            )


            # ------------------------------------------------
            # Resume key
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
                    f"[{position}/{total}] "
                    "SKIPPING — already processed"
                )

                print(
                    startup_name
                )

                continue


            print()
            print("=" * 75)

            print(
                f"STARTUP {position}/{total}"
            )

            print(
                "Startup:",
                startup_name
            )

            print(
                "Original URL:",
                original_url
            )

            print("=" * 75)


            # ------------------------------------------------
            # Normalize
            # ------------------------------------------------

            url = normalize_url(
                original_url
            )


            if not url:

                print()
                print(
                    "Invalid original URL."
                )

                save_result(

                    row,

                    "NEEDS_WEB_SEARCH",

                    "",

                    "INVALID_URL",

                    0,

                    set(),

                    set(),

                    set(),

                    0,

                    "Invalid or malformed original URL"

                )


                processed.add(
                    resume_key
                )

                processed_this_run += 1

                print(
                    "RESULT SAVED ✓"
                )

                continue


            # =================================================
            # METHOD 1 — HTTPS WITH CERTIFICATE ERRORS IGNORED
            # =================================================

            print()
            print(
                "METHOD 1:"
            )

            print(
                "HTTPS with certificate validation disabled"
            )


            (
                success,
                emails,
                phones,
                linkedin,
                pages_checked,
                attempts,
                error_message
            ) = try_url(

                browser_context,

                url,

                True,

                "HTTPS_IGNORE_SSL"

            )


            if success:

                save_result(

                    row,

                    "SUCCESS",

                    url,

                    "HTTPS_IGNORE_SSL",

                    attempts,

                    emails,

                    phones,

                    linkedin,

                    pages_checked,

                    ""

                )


                processed.add(
                    resume_key
                )

                processed_this_run += 1


                print()
                print(
                    "RESULT SAVED ✓"
                )

                print(
                    "Recovered using HTTPS."
                )

                continue


            # =================================================
            # METHOD 2 — HTTP
            # =================================================

            http_url = url


            if url.lower().startswith(
                "https://"
            ):

                http_url = (
                    "http://"
                    + url[8:]
                )


            print()
            print(
                "METHOD 2:"
            )

            print(
                "HTTP fallback"
            )


            (
                success_http,
                emails_http,
                phones_http,
                linkedin_http,
                pages_http,
                attempts_http,
                error_http
            ) = try_url(

                browser_context,

                http_url,

                False,

                "HTTP"

            )


            # ------------------------------------------------
            # Combine whatever was found
            # ------------------------------------------------

            emails.update(
                emails_http
            )

            phones.update(
                phones_http
            )

            linkedin.update(
                linkedin_http
            )


            pages_checked += (
                pages_http
            )


            total_attempts = (
                attempts
                + attempts_http
            )


            # =================================================
            # HTTP SUCCESS
            # =================================================

            if success_http:

                save_result(

                    row,

                    "SUCCESS",

                    http_url,

                    "HTTP_FALLBACK",

                    total_attempts,

                    emails,

                    phones,

                    linkedin,

                    pages_checked,

                    ""

                )


                processed.add(
                    resume_key
                )

                processed_this_run += 1


                print()
                print(
                    "RESULT SAVED ✓"
                )

                print(
                    "Recovered using HTTP."
                )

                continue


            # =================================================
            # FAILED BOTH
            # =================================================

            final_error = (
                "HTTPS failed: "
                + str(error_message)
                + " | HTTP failed: "
                + str(error_http)
            )


            save_result(

                row,

                "NEEDS_WEB_SEARCH",

                "",

                "HTTPS_AND_HTTP_FAILED",

                total_attempts,

                emails,

                phones,

                linkedin,

                pages_checked,

                final_error

            )


            processed.add(
                resume_key
            )

            processed_this_run += 1


            print()
            print(
                "RESULT SAVED ✓"
            )

            print(
                "Both HTTPS and HTTP failed."
            )

            print(
                "Marked for web search."
            )


            time.sleep(1)


        # ====================================================
        # CLOSE
        # ====================================================

        browser_context.close()

        context.close()


    # ========================================================
    # FINAL
    # ========================================================

    print()
    print("=" * 75)

    print(
        "SSL / HTTP RECOVERY FINISHED"
    )

    print("=" * 75)

    print()

    print(
        "Total rows:",
        total
    )

    print(
        "Processed this run:",
        processed_this_run
    )

    print()

    print(
        "Output:"
    )

    print(
        OUTPUT_FILE
    )

    print()

    print(
        "SUCCESS = website recovered"
    )

    print(
        "NEEDS_WEB_SEARCH = HTTPS and HTTP both failed"
    )

    print("=" * 75)


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()