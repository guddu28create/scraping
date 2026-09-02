import csv
import os
import re
from collections import Counter


# ============================================================
# SETTINGS
# ============================================================

BASE_FOLDER = r"C:\Users\ASUS\OneDrive\Desktop\Nagpur_Startup_Scraper"

INPUT_FILE = os.path.join(
    BASE_FOLDER,
    "Nagpur_DPIIT_Startups_Scraped.csv"
)

OUTPUT_FILE = os.path.join(
    BASE_FOLDER,
    "Nagpur_DPIIT_Startups_Cleaned.csv"
)

ERROR_FILE = os.path.join(
    BASE_FOLDER,
    "Nagpur_DPIIT_Startups_Errors.csv"
)


# ============================================================
# CLEAN EMAIL
# ============================================================

def clean_emails(value):

    if not value:
        return ""

    emails = set()

    # The scraper separated multiple emails with ;
    for email in value.split(";"):

        email = email.strip().lower()

        if not email:
            continue

        # Remove mailto if present
        if email.startswith("mailto:"):
            email = email[7:]

        # Remove query parameters
        email = email.split("?")[0].strip()

        # Reject obvious fake/example addresses
        bad_emails = [
            "example@email.com",
            "test@email.com",
            "test@example.com",
            "email@example.com",
            "name@example.com",
            "your@email.com",
            "youremail@example.com",
            "info@example.com"
        ]

        if email in bad_emails:
            continue

        if "example.com" in email:
            continue

        if "xxxx" in email or "****" in email:
            continue

        # Basic email validation
        if re.match(
            r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$",
            email
        ):
            emails.add(email)

    return "; ".join(sorted(emails))


# ============================================================
# CLEAN PHONES
# ============================================================

def clean_phones(value):

    if not value:
        return ""

    phones = set()

    # Existing scraper separates multiple phones with ;
    for phone in value.split(";"):

        phone = phone.strip()

        if not phone:
            continue

        digits = re.sub(r"\D", "", phone)

        # Convert 91XXXXXXXXXX → XXXXXXXXXX
        if digits.startswith("91") and len(digits) == 12:
            digits = digits[2:]

        # Must be 10 digits
        if len(digits) != 10:
            continue

        # Indian mobile numbers
        if digits[0] not in "6789":
            continue

        # Reject repeated/fake numbers
        if len(set(digits)) == 1:
            continue

        # Reject obvious dummy patterns
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
            continue

        phones.add("+91 " + digits)

    return "; ".join(sorted(phones))


# ============================================================
# CLEAN LINKEDIN
# ============================================================

def clean_linkedin(value):

    if not value:
        return ""

    links = set()

    for link in value.split(";"):

        link = link.strip()

        if not link:
            continue

        link_lower = link.lower()

        # Ignore sharing URLs
        if "sharearticle" in link_lower:
            continue

        if "linkedin.com/share" in link_lower:
            continue

        # Keep actual company/person profiles
        if (
            "linkedin.com/company/" in link_lower
            or "linkedin.com/in/" in link_lower
        ):
            links.add(link)

    return "; ".join(sorted(links))


# ============================================================
# CLASSIFY ERROR
# ============================================================

