import csv
import os
import re
import time

from scrapling.fetchers import Fetcher, StealthyFetcher


# ============================================================
# PATHS
# ============================================================

BASE_FOLDER = r"C:\Users\ASUS\OneDrive\Desktop\Nagpur_Startup_Scraper"

INPUT_FILE = os.path.join(
    BASE_FOLDER,
    "Nagpur_DPIIT_Startups_Cleaned.csv"
)

OUTPUT_FILE = os.path.join(
    BASE_FOLDER,
    "Nagpur_Scrapling_DNS_Test.csv"
)


# ============================================================
# SETTINGS
# ============================================================

TEST_LIMIT = 10

HTTP_TIMEOUT = 30

BROWSER_TIMEOUT = 45


# ============================================================
# GET VALUE
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


# ============================================================
# DOMAIN CHECK
# ============================================================

def get_domain(url):

    url = url.strip()

    url = re.sub(
        r"^https?://",
        "",
        url,
        flags=re.I
    )

    return url.split("/")[0]


# ============================================================
# SCRAPE ONE WEBSITE
# ============================================================

def try_scrapling(url):

    if not url:
        return {
            "status": "NO_URL",
            "method": "",
            "final_url": "",
            "title": "",
            "text_sample": "",
            "error": ""
        }


    if not url.startswith("http"):

        url = "https://" + url


    print()
    print("-" * 70)

    print(
        "Trying:",
        url
    )


    # ========================================================
    # METHOD 1 — NORMAL SCRAPLING FETCHER
    # ========================================================

    try:

        print(
            "Method 1: Scrapling Fetcher..."
        )


        page = Fetcher.get(
            url,
            stealthy_headers=True,
            follow_redirects=True,
            retries=3
        )


        status = getattr(
            page,
            "status",
            None
        )


        print(
            "HTTP status:",
            status
        )


        if status and status < 400:

            final_url = getattr(
                page,
                "url",
                url
            )


            title = ""

            try:

                title = (
                    page.css(
                        "title::text"
                    ).get()
                    or ""
                ).strip()

            except:

                pass


            try:

                text = page.get_all_text(
                    ignore_tags=(
                        "script",
                        "style"
                    )
                )

                text = " ".join(
                    text
                    if isinstance(text, list)
                    else [str(text)]
                )

            except:

                text = ""


            print(
                "SUCCESS ✓"
            )

            print(
                "Final URL:",
                final_url
            )

            print(
                "Title:",
                title
            )


            return {
                "status": "SUCCESS",
                "method": "SCRAPLING_FETCHER",
                "final_url": final_url,
                "title": title,
                "text_sample": text[:1000],
                "error": ""
            }


    except Exception as e:

        print(
            "Fetcher failed:"
        )

        print(
            str(e)[:500]
        )


    # ========================================================
    # METHOD 2 — STEALTHY BROWSER
    # ========================================================

    try:

        print(
            "Method 2: Scrapling StealthyFetcher..."
        )


        page = StealthyFetcher.fetch(

            url,

            headless=False,

            timeout=BROWSER_TIMEOUT * 1000,

            network_idle=False,

            disable_resources=True,

            block_webrtc=True

        )


        status = getattr(
            page,
            "status",
            None
        )


        print(
            "Browser HTTP status:",
            status
        )


        final_url = getattr(
            page,
            "url",
            url
        )


        title = ""

        try:

            title = (
                page.css(
                    "title::text"
                ).get()
                or ""
            ).strip()

        except:

            pass


        try:

            text = page.get_all_text(
                ignore_tags=(
                    "script",
                    "style"
                )
            )

            text = " ".join(
                text
                if isinstance(text, list)
                else [str(text)]
            )

        except:

            text = ""


        if status is None or status < 500:

            print(
                "STEALTH SUCCESS ✓"
            )

            print(
                "Final URL:",
                final_url
            )

            print(
                "Title:",
                title
            )


            return {
                "status": "SUCCESS",
                "method": "SCRAPLING_STEALTHY",
                "final_url": final_url,
                "title": title,
                "text_sample": text[:1000],
                "error": ""
            }


    except Exception as e:

        print(
            "StealthyFetcher failed:"
        )

        print(
            str(e)[:500]
        )


    # ========================================================
    # FAILED
    # ========================================================

    print(
        "FAILED ✗"
    )


    return {
        "status": "ERROR",
        "method": "",
        "final_url": "",
        "title": "",
        "text_sample": "",
        "error": "Both Scrapling methods failed"
    }


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 70)

    print(
        "SCRAPLING DNS TEST"
    )

    print("=" * 70)


    if not os.path.exists(
        INPUT_FILE
    ):

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
    # ONLY DNS ERRORS
    # --------------------------------------------------------

    dns_rows = []

    for row in rows:

        status = (
            row.get(
                "STATUS",
                row.get(
                    "status",
                    ""
                )
            )
            or ""
        ).strip().upper()


        error_type = (
            row.get(
                "ERROR_TYPE",
                row.get(
                    "errorType",
                    ""
                )
            )
            or ""
        ).strip().upper()


        if (
            error_type == "DNS_ERROR"
            or status == "DNS_ERROR"
        ):

            dns_rows.append(
                row
            )


    print()
    print(
        "DNS rows found:",
        len(dns_rows)
    )


    test_rows = dns_rows[
        :TEST_LIMIT
    ]


    print(
        "Testing:",
        len(test_rows)
    )


    # --------------------------------------------------------
    # OUTPUT
    # --------------------------------------------------------

    fields = [

        "startupId",
        "startupName",

        "originalWebsite",

        "originalStatus",
        "originalErrorType",

        "scraplingStatus",
        "scraplingMethod",

        "finalURL",
        "title",

        "textSample",

        "error"

    ]


    with open(
        OUTPUT_FILE,
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as f:

        writer = csv.DictWriter(
            f,
            fieldnames=fields
        )

        writer.writeheader()


        # ====================================================
        # PROCESS
        # ====================================================

        for number, row in enumerate(
            test_rows,
            start=1
        ):

            name = get_value(
                row,
                [
                    "startupName",
                    "Startup Name",
                    "name",
                    "Name"
                ]
            )


            website = get_value(
                row,
                [
                    "WEBSITE",
                    "Website",
                    "website",
                    "originalWebsite",
                    "Original Website"
                ]
            )


            print()
            print("=" * 70)

            print(
                f"DNS TEST {number}/{len(test_rows)}"
            )

            print(
                "Startup:",
                name
            )

            print(
                "Website:",
                website
            )

            print("=" * 70)


            result = try_scrapling(
                website
            )


            writer.writerow({

                "startupId":
                    get_value(
                        row,
                        [
                            "startupId",
                            "Startup ID",
                            "id",
                            "ID"
                        ]
                    ),

                "startupName":
                    name,

                "originalWebsite":
                    website,

                "originalStatus":
                    row.get(
                        "STATUS",
                        row.get(
                            "status",
                            ""
                        )
                    ),

                "originalErrorType":
                    row.get(
                        "ERROR_TYPE",
                        row.get(
                            "errorType",
                            ""
                        )
                    ),

                "scraplingStatus":
                    result["status"],

                "scraplingMethod":
                    result["method"],

                "finalURL":
                    result["final_url"],

                "title":
                    result["title"],

                "textSample":
                    result["text_sample"],

                "error":
                    result["error"]

            })


            # ------------------------------------------------
            # SAVE IMMEDIATELY
            # ------------------------------------------------

            f.flush()

            print()
            print(
                "RESULT SAVED ✓"
            )


            time.sleep(1)


    print()
    print("=" * 70)

    print(
        "SCRAPLING TEST COMPLETE"
    )

    print("=" * 70)

    print()
    print(
        "Output:"
    )

    print(
        OUTPUT_FILE
    )


if __name__ == "__main__":
    main()