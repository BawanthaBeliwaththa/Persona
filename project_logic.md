# Persona: LinkedIn Profile Scraper and Ranker - Project Logic

## 1. Project Overview
"Persona" is a full-stack application built to automate the extraction and ranking of LinkedIn profiles, specifically tailored to identify and evaluate professionals based in **Sri Lanka**. The backend is built using Python with **Flask** for API routing and **Playwright** for asynchronous, headless browser automation to scrape LinkedIn. 

The core functionalities include:
1. **Automated Scraping:** Searching and extracting detailed LinkedIn profile data (Experience, Education, Skills, About, etc.) while bypassing basic bot detection.
2. **Profile Ranking:** Scoring profiles based on completeness and industry relevance, filtered strictly for Sri Lankan locations.
3. **Data Export:** Allowing users to export scraped data to JSON, CSV, or PDF formats.

---

## 2. Core Components

### A. `app.py` (API Gateway & Server)
The entry point of the application. It initializes the Flask server and defines the RESTful endpoints for the frontend to interact with the scraper and ranker.
- **Asynchronous Execution:** Because Playwright operations are asynchronous and Flask handles synchronous requests, a background thread with an `asyncio` event loop is created (`_bg_loop`). The `run_async` helper safely executes coroutines in this loop.
- **Endpoints:**
  - `/api/scraper/init`: Initializes the Playwright browser context.
  - `/api/scraper/login`: Automates the LinkedIn login process.
  - `/api/scraper/search`: Searches for profiles by name/company.
  - `/api/scraper/extract`: Extracts data from a specific profile URL.
  - `/api/scraper/search-and-extract`: Combines search and extraction for the top results.
  - `/api/rank`: Takes extracted profiles and ranks them using the ranking logic.
  - `/api/scraper/export` & `/api/export-text-pdf`: Converts profile data into JSON, CSV, or PDF for download.

### B. `core.py` (The Scraping Engine)
Contains the `LinkedInScraper` class, which handles all browser automation using **Playwright**.
- **Initialization:** Launches a Chromium instance. It uses persistent contexts (saving data in `./browser_data`) to maintain sessions and bypasses bot detection using specific user agents and by disabling `webdriver` flags.
- **Data Extraction (`extract_profile`):**
  - Navigates to a profile and scrolls down repeatedly to load lazy-loaded elements.
  - Injects Javascript to extract basic fields (Name, Headline, Location, Profile Picture) from DOM selectors.
  - Extracts the `innerText` of the entire page to parse structured data natively.
- **Text Parsing:** 
  - `_strip_posts()`: Removes the "Activity" sections (user posts) that clutter the page text.
  - `_parse_experience()`, `_parse_education()`, `_parse_certifications()`: Custom string manipulation functions that parse chronological resume sections by identifying section headers and grouping lines into structured dictionaries.

### C. `ranker.py` (The Scoring & Ranking Algorithm)
Evaluates scraped profiles based on a weighted scoring model out of 150 points.
- **Geo-Filtering (`is_sri_lankan`):** Ensures only profiles mentioning Sri Lankan locations (e.g., Colombo, Kandy, SL) in their location, headline, or about sections are ranked.
- **Taxonomy Detection (`detect_field_category`):** Classifies the profile into industries (e.g., Software & IT, Finance, Marketing) by checking keywords against their text data.
- **Scoring Breakdown:**
  - **Profile Strength (max 100 pts):** Points are awarded for having a headline, a detailed about section, the number and quality of job experiences, education history, skills, certifications, recommendations, and profile photos.
  - **Field-Match Followers (max 50 pts):** Uses the user's connection count combined with how densely their profile matches their detected industry field to calculate relevance.
- **Tiers:** Total scores are mapped to descriptive tiers (Elite: >120, Expert: >100, Strong: >80, Moderate: >60, Beginner: <60).

### D. `session_manager.py`
A utility module for saving and loading Playwright session cookies using `pickle`. 
- By persisting cookies to a local `sessions/` directory, the scraper avoids logging into LinkedIn repeatedly, reducing the risk of triggering CAPTCHAs or temporary account bans.

### E. `llm_parser.py`
An optional fallback parser that utilizes OpenAI's GPT models (e.g., `gpt-3.5-turbo`) to extract structured JSON data from unstructured raw HTML. It acts as an alternative if the native string parsing in `core.py` fails due to LinkedIn UI changes.

---

## 3. Standard Execution Flow

1. **Initialize & Authenticate:** The user triggers `/api/scraper/init` to launch the browser. If a valid session exists, they are authenticated automatically. Otherwise, they use `/api/scraper/login`.
2. **Search:** The user sends a name or company to `/api/scraper/search`. The Playwright script navigates to LinkedIn Search, extracts the top profile URLs, and returns them.
3. **Extract:** Using the URLs, `/api/scraper/extract` navigates to each profile, scrolls to trigger lazy loading, and extracts both DOM elements and full page text. The text is parsed into structured objects (Experiences, Education, etc.).
4. **Rank:** The extracted JSON array is sent to `/api/rank`. The ranker filters out non-Sri Lankan profiles, scores the remaining ones out of 150 points based on completeness and industry relevance, and assigns a tier.
5. **Export:** The user can export the processed and ranked dataset to a CSV or JSON file via the export endpoints.

---

## 4. Key Technical Decisions
- **Playwright over Requests/BeautifulSoup:** LinkedIn heavily relies on React and client-side rendering. Playwright is required to execute Javascript, scroll for lazy loading, and mimic human interaction.
- **Native String Parsing vs HTML Selectors:** Instead of relying entirely on complex HTML classes (which LinkedIn changes frequently), `core.py` extracts the raw `innerText` of the page and parses it based on semantic English headers (e.g., "Experience", "Education"). This makes the scraper highly resilient to UI updates.
- **Async to Sync Bridge:** Using a daemon thread to maintain an `asyncio` loop allows Flask (which handles synchronous requests) to manage long-running Playwright browser sessions seamlessly.
