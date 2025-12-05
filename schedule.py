import requests
from bs4 import BeautifulSoup
import requests.exceptions
import json
import re
import os
from datetime import datetime, timedelta
from calendar import MONDAY

# --- Global Configurations (unchanged) ---
BASE_URL = "https://wol.jw.org"
INITIAL_MEETING_URL = "https://wol.jw.org/en/wol/meetings/r1/lp-e/"
EARLY_TERMINATION_MARKER = '</article>'
TIMEOUT = 15
SCHEDULES_DIR = "schedules"  # Directory where JSON files are saved
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; Konqueror/4.0; Linux) KHTML/4.0.80 (like Gecko)',
    'Accept': 'text/html,application/xhtml+xml'
}

# --- Parsing Configurations (unchanged) ---
VALID_CATEGORIES = {
    "TREASURES FROM GOD’S WORD",
    "APPLY YOURSELF TO THE FIELD MINISTRY",
    "LIVING AS CHRISTIANS"
}
duration_pattern = re.compile(r"\((\d+)\s*min\.?\)")


# --- Helper Functions for Initial Fetch & Link Discovery (unchanged) ---

def fetch_current_page_content(url):
    """Fetches the content using streaming, terminates early, and returns the HTML string."""
    print(f"STEP 1: Fetching overview content (optimized streaming) from: {url}")
    try:
        response = requests.get(url, stream=True, timeout=TIMEOUT, headers=HEADERS)
        response.raise_for_status()
        full_html_bytes = b""
        for chunk in response.iter_content(chunk_size=1024, decode_unicode=False):
            if chunk:
                full_html_bytes += chunk
                if EARLY_TERMINATION_MARKER.encode('utf-8') in full_html_bytes:
                    response.close()
                    break
        return full_html_bytes.decode('utf-8', errors='ignore')
    except requests.exceptions.RequestException as e:
        return f"Error fetching URL: {e}"
    except Exception as e:
        return f"An unexpected error occurred during streaming/extraction: {e}"


def _extract_life_and_ministry_link(html_content, section_title='Life and Ministry'):
    """Parses the HTML content to find the URL for the specific meeting section."""
    soup = BeautifulSoup(html_content, 'lxml')
    heading = soup.find('h2', string=section_title)
    if not heading:
        return f"Error: '{section_title}' section heading not found in downloaded content."
    nav_list = heading.find_next_sibling('ul', class_='directory navCard')
    if not nav_list:
        return f"Error: Navigation list for '{section_title}' not found."
    target_link = nav_list.find('a', class_='cardContainer')
    if target_link and 'href' in target_link.attrs:
        relative_url = target_link['href']
        return BASE_URL + relative_url
    else:
        return f"Error: Could not find the link within the '{section_title}' section."


def _extract_next_week_link(html_content):
    """Parses the HTML content to find the 'next week' navigation link."""
    soup = BeautifulSoup(html_content, 'lxml')
    target_link = soup.find('a', attrs={'aria-label': 'next week'})
    if target_link and 'href' in target_link.attrs:
        relative_url = target_link['href']
        return BASE_URL + relative_url
    else:
        return None


# --- Helper Functions for Parsing Details (unchanged) ---

def fetch_page_details(url):
    """Fetches the full details page content."""
    print(f"STEP 2: Fetching details from: {url}")
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.text


def extract_duration_int(text):
    """Extracts the duration integer from a string like '(5 min.)'"""
    m = duration_pattern.search(text)
    if m:
        return int(m.group(1))
    return None


def extract_meeting_parts(html):
    """Parses the detailed meeting HTML to extract schedule parts, applying filtering rules."""
    print("STEP 3: Extracting meeting parts...")
    soup = BeautifulSoup(html, "html.parser")
    parts = []
    current_category = None
    category_has_started = False
    week_title_tag = soup.find('h1', id='p1')
    week_title = week_title_tag.get_text(strip=True) if week_title_tag else "Unknown Week"
    article_tag = soup.find('article', id='article')
    if not article_tag:
        print("Warning: Could not find main article content.")
        return []

    for tag in article_tag.select("h2, h3"):
        if tag.name == "h2":
            text = tag.get_text(strip=True)
            if text and text in VALID_CATEGORIES:
                current_category = text
                category_has_started = True
            continue

        if tag.name == "h3":
            full_title = tag.get_text(" ", strip=True)
            duration_int = extract_duration_int(full_title)

            # Fallback for duration lookup (scrapes nearby text if not on the h3 tag)
            if duration_int is None:
                sibling = tag.find_next_sibling()
                for _ in range(6):
                    if not sibling:
                        break
                    # Check text content of sibling for duration
                    duration_int = extract_duration_int(sibling.get_text(" ", strip=True))
                    if duration_int is not None:
                        break
                    sibling = sibling.find_next_sibling()

            # Remove "(x min.)" from title
            title = duration_pattern.sub("", full_title).strip()

            if not title and duration_int is None:
                continue

            # --- FILTERING LOGIC ---
            title_upper = title.upper()

            # Exclusion Rule: If it contains "SONG" AND does NOT contain "COMMENTS", skip it.
            is_song_without_comments = "SONG" in title_upper and "COMMENTS" not in title_upper

            if is_song_without_comments:
                continue  # Skip standalone songs (like the mid-meeting break)

            # --- CLEANING LOGIC (for the bookend comments only) ---
            title_cleaned = title

            # Clean the title if it contains "Song" or "Prayer", to remove the bookend details
            if "SONG" in title_upper or "PRAYER" in title_upper:
                # Regex to remove "Song X and Prayer | " from the start or " | Song Y and Prayer" from the end
                title_cleaned = re.sub(
                    r"^(Song\s*\d+\s+and\s+Prayer\s*\|\s*)|(\s*\|\s*Song\s*\d+\s+and\s+Prayer)$",
                    "",
                    title,
                    flags=re.IGNORECASE
                ).strip()

            # Fallback to original title if the regex failed to find and clean anything
            if not title_cleaned:
                title_cleaned = title

            item = {
                "week_title": week_title,
                "category": current_category if category_has_started else None,
                "title": title_cleaned,
                "duration": duration_int
            }
            parts.append(item)

    return parts


