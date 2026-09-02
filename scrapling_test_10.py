import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import pandas as pd
from scrapling.fetchers import Fetcher


INPUT_FILE = "Nagpur_DPIIT_Missing_Startups_Diagnostic.csv"
OUTPUT_FILE = "02_scrapling_test_10.csv"

TEST_ROWS = 10


CONTACT_WORDS = [
    "contact",
    "contact-us",
    "contactus",
    "about",
    "about-us",
    "aboutus",
    "team",
    "company",
    "reach",
    "connect",
]


EMAIL_PATTERN = re.compile(
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
)

PHONE_PATTERN = re.compile(
    r"(?:\+91[\s-]?)?(?:\d[\s-]?){10,12}"
)


def clean(value):
    if not value:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def domain(url):
    try:
        return urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return ""


def extract_emails(text):
    emails = EMAIL_PATTERN.findall(text or "")

    cleaned = []

    for email in emails:
        email = email.lower().strip()

        if email not in cleaned:
            cleaned.append(email)

    return cleaned


def extract_phones(text):
    matches = PHONE_PATTERN.findall(text or "")

    phones = []

    for phone in matches:
        phone = clean(phone)

        if phone not in phones:
            phones.append(phone)

    return phones


def useful_link(href):
    if not href:
        return False

    href_lower = href.lower()

    return any(
        word in href_lower
        for word in CONTACT_WORDS
    )


def scrape_website(startup_name, website):

    result = {
        "startupName": startup_name,
        "website": website,
        "domain": domain(website),
        "email": "",
        "phone": "",
        "linkedin": "",
        "pagesChecked": "",
        "scrapeStatus": "",
        "errorType": "",
    }

    if not website:
        result["scrapeStatus"] = "NO_WEBSITE"
        return result

    website = website.strip()

    if not website.startswith(
        ("http://", "https://")
    ):
        website = "https://" + website

    pages = [website]
    checked = []

    emails = set()
    phones = set()
    linkedins = set()

    try:

        # ----------------------------------------------------
        # Homepage
        # ----------------------------------------------------

        page = Fetcher.get(
            website,
            impersonate="chrome",
            stealthy_headers=True,
            timeout=30,
        )

        checked.append(website)

        html_text = clean(
            page.get_text()
        )

        emails.update(
            extract_emails(html_text)
        )

        phones.update(
            extract_phones(html_text)
        )

        # ----------------------------------------------------
        # Find useful internal links
        # ----------------------------------------------------

        links = page.css(
            "a::attr(href)"
        ).getall()

        for href in links:

            if not href:
                continue

            absolute = urljoin(
                website,
                href
            )

            # Stay on the same domain
            if domain(absolute) != domain(website):
                continue

            if useful_link(absolute):
                if absolute not in pages:
                    pages.append(absolute)

        # Maximum 5 pages for this test
        pages = pages[:5]

        # ----------------------------------------------------
        # Crawl useful pages
        # ----------------------------------------------------

        for url in pages[1:]:

            try:

                subpage = Fetcher.get(
                    url,
                    impersonate="chrome",
                    stealthy_headers=True,
                    timeout=30,
                )

                checked.append(url)

                text = clean(
                    subpage.get_text()
                )

                emails.update(
                    extract_emails(text)
                )

                phones.update(
                    extract_phones(text)
                )

                social_links = subpage.css(
                    "a::attr(href)"
                ).getall()

                for social in social_links:

                    if social and "linkedin.com" in social.lower():
                        linkedins.add(
                            social.strip()
                        )

            except Exception:
                continue

        # Also inspect homepage social links
        for href in links:

            if href and "linkedin.com" in href.lower():
                linkedins.add(
                    urljoin(website, href)
                )

        result["email"] = "; ".join(
            sorted(emails)
        )

        result["phone"] = "; ".join(
            sorted(phones)
        )

        result["linkedin"] = "; ".join(
            sorted(linkedins)
        )

        result["pagesChecked"] = "; ".join(
            checked
        )

        result["scrapeStatus"] = (
            "SUCCESS"
            if len(checked) > 0
            else "NO_PAGES"
        )

    except Exception as e:

        result["scrapeStatus"] = "ERROR"
        result["errorType"] = (
            type(e).__name__ + ": " + str(e)
        )

    return result


def main():

    folder = Path(__file__).resolve().parent

    input_path = folder / INPUT_FILE
    output_path = folder / OUTPUT_FILE

    if not input_path.exists():

        print("ERROR: Input file not found:")
        print(input_path)
        return

    df = pd.read_csv(input_path)

    print("=" * 65)
    print("SCRAPLING TEST")
    print("=" * 65)
    print()

    print(
        "The diagnostic file contains startup names, "
        "but no official websites."
    )

    print(
        "Therefore this test will demonstrate the "
        "website-crawling stage."
    )

    print()

    test = df.head(TEST_ROWS).copy()

    # We deliberately don't invent website URLs.
    # These will remain blank until the discovery stage
    # identifies and verifies a candidate.
    results = []

    for number, (_, row) in enumerate(
        test.iterrows(),
        start=1
    ):

        startup_name = clean(
            row["startupName"]
        )

        print(
            f"{number}/{len(test)}: "
            f"{startup_name}"
        )

        results.append(
            scrape_website(
                startup_name,
                ""
            )
        )

    output = pd.DataFrame(results)

    output.to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig"
    )

    print()
    print("=" * 65)
    print("TEST COMPLETE")
    print("=" * 65)
    print()
    print(
        f"Created: {output_path}"
    )


if __name__ == "__main__":
    main()