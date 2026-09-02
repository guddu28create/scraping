from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import re
import csv
import os
from urllib.parse import urljoin, urlparse


# ============================================================
# SETTINGS
# ============================================================

BASE_FOLDER = r"C:\Users\ASUS\OneDrive\Desktop\Nagpur_Startup_Scraper"

INPUT_FILE = os.path.join(
    BASE_FOLDER,
    "Nagpur_DPIIT_Startups_With_Contacts.csv"
)

OUTPUT_FILE = os.path.join(
    BASE_FOLDER,
    "Nagpur_DPIIT_Startups_Scraped.csv"
)

# ============================================================
# FULL RUN
# ============================================================

TEST_MODE = False

# Only used if TEST_MODE = True
TEST_LIMIT = 10

# Maximum Contact/About pages to check per website
MAX_CONTACT_PAGES = 3

# Timeouts in milliseconds
PAGE_TIMEOUT = 20000
CONTACT_TIMEOUT = 15000

# Keep browser visible
HEADLESS = False


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

    # Ignore obvious placeholders
    if "example.com" in email:
        return None

    if "xxxx" in email or "****" in email:
        return None

    # Basic email validation
    if not re.match(
        r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$",
        email
    ):
        return None

    return email


# ============================================================
# CLEAN PHONE
# ============================================================

def normalize_phone(phone):

    if not phone:
        return None

    digits = re.sub(r"\D", "", phone)

    # Convert +91XXXXXXXXXX to XXXXXXXXXX
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]

    # Must be exactly 10 digits
    if len(digits) != 10:
        return None

    # Indian mobile numbers
    if digits[0] not in "6789":
        return None

    # Obvious fake numbers
    fake_numbers = {
        "0000000000",
        "1111111111",
        "2222222222",
        "3333333333",
        "4444444444",
        "5555555555",
        "6666666666",
        "7777777777",
        "8888888888",
        "9999999999"
    }

    if digits in fake_numbers:
        return None

    return "+91 " + digits


# ============================================================
# EXTRACT DATA FROM PAGE
# ============================================================

def extract_data(page):

    emails = set()
    phones = set()
    linkedin = set()

    # --------------------------------------------------------
    # VISIBLE TEXT
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
    # HTML
    # --------------------------------------------------------

    try:

        html = page.content()

    except Exception:

        html = ""


    combined = text + "\n" + html


    # ========================================================
    # EMAILS
    # ========================================================

    email_matches = re.findall(
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        combined
    )

    for email in email_matches:

        email = clean_email(email)

        if email:
            emails.add(email)


    # ========================================================
    # MAILTO LINKS
    # ========================================================

    try:

        mailto_links = page.locator(
            'a[href^="mailto:"]'
        ).evaluate_all(
            "links => links.map(a => a.href)"
        )

        for link in mailto_links:

            email = clean_email(link)

            if email:
                emails.add(email)

    except Exception:

        pass


    # ========================================================
    # PHONE NUMBERS
    # ========================================================

    phone_matches = re.findall(
        r"(?:\+91[\s.-]?)?[6-9]\d{9}",
        combined
    )

    for phone in phone_matches:

        phone = normalize_phone(phone)

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

            phone = normalize_phone(link)

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

            link_lower = link.lower()

            # Ignore LinkedIn sharing buttons
            if "sharearticle" in link_lower:
                continue

            if "linkedin.com/share" in link_lower:
                continue

            # Actual company LinkedIn page
            if "linkedin.com/company/" in link_lower:
                linkedin.add(link)

            # Actual person profile
            elif "linkedin.com/in/" in link_lower:
                linkedin.add(link)

    except Exception:

        pass


    return emails, phones, linkedin


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


    keywords = [
        "contact",
        "contact us",
        "contact-us",
        "contactus",
        "reach us",
        "reach-us",
        "about",
        "about us"
    ]


    base_domain = urlparse(
        page.url
    ).netloc.lower()


    for link in links:

        text = (
            link.get("text") or ""
        ).lower().strip()

        href = (
            link.get("href") or ""
        ).strip()


        if not href:
            continue


        # Ignore email and phone links
        if href.startswith("mailto:"):
            continue

        if href.startswith("tel:"):
            continue


        # Convert relative URLs
        if not href.startswith("http"):

            href = urljoin(
                page.url,
                href
            )


        href_domain = urlparse(
            href
        ).netloc.lower()


        # Stay on the same website
        if href_domain != base_domain:
            continue


        href_lower = href.lower()


        if any(
            keyword in text or keyword in href_lower
            for keyword in keywords
        ):

            contact_urls.add(href)


    return list(
        contact_urls
    )[:MAX_CONTACT_PAGES]


# ============================================================
# LOAD INPUT CSV
# ============================================================