# --- Core Logic for Date Parsing and File Saving (unchanged) ---

def get_monday_date(week_title):
    """
    Parses the week title to get the actual Monday's date.
    Returns a datetime.date object.
    """
    now = datetime.now()
    current_year = now.year
    is_abbreviated = False

    # 1. Full match (e.g., "September 2–8, 2024")
    full_match = re.search(r'([A-Za-z]+ \d{1,2}).*(\d{4})', week_title)

    if full_match:
        date_str = f"{full_match.group(1)}, {full_match.group(2)}"
        date_format = '%B %d, %Y'
    else:
        # 2. Abbreviated match (e.g., "DECEMBER 22-28")
        abbreviated_match = re.search(r'([A-Za-z]{3,}\.? \d{1,2})', week_title)
        is_abbreviated = True

        if abbreviated_match:
            date_str = f"{abbreviated_match.group(1)}, {current_year}"
            date_format = '%B %d, %Y' if len(abbreviated_match.group(1).split()[0]) > 3 else '%b %d, %Y'
        else:
            # print(f"Warning: Could not reliably parse any date from title: {week_title}")
            return None

    try:
        # Attempt to parse the date
        date_object = datetime.strptime(date_str, date_format)

        # Calculate the actual Monday date of that week.
        days_to_monday = date_object.weekday()
        if days_to_monday != MONDAY:  # MONDAY is 0
            date_object = date_object - timedelta(days=days_to_monday)

        # Handle Year Rollover for abbreviated titles
        if is_abbreviated and date_object.year != current_year:
            # If the date is Jan/Feb, and we are in Nov/Dec of the current year, it's next year
            if date_object.month < 3 and now.month > 10:
                date_object = date_object.replace(year=current_year + 1)
            # If the date is Nov/Dec, and we are in Jan/Feb of the current year, it's last year
            elif date_object.month > 10 and now.month < 3:
                date_object = date_object.replace(year=current_year - 1)

        # Return as a simple date object (without time components)
        return date_object.date()

    except ValueError as e:
        print(f"Error: Date parsing failed for string: {date_str}. Error: {e}")
        return None


def get_schedules_for_weeks(num_weeks=4):
    """
    Loops through specified number of weeks, fetching, parsing, and saving
    the schedule for each as a JSON file. Uses iterative date calculation.
    """
    current_overview_url = INITIAL_MEETING_URL
    saved_files_count = 0
    current_monday = None

    print(f"Starting scheduled extraction and saving for {num_weeks} weeks.")
    print("-------------------------------------------------------")

    try:
        if not os.path.exists(SCHEDULES_DIR):
            os.makedirs(SCHEDULES_DIR)
            print(f"Created directory: {SCHEDULES_DIR}")
    except OSError as e:
        print(f"FATAL ERROR: Could not create directory '{SCHEDULES_DIR}': {e}. Stopping.")
        return 0

    for i in range(num_weeks):

        print(f"\nProcessing WEEK {i + 1} from URL: {current_overview_url}")

        # --- Step 1 & 2: Fetch Overview and Extract Details URL ---
        html_overview = fetch_current_page_content(current_overview_url)

        if isinstance(html_overview, str) and html_overview.startswith("Error"):
            print(f"FATAL ERROR on overview page: {html_overview}. Stopping loop.")
            break

        details_url_or_error = _extract_life_and_ministry_link(html_overview)

        if "Error" in details_url_or_error:
            print(f"FATAL ERROR extracting details URL: {details_url_or_error}. Stopping loop.")
            break

        details_url = details_url_or_error

        # --- Step 3: Fetch Details Page and Extract Parts ---
        try:
            html_details = fetch_page_details(details_url)
            schedule_data = extract_meeting_parts(html_details)

            # --- Step 4: Determine Filename and Save JSON ---
            if schedule_data:
                week_title = schedule_data[0].get("week_title", "Unknown Week")

                if i == 0:
                    current_monday = get_monday_date(week_title)
                elif current_monday is not None:
                    current_monday += timedelta(days=7)

                if current_monday:
                    date_str = current_monday.strftime('%Y%m%d')

                    filename = os.path.join(SCHEDULES_DIR, f"{date_str}.json")

                    with open(filename, 'w', encoding='utf-8') as f:
                        json.dump(schedule_data, f, ensure_ascii=False, indent=2)

                    print(f"SUCCESS: Saved schedule for '{week_title}' (Monday: {date_str}) to file: {filename}")
                    saved_files_count += 1
                else:
                    print(f"SKIPPED: Could not determine starting date for week 1: {week_title}")


        except requests.exceptions.HTTPError as e:
            print(
                f"FATAL ERROR: HTTP request failed for details page ({details_url}). Status code: {e.response.status_code}")
            break
        except Exception as e:
            print(f"FATAL ERROR during details extraction/saving: {e}")
            break

        # --- Step 5: Find Next Week URL ---
        next_url = _extract_next_week_link(html_overview)

        if next_url is None:
            print("No 'next week' link found. Ending loop.")
            break

        current_overview_url = next_url

    return saved_files_count


if __name__ == "__main__":
    count = get_schedules_for_weeks(4)

    print("\n=======================================================")
    print(f"Processing complete. Successfully saved {count} schedule file(s) in the '{SCHEDULES_DIR}' directory.")
    print("=======================================================")