def classify_error(error):

    if not error:
        return ""

    error_lower = error.lower()

    if (
        "timeout" in error_lower
        or "timed out" in error_lower
        or "timeouterror" in error_lower
    ):
        return "TIMEOUT"

    if (
        "err_name_not_resolved" in error_lower
        or "name_not_resolved" in error_lower
        or "dns" in error_lower
    ):
        return "DNS_ERROR"

    if (
        "err_connection" in error_lower
        or "connection" in error_lower
    ):
        return "CONNECTION_ERROR"

    if (
        "err_http" in error_lower
        or "http_response" in error_lower
        or "http" in error_lower
    ):
        return "HTTP_ERROR"

    if (
        "ssl" in error_lower
        or "certificate" in error_lower
    ):
        return "SSL_ERROR"

    return "OTHER_ERROR"


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 70)
    print("NAGPUR STARTUP DATA CLEANER")
    print("=" * 70)


    # --------------------------------------------------------
    # CHECK INPUT
    # --------------------------------------------------------

    if not os.path.exists(INPUT_FILE):

        print()
        print("ERROR: Input file not found:")
        print(INPUT_FILE)

        return


    # --------------------------------------------------------
    # READ CSV
    # --------------------------------------------------------

    with open(
        INPUT_FILE,
        "r",
        newline="",
        encoding="utf-8-sig"
    ) as file:

        reader = csv.DictReader(file)

        rows = list(reader)

        fieldnames = reader.fieldnames


    print()
    print(
        "Rows loaded:",
        len(rows)
    )


    # --------------------------------------------------------
    # ADD NEW COLUMNS
    # --------------------------------------------------------

    output_fields = list(fieldnames)

    new_columns = [
        "cleanedEmail",
        "cleanedPhone",
        "cleanedLinkedIn",
        "errorType"
    ]

    for column in new_columns:

        if column not in output_fields:
            output_fields.append(column)


    # --------------------------------------------------------
    # STATISTICS
    # --------------------------------------------------------

    status_counter = Counter()
    error_counter = Counter()

    email_count = 0
    phone_count = 0
    linkedin_count = 0


    cleaned_rows = []
    error_rows = []


    # --------------------------------------------------------
    # PROCESS EACH ROW
    # --------------------------------------------------------

    for row in rows:

        # Clean contact data
        cleaned_email = clean_emails(
            row.get("scrapedEmail", "")
        )

        cleaned_phone = clean_phones(
            row.get("scrapedPhone", "")
        )

        cleaned_linkedin = clean_linkedin(
            row.get("scrapedLinkedIn", "")
        )


        # Error classification
        status = (
            row.get("scrapeStatus", "")
            .strip()
            .upper()
        )

        error = (
            row.get("scrapeError", "")
            .strip()
        )

        error_type = classify_error(error)


        # Add cleaned columns
        row["cleanedEmail"] = cleaned_email
        row["cleanedPhone"] = cleaned_phone
        row["cleanedLinkedIn"] = cleaned_linkedin
        row["errorType"] = error_type


        # Statistics
        status_counter[status] += 1

        if error_type:
            error_counter[error_type] += 1

        if cleaned_email:
            email_count += 1

        if cleaned_phone:
            phone_count += 1

        if cleaned_linkedin:
            linkedin_count += 1


        cleaned_rows.append(row)


        # Save errors separately
        if status == "ERROR":
            error_rows.append(row)


    # ========================================================
    # WRITE CLEANED CSV
    # ========================================================

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

        writer.writerows(cleaned_rows)


    # ========================================================
    # WRITE ERROR CSV
    # ========================================================

    with open(
        ERROR_FILE,
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=output_fields
        )

        writer.writeheader()

        writer.writerows(error_rows)


    # ========================================================
    # DISPLAY REPORT
    # ========================================================

    print()
    print("=" * 70)
    print("CLEANING COMPLETE")
    print("=" * 70)

    print()
    print("Total rows:", len(rows))

    print()
    print("STATUS")
    print("-" * 40)

    for status, count in status_counter.items():

        print(
            f"{status}: {count}"
        )


    print()
    print("CONTACT DATA")
    print("-" * 40)

    print(
        "Rows with cleaned email:",
        email_count
    )

    print(
        "Rows with cleaned phone:",
        phone_count
    )

    print(
        "Rows with cleaned LinkedIn:",
        linkedin_count
    )


    print()
    print("ERROR TYPES")
    print("-" * 40)

    if error_counter:

        for error_type, count in error_counter.items():

            print(
                f"{error_type}: {count}"
            )

    else:

        print("No errors found.")


    print()
    print("ERROR ROWS:", len(error_rows))


    print()
    print("=" * 70)

    print("Cleaned file:")
    print(OUTPUT_FILE)

    print()
    print("Error/retry file:")
    print(ERROR_FILE)

    print("=" * 70)


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()