def load_input_csv():

    rows = []

    with open(
        INPUT_FILE,
        "r",
        newline="",
        encoding="utf-8-sig"
    ) as file:

        reader = csv.DictReader(file)

        fieldnames = reader.fieldnames


        if not fieldnames:

            raise Exception(
                "The CSV does not contain a header row."
            )


        # Check required columns
        required_columns = [
            "startupName",
            "website"
        ]

        for column in required_columns:

            if column not in fieldnames:

                raise Exception(
                    f'Required column "{column}" '
                    f'was not found.\n\n'
                    f"Columns found:\n{fieldnames}"
                )


        for row in reader:

            rows.append(row)


    return rows, fieldnames


# ============================================================
# CREATE OUTPUT FILE
# ============================================================

def create_output_file(fieldnames):

    if os.path.exists(OUTPUT_FILE):

        print()
        print("ERROR:")
        print(
            "Output file already exists:"
        )
        print(OUTPUT_FILE)

        print()
        print(
            "Delete the old output file before "
            "starting a fresh full run."
        )

        return False


    output_fields = list(fieldnames)


    new_columns = [
        "scrapedEmail",
        "scrapedPhone",
        "scrapedLinkedIn",
        "pagesChecked",
        "scrapeStatus",
        "scrapeError"
    ]


    for column in new_columns:

        if column not in output_fields:

            output_fields.append(column)


    with open(
        OUTPUT_FILE,
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=output_fields
        )

        writer.writeheader()


    return True


# ============================================================
# SAVE RESULT
# ============================================================

def save_result(
    original_row,
    emails,
    phones,
    linkedin,
    pages_checked,
    status,
    error
):

    result = dict(original_row)


    result["scrapedEmail"] = "; ".join(
        sorted(emails)
    )

    result["scrapedPhone"] = "; ".join(
        sorted(phones)
    )

    result["scrapedLinkedIn"] = "; ".join(
        sorted(linkedin)
    )

    result["pagesChecked"] = pages_checked

    result["scrapeStatus"] = status

    result["scrapeError"] = error


    # Read output headers
    with open(
        OUTPUT_FILE,
        "r",
        newline="",
        encoding="utf-8-sig"
    ) as file:

        reader = csv.reader(file)

        fieldnames = next(reader)


    # Save immediately
    with open(
        OUTPUT_FILE,
        "a",
        newline="",
        encoding="utf-8-sig"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames
        )

        writer.writerow(result)


# ============================================================
# SCRAPE ONE STARTUP
# ============================================================

