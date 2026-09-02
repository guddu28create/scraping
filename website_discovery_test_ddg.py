import re
import time
from pathlib import Path
from urllib.parse import quote, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup


INPUT_FILE = "Nagpur_DPIIT_Missing_Startups_Diagnostic.csv"
OUTPUT_FILE = "01_website_discovery_test_10.csv"

TEST_ROWS = 10
RESULTS_PER_STARTUP = 8

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )
}


BAD_DOMAINS = {
    "google.com",
    "google.co.in",
    "youtube.com",
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "x.com",
    "twitter.com",
    "crunchbase.com",
    "tracxn.com",
    "zaubacorp.com",
    "tofler.in",
    "thecompanycheck.com",
    "indiamart.com",
    "justdial.com",
    "sulekha.com",
    "tradeindia.com",
    "exportersindia.com",
    "ambitionbox.com",
    "glassdoor.com",
    "glassdoor.co.in",
    "indeed.com",
    "startupindia.gov.in",
    "dpiit.gov.in",
}


def clean_text(text):
    if not text:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip()


def normalize_url(url):
    if not url:
        return ""

    url = url.strip()

    if url.startswith("//"):
        url = "https:" + url

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    return url


def get_domain(url):
    try:
        domain = urlparse(url).netloc.lower()
        return domain.replace("www.", "")
    except Exception:
        return ""


def is_bad_domain(url):
    domain = get_domain(url)

    return any(
        domain == bad or domain.endswith("." + bad)
        for bad in BAD_DOMAINS
    )


def score_candidate(startup_name, title, url, snippet):

    score = 0
    reasons = []

    name = startup_name.lower()
    title = title.lower()
    snippet = snippet.lower()
    domain = get_domain(url)

    generic = {
        "private", "limited", "pvt", "ltd",
        "llp", "opc", "company", "co",
        "and", "the"
    }

    words = {
        w for w in re.findall(r"[a-z0-9]+", name)
        if w not in generic and len(w) > 2
    }

    domain_text = domain.replace(".", " ").replace("-", " ")

    matches = sum(
        1 for word in words
        if word in domain_text
    )

    if matches >= 3:
        score += 45
        reasons.append("strong domain-name match")

    elif matches == 2:
        score += 30
        reasons.append("good domain-name match")

    elif matches == 1:
        score += 12
        reasons.append("partial domain-name match")

    title_matches = sum(
        1 for word in words
        if word in title
    )

    if title_matches >= 3:
        score += 25
        reasons.append("strong title match")

    elif title_matches >= 2:
        score += 15
        reasons.append("title match")

    business_terms = [
        "private limited",
        "pvt ltd",
        "llp",
        "company",
        "official website",
        "about us",
        "contact us",
    ]

    term_matches = sum(
        term in title + " " + snippet
        for term in business_terms
    )

    score += min(term_matches * 3, 12)

    if is_bad_domain(url):
        score -= 60
        reasons.append("directory/social domain")

    return max(score, 0), "; ".join(reasons)


def search_duckduckgo(query):

    url = (
        "https://html.duckduckgo.com/html/?q="
        + quote(query)
    )

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=30
        )

        print(f"    HTTP status: {response.status_code}")

        if response.status_code != 200:
            return []

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        results = []

        for result in soup.select(".result"):

            link = result.select_one(
                ".result__a"
            )

            if not link:
                continue

            href = link.get("href")

            if not href:
                continue

            title = clean_text(
                link.get_text(" ", strip=True)
            )

            snippet_element = result.select_one(
                ".result__snippet"
            )

            snippet = ""

            if snippet_element:
                snippet = clean_text(
                    snippet_element.get_text(
                        " ",
                        strip=True
                    )
                )

            results.append({
                "title": title,
                "url": normalize_url(href),
                "snippet": snippet,
            })

        return results[:RESULTS_PER_STARTUP]

    except Exception as e:

        print(f"    Search error: {e}")
        return []


def main():

    project_folder = Path(__file__).resolve().parent

    input_path = project_folder / INPUT_FILE
    output_path = project_folder / OUTPUT_FILE

    if not input_path.exists():

        print()
        print("ERROR: CSV not found:")
        print(input_path)
        return

    df = pd.read_csv(input_path)

    if "startupName" not in df.columns:

        print("ERROR: startupName column not found.")
        print(df.columns.tolist())
        return

    # Only startups without a website
    df = df[
        df["website"].isna()
        | (df["website"].astype(str).str.strip() == "")
    ].head(TEST_ROWS)

    print("=" * 70)
    print("DUCKDUCKGO WEBSITE DISCOVERY TEST")
    print("=" * 70)
    print()
    print(f"Testing {len(df)} startups")
    print()

    output = []

    for number, (_, row) in enumerate(
        df.iterrows(),
        start=1
    ):

        startup_name = clean_text(
            row["startupName"]
        )

        query = (
            f'"{startup_name}" '
            f'Nagpur official website'
        )

        print("-" * 70)
        print(f"{number}/{len(df)}: {startup_name}")
        print(f"Query: {query}")

        results = search_duckduckgo(query)

        print(
            f"Results found: {len(results)}"
        )

        if not results:

            output.append({
                "startupId": row.get(
                    "startupId", ""
                ),
                "startupName": startup_name,
                "searchQuery": query,
                "candidateRank": "",
                "candidateTitle": "",
                "candidateURL": "",
                "candidateDomain": "",
                "candidateSnippet": "",
                "candidateScore": 0,
                "scoreReason": "",
                "discoveryStatus": "NO_RESULTS",
            })

        else:

            for rank, result in enumerate(
                results,
                start=1
            ):

                score, reason = score_candidate(
                    startup_name,
                    result["title"],
                    result["url"],
                    result["snippet"]
                )

                if is_bad_domain(
                    result["url"]
                ):
                    status = "NON_OFFICIAL_DOMAIN"

                elif score >= 60:
                    status = "HIGH_PRIORITY_CANDIDATE"

                elif score >= 30:
                    status = "MEDIUM_PRIORITY_CANDIDATE"

                else:
                    status = "LOW_PRIORITY_CANDIDATE"

                output.append({
                    "startupId": row.get(
                        "startupId", ""
                    ),
                    "startupName": startup_name,
                    "searchQuery": query,
                    "candidateRank": rank,
                    "candidateTitle": result["title"],
                    "candidateURL": result["url"],
                    "candidateDomain": get_domain(
                        result["url"]
                    ),
                    "candidateSnippet": result["snippet"],
                    "candidateScore": score,
                    "scoreReason": reason,
                    "discoveryStatus": status,
                })

                print(
                    f"  {rank}. "
                    f"{result['url']} "
                    f"[{score}]"
                )

        # Be polite to the search service.
        time.sleep(3)

    result_df = pd.DataFrame(output)

    result_df.to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig"
    )

    print()
    print("=" * 70)
    print("COMPLETE")
    print("=" * 70)
    print()
    print(
        f"Created: {output_path}"
    )
    print(
        f"Rows: {len(result_df)}"
    )


if __name__ == "__main__":
    main()