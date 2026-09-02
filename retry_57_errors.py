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
    "Nagpur_DPIIT_Startups_Errors.csv"
)

OUTPUT_FILE = os.path.join(
    BASE_FOLDER,
    "Nagpur_57_Error_Retry.csv"
)

# Try each website up to 3 times
MAX_RETRIES = 3

# Timeouts
NAVIGATION_TIMEOUT = 30000
PAGE_OPERATION_TIMEOUT = 10000

# Wait after successful page load
WAIT_AFTER_LOAD = 1500

# Keep browser visible
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

    # Remove obvious placeholders
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

    # Remove +91 from comparison
    if digits.startswith("91") and len(digits) == 12:
        indian_digits = digits[2:]
    else:
        indian_digits = digits

    if indian_digits in [
        "0000000000",
        "1111111111",
        "9999999999",
    ]:
        return None

    if len(indian_digits) != 10:
        return None

    if indian_digits[0] not in "6789":
        return None

    return phone


# ============================================================
# EXTRACT DATA FROM PAGE
# ============================================================

def extract_data(page):

    emails = set()
    phones = set()
    linkedin = set()

    # --------------------------------------------------------
    # PAGE TEXT
    # --------------------------------------------------------

    try:

        text = page.locator(
            "body"
        ).inner_text(
            timeout=5000
        )

    except Exception:

        text = ""


    # --------------------------------------------------------
    # PAGE HTML
    # --------------------------------------------------------

    try:

        html = page.content()

    except Exception:

        html = ""


    combined = (
        text
        + "\n"
        + html
    )


    # ========================================================
    # EMAILS
    # ========================================================

    email_matches = re.findall(
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        combined
    )

    for email in email_matches:

        email = clean_email(
            email
        )

        if email:
            emails.add(email)


    # --------------------------------------------------------
    # MAILTO LINKS
    # --------------------------------------------------------

    try:

        mailto_links = page.locator(
            'a[href^="mailto:"]'
        ).evaluate_all(
            "links => links.map(a => a.href)"
        )

        for link in mailto_links:

            email = clean_email(
                link
            )

            if email:
                emails.add(email)

    except Exception:

        pass


    # ========================================================
    # PHONES
    # ========================================================

    phone_matches = re.findall(
        r"(?:\+91[\s.-]?)?[6-9]\d{9}",
        combined
    )

    for phone in phone_matches:

        phone = clean_phone(
            phone
        )

        if phone:
            phones.add(phone)


    # ========================================================
    # TEL LINKS
    # ========================================================

    try:

        tel_links = page.locator(
            'a[href^="tel:"]'
        ).evaluate_all(
            "links => links.map(a => a.href)"
        )

        for link in tel_links:

            phone = link.replace(
                "tel:",
                ""
            ).strip()

            phone = clean_phone(
                phone
            )

            if phone:
                phones.add(phone)

    except Exception:

        pass


    # ========================================================
    # LINKEDIN
    # ========================================================

    try:

        linkedin_links = page.locator(
            'a[href*="linkedin.com"]'
        ).evaluate_all(
            "links => links.map(a => a.href)"
        )

        for link in linkedin_links:

            if "linkedin.com" in link.lower():

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
        ).lower().strip()

        href = (
            link.get("href")
            or ""
        ).strip()


        if not href:
            continue


        # Ignore email/phone links
        if href.startswith(
            "mailto:"
        ):
            continue

        if href.startswith(
            "tel:"
        ):
            continue


        # Convert relative URL
        if not href.startswith(
            "http"
        ):

            href = urljoin(
                page.url,
                href
            )


        parsed = urlparse(
            href
        )


        # Same domain only
        if parsed.netloc.lower() != base_domain:
            continue


        href_lower = href.lower()


        if any(
            keyword in text
            or keyword in href_lower
            for keyword in CONTACT_KEYWORDS
        ):

            contact_urls.add(
                href
            )


    return list(
        contact_urls
    )[:3]


# ============================================================
# GET WEBSITE COLUMN
# ============================================================

def get_website(row):

    possible_columns = [
        "originalWebsite",
        "originalWeb",
        "website",
        "Website",
        "Website URL",
        "websiteUrl",
        "original_url",
        "url",
    ]

    for column in possible_columns:

        if column in row:

            value = (
                row.get(column)
                or ""
            ).strip()

            if value:
                return value


    return ""


# ============================================================
# GET STARTUP NAME
# ============================================================

def get_startup_name(row):

    possible_columns = [
        "startupName",
        "startupName ",
        "Startup Name",
        "startup",
        "name",
        "Name",
    ]

    for column in possible_columns:

        if column in row:

            value = (
                row.get(column)
                or ""
            ).strip()

            if value:
                return value


    return "Unknown Startup"


# ============================================================
# GET STARTUP ID
# ============================================================

def get_startup_id(row):

    possible_columns = [
        "startupId",
        "Startup ID",
        "startupID",
        "id",
        "ID",
    ]

    for column in possible_columns:

        if column in row:

            value = (
                row.get(column)
                or ""
            ).strip()

            if value:
                return value


    return ""