def scrape_startup(
    context,
    startup_name,
    website,
    number,
    total
):

    print()
    print("=" * 70)
    print(
        f"STARTUP {number}/{total}"
    )
    print("=" * 70)

    print(
        "Startup:",
        startup_name
    )

    print(
        "Website:",
        website
    )


    all_emails = set()
    all_phones = set()
    all_linkedin = set()

    pages_checked = 0


    page = context.new_page()


    try:

        # ====================================================
        # HOMEPAGE
        # ====================================================

        print()
        print("Opening website...")


        try:

            response = page.goto(
                website,
                wait_until="domcontentloaded",
                timeout=PAGE_TIMEOUT
            )


            if response:

                print(
                    "HTTP status:",
                    response.status
                )


            print(
                "Final URL:",
                page.url
            )


            try:

                print(
                    "Title:",
                    page.title()
                )

            except Exception:

                pass


        except PlaywrightTimeoutError:

            print()
            print(
                "WARNING: Homepage timed out."
            )

            print(
                "Trying to extract whatever loaded..."
            )


        except Exception as e:

            print()
            print(
                "ERROR opening homepage:"
            )

            print(e)


            try:
                page.close()
            except Exception:
                pass


            return (
                set(),
                set(),
                set(),
                0,
                "ERROR",
                str(e)
            )


        # ====================================================
        # EXTRACT HOMEPAGE
        # ====================================================

        print()
        print("Extracting homepage...")


        emails, phones, linkedin = extract_data(
            page
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


        pages_checked += 1


        print(
            "Emails:",
            emails if emails else "None"
        )

        print(
            "Phones:",
            phones if phones else "None"
        )

        print(
            "LinkedIn:",
            linkedin if linkedin else "None"
        )


        # ====================================================
        # FIND CONTACT / ABOUT PAGES
        # ====================================================

        print()
        print(
            "Looking for Contact/About pages..."
        )


        contact_urls = find_contact_pages(
            page
        )


        print(
            "Pages found:",
            len(contact_urls)
        )


        for contact_url in contact_urls:

            print(
                "Found:",
                contact_url
            )


        # ====================================================
        # VISIT CONTACT / ABOUT PAGES
        # ====================================================

        for contact_url in contact_urls:

            print()
            print(
                "Checking:",
                contact_url
            )


            contact_page = context.new_page()


            try:

                contact_page.goto(
                    contact_url,
                    wait_until="domcontentloaded",
                    timeout=CONTACT_TIMEOUT
                )


                contact_page.wait_for_timeout(
                    500
                )


                emails, phones, linkedin = extract_data(
                    contact_page
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


                pages_checked += 1


                print(
                    "Emails found:",
                    emails if emails else "None"
                )

                print(
                    "Phones found:",
                    phones if phones else "None"
                )

                print(
                    "LinkedIn found:",
                    linkedin if linkedin else "None"
                )


            except PlaywrightTimeoutError:

                print(
                    "Contact page timed out — skipping."
                )


            except Exception as e:

                print(
                    "Contact page error:",
                    e
                )


            finally:

                try:
                    contact_page.close()
                except Exception:
                    pass


        try:
            page.close()
        except Exception:
            pass


        return (
            all_emails,
            all_phones,
            all_linkedin,
            pages_checked,
            "SUCCESS",
            ""
        )


    except Exception as e:

        print()
        print(
            "Unexpected error:"
        )

        print(e)


        try:
            page.close()
        except Exception:
            pass


        return (
            all_emails,
            all_phones,
            all_linkedin,
            pages_checked,
            "ERROR",
            str(e)
        )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 70)
    print("NAGPUR DPIIT STARTUP WEBSITE SCRAPER")
    print("=" * 70)


    # ========================================================
    # CHECK INPUT
    # ========================================================

    if not os.path.exists(INPUT_FILE):

        print()
        print(
            "ERROR: Input CSV not found:"
        )

        print(
            INPUT_FILE
        )

        return


    # ========================================================
    # LOAD CSV
    # ========================================================

    try:

        rows, fieldnames = load_input_csv()

    except Exception as e:

        print()
        print(
            "ERROR reading CSV:"
        )

        print(e)

        return


    print()
    print(
        "Total startups in original CSV:",
        len(rows)
    )


    # ========================================================
    # FIND STARTUPS WITH WEBSITES
    # ========================================================

    startups_with_websites = []


    for row in rows:

        website = (
            row.get("website") or ""
        ).strip()


        if website:

            if not website.startswith(
                ("http://", "https://")
            ):

                website = (
                    "https://" + website
                )


            row_copy = dict(row)

            row_copy["website"] = website

            startups_with_websites.append(
                row_copy
            )


    print(
        "Startups with websites:",
        len(startups_with_websites)
    )


    print(
        "Startups without websites:",
        len(rows) - len(startups_with_websites)
    )


    # ========================================================
    # SELECT TEST OR FULL RUN
    # ========================================================

    if TEST_MODE:

        startups_to_process = (
            startups_with_websites[:TEST_LIMIT]
        )

        print()
        print("TEST MODE IS ON")

        print(
            "Processing first",
            len(startups_to_process),
            "startups only."
        )

    else:

        startups_to_process = (
            startups_with_websites
        )

        print()
        print("FULL MODE IS ON")

        print(
            "Processing all",
            len(startups_to_process),
            "startups with websites."
        )


    # ========================================================
    # CREATE OUTPUT
    # ========================================================

    if not create_output_file(
        fieldnames
    ):

        return


    # ========================================================
    # START PLAYWRIGHT
    # ========================================================

    with sync_playwright() as p:

        print()
        print(
            "Starting Playwright..."
        )


        browser = p.chromium.launch(
            headless=HEADLESS
        )


        context = browser.new_context(
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
            PAGE_TIMEOUT
        )


        # ====================================================
        # BLOCK HEAVY RESOURCES
        # ====================================================

        def handle_route(route):

            resource_type = (
                route.request.resource_type
            )


            if resource_type in [
                "image",
                "media",
                "font"
            ]:

                route.abort()

            else:

                route.continue_()


        context.route(
            "**/*",
            handle_route
        )


        # ====================================================
        # PROCESS
        # ====================================================

        total = len(
            startups_to_process
        )


        for index, row in enumerate(
            startups_to_process,
            start=1
        ):

            startup_name = (
                row.get("startupName")
                or "Unknown Startup"
            ).strip()


            website = (
                row.get("website")
                or ""
            ).strip()


            (
                emails,
                phones,
                linkedin,
                pages_checked,
                status,
                error
            ) = scrape_startup(
                context,
                startup_name,
                website,
                index,
                total
            )


            # =================================================
            # SAVE RESULT
            # =================================================

            save_result(
                original_row=row,
                emails=emails,
                phones=phones,
                linkedin=linkedin,
                pages_checked=pages_checked,
                status=status,
                error=error
            )


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
                "Status:",
                status
            )

            print("=" * 70)


    # ========================================================
    # COMPLETE
    # ========================================================

    print()
    print()
    print("=" * 70)
    print("SCRAPING FINISHED")
    print("=" * 70)

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