# ============================================================
# LOAD INPUT
# ============================================================

def load_error_rows():

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

        return []


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


    print()
    print(
        "Total rows in error file:",
        len(rows)
    )


    # --------------------------------------------------------
    # Select only the 57 non-DNS errors
    # --------------------------------------------------------

    allowed_errors = {
        "HTTP_ERROR",
        "CONNECTION_ERROR",
        "OTHER_ERROR",
    }


    selected = []


    for row in rows:

        error_type = (
            row.get(
                "errorType",
                ""
            )
            or row.get(
                "originalErrorType",
                ""
            )
            or row.get(
                "Error Type",
                ""
            )
        ).strip().upper()


        if error_type in allowed_errors:

            selected.append(
                row
            )


    return selected


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
# LOAD PROCESSED STARTUPS
# ============================================================

def load_processed():

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


    except Exception as e:

        print(
            "Could not read existing retry file:"
        )

        print(e)


    return processed


# ============================================================
# SAVE RESULT
# ============================================================

def save_result(
    row,
    status,
    attempts,
    emails,
    phones,
    linkedin,
    pages_checked,
    error_message
):

    output_row = {

        "startupId":
            get_startup_id(row),

        "startupName":
            get_startup_name(row),

        "originalWebsite":
            get_website(row),

        "originalErrorType":
            (
                row.get(
                    "errorType",
                    ""
                )
                or row.get(
                    "originalErrorType",
                    ""
                )
            ),

        "status":
            status,

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

        writer.writerow(
            output_row
        )


# ============================================================
# SCRAPE ONE WEBSITE
# ============================================================

def scrape_website(
    context,
    website
):

    all_emails = set()
    all_phones = set()
    all_linkedin = set()

    pages_checked = 0

    last_error = ""

    page = None


    # ========================================================
    # THREE ATTEMPTS
    # ========================================================

    for attempt in range(
        1,
        MAX_RETRIES + 1
    ):

        print()
        print(
            f"Attempt {attempt}/{MAX_RETRIES}"
        )


        try:

            page = context.new_page()


            # ------------------------------------------------
            # Block heavy resources
            # ------------------------------------------------

            def handle_route(route):

                resource_type = (
                    route.request.resource_type
                )


                if resource_type in [
                    "image",
                    "media",
                    "font",
                ]:

                    route.abort()

                else:

                    route.continue_()


            page.route(
                "**/*",
                handle_route
            )


            # ------------------------------------------------
            # Open website
            # ------------------------------------------------

            print(
                "Opening:",
                website
            )


            response = page.goto(
                website,
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


            print(
                "Title:",
                page.title()
            )


            time.sleep(
                WAIT_AFTER_LOAD / 1000
            )


            # ------------------------------------------------
            # HTTP status check
            # ------------------------------------------------

            if (
                status_code
                and status_code >= 400
            ):

                last_error = (
                    f"HTTP {status_code}"
                )

                print(
                    "HTTP error."
                )

                page.close()

                continue


            # =================================================
            # HOMEPAGE EXTRACTION
            # =================================================

            print()
            print(
                "Extracting homepage..."
            )


            emails, phones, linkedin = (
                extract_data(page)
            )


            all_emails.update(
                emails
            )

            all_phones.update(
                phones
            )

            all_linkedin.update(
                linkedin
            )


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


            # =================================================
            # FIND CONTACT PAGES
            # =================================================

            print()
            print(
                "Looking for Contact/About pages..."
            )


            contact_urls = (
                find_contact_pages(page)
            )


            print(
                "Pages found:",
                len(contact_urls)
            )


            # ------------------------------------------------
            # Contact pages
            # ------------------------------------------------

            for contact_url in contact_urls:

                print()
                print(
                    "Checking:",
                    contact_url
                )


                contact_page = None


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


                    time.sleep(
                        WAIT_AFTER_LOAD / 1000
                    )


                    emails, phones, linkedin = (
                        extract_data(
                            contact_page
                        )
                    )


                    all_emails.update(
                        emails
                    )

                    all_phones.update(
                        phones
                    )

                    all_linkedin.update(
                        linkedin
                    )


                    print(
                        "Emails found:",
                        emails
                    )

                    print(
                        "Phones found:",
                        phones
                    )

                    print(
                        "LinkedIn found:",
                        linkedin
                    )


                except Exception as e:

                    print(
                        "Contact page failed:",
                        e
                    )


                finally:

                    if contact_page:

                        try:
                            contact_page.close()
                        except:
                            pass


            # ------------------------------------------------
            # Close homepage
            # ------------------------------------------------

            try:
                page.close()
            except:
                pass


            # =================================================
            # SUCCESS
            # =================================================

            return (
                "SUCCESS",
                attempt,
                all_emails,
                all_phones,
                all_linkedin,
                pages_checked,
                ""
            )


        except PlaywrightTimeoutError as e:

            last_error = (
                "Playwright timeout"
            )


            print()
            print(
                "TIMEOUT:"
            )

            print(e)


        except Exception as e:

            last_error = str(e)


            print()
            print(
                "ERROR:"
            )

            print(e)


        finally:

            if page:

                try:
                    page.close()
                except:
                    pass


        # ----------------------------------------------------
        # Wait before next attempt
        # ----------------------------------------------------

        if attempt < MAX_RETRIES:

            print()
            print(
                "Waiting before retry..."
            )

            time.sleep(3)


    # ========================================================
    # ALL ATTEMPTS FAILED
    # ========================================================

    return (
        "RETRY_FAILED",
        MAX_RETRIES,
        all_emails,
        all_phones,
        all_linkedin,
        pages_checked,
        last_error
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 70)
    print(
        "57 ERROR WEBSITE RETRY"
    )
    print("=" * 70)


    # --------------------------------------------------------
    # Load rows
    # --------------------------------------------------------

    rows = load_error_rows()


    if not rows:

        print()
        print(
            "No HTTP/CONNECTION/OTHER error rows found."
        )

        return


    print()
    print(
        "Non-DNS errors found:",
        len(rows)
    )


    print()
    print(
        "Expected:",
        "45 HTTP + 11 CONNECTION + 1 OTHER = 57"
    )


    # --------------------------------------------------------
    # Create output
    # --------------------------------------------------------

    create_output_file()


    # --------------------------------------------------------
    # Resume
    # --------------------------------------------------------

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
            PAGE_OPERATION_TIMEOUT
        )


        context.set_default_navigation_timeout(
            NAVIGATION_TIMEOUT
        )


        # ----------------------------------------------------
        # Process websites
        # ----------------------------------------------------

        total = len(rows)

        processed_this_run = 0


        for position, row in enumerate(
            rows,
            start=1
        ):

            startup_id = get_startup_id(
                row
            )

            startup_name = get_startup_name(
                row
            )

            website = get_website(
                row
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


            # ------------------------------------------------
            # Skip already processed
            # ------------------------------------------------

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


            # =================================================
            # STARTUP
            # =================================================

            print()
            print("=" * 70)

            print(
                f"STARTUP {position}/{total}"
            )

            print(
                "Startup:",
                startup_name
            )

            print(
                "Website:",
                website
            )

            print(
                "Original error:",
                (
                    row.get(
                        "errorType",
                        ""
                    )
                    or row.get(
                        "originalErrorType",
                        ""
                    )
                )
            )

            print("=" * 70)


            # ------------------------------------------------
            # No website
            # ------------------------------------------------

            if not website:

                print()
                print(
                    "No original website URL found."
                )


                save_result(

                    row,

                    "NO_WEBSITE_URL",

                    0,

                    set(),

                    set(),

                    set(),

                    0,

                    "No original website URL in input"

                )


                processed.add(
                    resume_key
                )


                processed_this_run += 1


                print(
                    "RESULT SAVED ✓"
                )

                continue


            # ------------------------------------------------
            # Make sure URL has scheme
            # ------------------------------------------------

            if not website.startswith(
                (
                    "http://",
                    "https://"
                )
            ):

                website = (
                    "https://"
                    + website
                )


            # =================================================
            # SCRAPE
            # =================================================

            (
                status,
                attempts,
                emails,
                phones,
                linkedin,
                pages_checked,
                error_message
            ) = scrape_website(
                context,
                website
            )


            # =================================================
            # SAVE
            # =================================================

            save_result(

                row,

                status,

                attempts,

                emails,

                phones,

                linkedin,

                pages_checked,

                error_message

            )


            processed.add(
                resume_key
            )


            processed_this_run += 1


            # =================================================
            # DISPLAY
            # =================================================

            print()
            print("=" * 70)

            print(
                "RESULT SAVED ✓"
            )

            print(
                "Startup:",
                startup_name
            )

            print(
                "Status:",
                status
            )

            print(
                "Attempts:",
                attempts
            )

            print(
                "Emails:",
                ", ".join(
                    sorted(emails)
                )
                if emails
                else "None"
            )

            print(
                "Phones:",
                ", ".join(
                    sorted(phones)
                )
                if phones
                else "None"
            )

            print(
                "LinkedIn:",
                ", ".join(
                    sorted(linkedin)
                )
                if linkedin
                else "None"
            )

            print(
                "Pages checked:",
                pages_checked
            )

            print(
                f"Progress: {position}/{total}"
            )

            print("=" * 70)


            # ------------------------------------------------
            # Small delay
            # ------------------------------------------------

            time.sleep(1)


        # ====================================================
        # CLOSE
        # ====================================================

        context.close()

        browser.close()


    # ========================================================
    # FINAL
    # ========================================================

    print()
    print("=" * 70)

    print(
        "57 ERROR RETRY FINISHED"
    )

    print("=" * 70)

    print()

    print(
        "Total non-DNS errors:",
        total
    )

    print(
        "Processed this run:",
        processed_this_run
    )

    print()

    print(
        "Output file:"
    )

    print(
        OUTPUT_FILE
    )

    print()

    print(
        "If some websites still failed after 3 attempts,"
    )

    print(
        "they are marked RETRY_FAILED."
    )

    print("=" * 70)


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()