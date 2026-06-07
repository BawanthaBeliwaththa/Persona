# The Ultimate System Manual: The LinkedIn Scraper Application

Welcome to the ultimate, incredibly detailed manual for the LinkedIn Scraper system. If you have absolutely zero technical knowledge, you are in the right place! 

This document is written in the plainest, easiest-to-understand English possible. We will explain exactly what this system is, how every tiny moving part works together, every single process that happens behind the scenes, and provide a massive dictionary explaining every single piece of code. 

Grab a cup of coffee, and let's dive in!

---

## Part 1: Basic Concepts (What are we even talking about?)

Before we look at the system, let's understand three simple concepts:

1. **What is an API?** 
   Imagine you go to a restaurant. You don't walk into the kitchen to cook your own food. You talk to a waiter, give them your order, the waiter goes to the kitchen, gets your food, and brings it back to you. An **API** is a digital waiter. It takes requests from a user ("I want to see this profile"), goes to the backend system to get the work done, and brings the data back.
2. **What is a Scraper?**
   A scraper is a software robot. If you wanted to copy someone's work history from LinkedIn, you would open the page, highlight the text, copy it, and paste it into a Word document. A scraper does the exact same thing, but it does it invisibly, incredibly fast, and without complaining. 
3. **What is "Headless" Browsing?**
   When you use Google Chrome, you see a window on your screen. But computers don't actually need to "see" a window to browse the internet. A "headless" browser is a web browser running in the background with no visual window. Our robots use headless browsing so they can work quietly without interrupting whatever you are doing on your screen.

---

## Part 2: The Big Picture - How the Entire System is Organized

Imagine this entire system as a digital "company." Inside this company, there are a few main departments:

1. **The Admin Dashboard (The Manager's Office):** 
   This is a web page (`index.html`). Here, the human manager can manually control the robots. They can click a button to wake the robots up, log them into LinkedIn using a company account, and ask them to search for specific people. 
2. **The Client Portal (The Customer Service Desk):** 
   This is an automated system and webpage (`client.html`) where outside clients can send in a "support ticket" asking for a specific person's profile to be read. 
3. **The Scraper Robots (Playwright):** 
   These are the actual invisible workers. The system uses a tool called `Playwright` to create these robots. They literally open LinkedIn, type in the search bar, scroll all the way down the page to make sure everything loads, and copy all the text they see (like past jobs, schools, and skills).
4. **The Brain / The Web Server (`app.py`):** 
   This is the core of the entire operation. It is the boss. It listens to what the Admins and Clients want, translates those requests into instructions for the Robots, and makes sure the final data is stored safely in filing cabinets.

---

## Part 3: Step-by-Step Workflows (Every Single Action Explained)

Let's look at exactly what happens in the system during different real-world scenarios, step by agonizing step.

### Scenario A: A Client Wants to Scrape a Profile (The Automated API Flow)
*This is the main way outside businesses or software programs interact with your system without human intervention.*

1. **The Client Knocks on the Door:** 
   A client's computer sends a digital message over the internet to our Brain. The message says, "Please read the LinkedIn profile of John Doe at this URL." 
2. **Checking the Secret Password (API Key):** 
   The Brain doesn't just let anyone use the robots. The client must include a secret password (called an `API Key`). The Brain opens a file called `api_keys.json` to check if this password is real and active. If it's a fake password, the Brain slams the door and says "Access Denied."
3. **Taking a Ticket Number:** 
   If the password is correct, the client hands the Brain a unique ticket number for this request (called a `return_code`). 
4. **Writing on the Whiteboard:** 
   The Brain goes to a digital whiteboard called `jobs.json`. It writes down the ticket number and marks it as `in_progress`.
5. **The Quick Reply:** 
   Because reading a profile takes 10 to 20 seconds, the Brain immediately replies to the client: "Okay, I got your ticket. I'm putting a robot on it right now. Please come back later for the results." This prevents the client's computer from freezing or showing an endless spinning loading wheel.
6. **The Robot Goes to Work (Background Scrape):** 
   Quietly in the background, the Brain taps a robot on the shoulder. The robot invisibly opens a web browser, goes to John Doe's profile, scrolls down to load all the text, and reads his entire page. It throws away random posts he liked or commented on, keeping only his pure resume details (jobs, education, skills).
7. **Filing the Paperwork:** 
   Once the robot finishes, it takes all the information it found and saves it in three separate places to be extremely safe:
   - A unique data file (JSON format) just for that specific ticket number.
   - A unique spreadsheet (CSV format) just for that specific ticket number.
   - The giant master filing cabinet (`all_scraped_profiles.json` and `.csv`) so the company permanently remembers this profile forever.
8. **Erasing the Whiteboard:** 
   The Brain goes back to the `jobs.json` whiteboard, erases `in_progress`, and writes `completed`. It also writes down the exact time (down to the second) that the robot finished.
9. **The 1-Minute Rule (Client Comes Back):** 
   A few seconds later, the client comes back and asks, "Is my data ready?" The Brain looks at the whiteboard. **However, there is a strict company rule**: The client is legally not allowed to see the data until exactly 1 full minute has passed since the robot finished. 
   - If the client asks after 30 seconds, the Brain says: "The robot is done, but you are early. You must wait exactly 30 more seconds."
10. **Handing Over the Data:** 
    Once the 1-minute delay is totally over, the Brain finally hands the client the complete profile data and a link to download their neat spreadsheet.

### Scenario B: The Manual Admin Approval Process
*Sometimes, the system wants a human manager to approve scraping before a robot wastes time or risks getting caught by LinkedIn security.*

1. **A Request is Made:** 
   Someone uses the web dashboard to ask the system to read a profile.
2. **Checking the Master Memory:** 
   The Brain first checks the giant master filing cabinet (`all_scraped_profiles.json`). It says, "Have we ever read this profile before?" If the answer is yes, it just instantly hands over the old memory. Boom, done. No robot needed!
3. **Asking for Human Permission:** 
   If the profile has never been read before, the Brain does NOT send a robot out into the wild immediately. Instead, it creates a sticky note in a file called `approvals.json` and marks it as `pending`.
4. **The Waiting Game:** 
   The Brain replies to the user: "This is a brand new profile. An Admin manager must approve this request first." The Admin will see this pending sticky note on their private dashboard and can click "Approve" or "Deny". Only if they click "Approve" does the robot actually wake up to do the work.

### Scenario C: Ranking and Scoring Profiles (Finding the Best Candidates)
*When the system needs to find the "best" people from a giant list.*

1. **Feeding the Machine:** 
   The user hands the Brain a massive list of hundreds of scraped profiles and says, "Tell me who the best people are."
2. **The Sri Lankan Bouncer:** 
   The system acts as a nightclub bouncer. It looks at the "Location" and "Education" sections of every single profile. If the person has absolutely nothing to do with Sri Lanka, they are immediately thrown out of the list.
3. **Scoring the Survivors:** 
   For the remaining profiles, the system starts giving out mathematical points based on strict rules:
   - Does this person have over 500 connections? (+ Points!)
   - Have they worked at their current job for a long time? (+ Points!)
   - Do they have a lot of detailed work history? (+ Points!)
4. **Assigning a Grade:** 
   The Brain adds up all the points. If the score is very high, it slaps an 'A+' grade on the profile. If it's average, it gets a 'B'. If it's poor, it gets a 'C'.
5. **The Final Report:** 
   The system hands the user a beautifully sorted list, with all the top-tier 'A+' profiles right at the top, making the hiring manager's job incredibly easy.

---

## Part 4: How the System Stores Data (The Filing Cabinets)

The system is obsessed with organization. It keeps all of its permanent memories in a specific folder on the computer called `exports/`. Here is what is inside:

- **`all_scraped_profiles.json` and `all_scraped_profiles.csv`**: 
  This is the Master Brain. Think of it like the company's permanent vault. Every time a robot reads a new profile, all the data is copied into these two files. One is for computers to read easily (JSON), and the other is a spreadsheet for humans to open in Excel (CSV). If anyone ever asks for a profile that is already in the vault, the system just copies it from here instead of sending a robot out to do the work again.
- **`jobs.json`**: 
  This is the temporary to-do list for automated client requests. It tracks what the robots are currently doing, what they have finished, and exactly what time they finished it.
- **`approvals.json`**: 
  This is the manager's physical desk tray. It holds requests that are waiting for a human manager to say "yes" or "no" before a robot is allowed to go to work.
- **The `sessions/` folder**: 
  This is where the robots store their login cookies. When you log into Facebook on your phone, you don't have to log in again the next day because your phone saves a "cookie." This folder saves the robot's cookies so it can stay logged into LinkedIn for days or weeks without typing the password.

---

## Part 5: The Ultimate Dictionary (Every Single Function Explained)

*In programming, a "function" is a tiny mini-program that does one very specific job. Imagine a function like a specialized factory worker. One worker's only job is to put lids on bottles. Another worker's only job is to put labels on bottles. Together, they run a factory.*

*Below is an exhaustive, word-by-word explanation of every single function (worker) inside the system, explained so simply that a child could understand.*

### File: `session_manager.py` (The Memory Manager)
*This file's only job is to make sure the robot remembers its login details.*

- **`__init__` (Initialize)**: This is the setup worker. When the system turns on, this worker builds the physical folder on the computer where the login cookies will be kept safe. 
- **`save_session`**: This is the "Save Game" worker. It takes the fact that the robot is currently logged into LinkedIn and saves it into a file. 
- **`load_session`**: This is the "Load Game" worker. When the robot wakes up the next day, this worker grabs the saved file and injects it into the browser so the robot is instantly logged in without typing anything.
- **`list_sessions`**: This worker simply looks into the folder and reads out loud a list of all the different saved logins you currently have.
- **`delete_session`**: This is the trash collector. It deletes a saved login memory if the password changed, it expired, or you just don't need it anymore.

### File: `ranker.py` (The Profile Scorer)
*This file is the judge. It reads a profile and decides if it is good or bad.*

- **`_normalise`**: This is the cleaner. People type weirdly on the internet. Someone might type "  SoftWare   EnginEER ". This worker takes that text, forces it all into lowercase letters, and deletes extra spaces, turning it into "software engineer". This makes it so much easier for the computer to read.
- **`is_sri_lankan`**: This is the detective. It looks at a profile's location and the names of the schools they attended. It tries to find clues (like the word "Colombo") to guess if the person actually lives in Sri Lanka.
- **`detect_field_category`**: This worker is a categorizer. It reads a person's job title and tries to drop them into a bucket like "Finance", "Software", or "Marketing". 
- **`_parse_connections`**: This is the math translator. LinkedIn will say something like "500+ connections". Computers are bad at doing math with the plus symbol or the word "connections". This worker reads that sentence and just extracts the pure number `500`.
- **`_experience_quality_score`**: This worker is the experience rater. It looks at the person's job history. If they have had 5 jobs and worked for 10 years, they get a lot of points. If they have had 1 job for 2 months, they get very few points. 
- **`score_profile`**: This is the head judge. It gathers the points from the detective, the categorizer, and the experience rater, and adds them all up to create one final, total score number.
- **`rank_sri_lankan_profiles`**: This is the sorter. It takes a huge, messy list of 1,000 profiles. First, it throws out anyone who isn't from Sri Lanka. Then, it sorts the remaining people from the absolute highest score down to the absolute lowest score.
- **`get_score_tier`**: This is the teacher grading a test. It looks at the final score number and slaps a letter grade on it. Over 80 points? That's an 'A'. Under 20 points? That's a 'D'.

### File: `llm_parser.py` (The AI Text Reader)
*This file uses advanced Artificial Intelligence (like ChatGPT) to read confusing text.*

- **`__init__` (Initialize)**: This worker turns the AI on by giving it the secret password (API key) it needs to connect to the internet brain.
- **`parse_profile_html`**: This is the magic translator. Webpage code is incredibly messy and confusing. This worker takes that messy code, hands it to the AI, and says, "Please read this mess and just tell me the person's name, their job, and their school in a neat list."

### File: `core.py` (The Scraper Robot)
*This file directly controls the invisible web browser. It is the hands and eyes of the system.*

- **`__init__` (Initialize)**: This worker decides what kind of robot to build. Should the robot be invisible (headless) so it doesn't bother the user? Or should it be visible on the screen so the user can watch it work?
- **`initialize`**: This worker actually turns the browser on. It double-clicks the Google Chrome icon, basically.
- **`login`**: This worker is the typist. It literally tells the robot to move the mouse to the email box, type the email, move to the password box, type the password, and click the "Sign In" button.
- **`extract_profile`**: This worker is the main reader. It tells the robot to type a specific person's URL into the top bar, hit Enter, wait for the page to load, scroll all the way to the very bottom, and then highlight and copy all the text on the page.
- **`_strip_posts`**: This worker is the editor. When you read a LinkedIn profile, there are often sections showing "Posts this person liked". We don't care about that! This worker deletes that useless information so we only keep the person's actual resume details.
- **`_parse_section`**: This is a magnifying glass worker. It helps the robot find exactly where a specific paragraph begins and where it ends on the giant page of text.
- **`_parse_experience`**: This worker's only job is to read the details of ONE specific past job (like the title, the company name, and the dates worked).
- **`_parse_all_experiences`**: This worker reads the entire list of EVERY past job the person has ever had and bundles them all together.
- **`_parse_education`**: This worker looks specifically for universities, colleges, and high schools to see what degrees the person earned.
- **`_parse_certifications`**: This worker looks for any extra licenses, online courses, or certificates the person might have earned outside of normal school.
- **`search_people`**: This worker acts like a human using a search engine. It types a name (like "John Smith") into the LinkedIn search bar, hits Enter, and writes down the names of everyone who shows up on the results page.
- **`search_and_extract`**: This is a combo move. It tells the robot: "Search for John Smith, click on the very first result, and immediately read his entire profile." It does two steps in one smooth motion.
- **`get_stats`**: This worker takes the robot's pulse. It asks, "How many pages have you visited today? Are you feeling okay or are you frozen?"
- **`close`**: This is the night watchman. When all the work is completely done, it tells the robot to shut down the web browser, turn off the lights, and go to sleep.

### File: `app.py` (The Web Server / The Main Brain)
*This file is the central command station. It listens for clicks on the website and tells all the other workers what to do.*

- **`run_async`**: This is a special background manager. Normally, if a computer is thinking hard, the screen freezes. This manager forces the robots to do their heavy lifting in the shadows, so the main website stays lightning fast and never freezes for the user.
- **`index`**: This worker is a greeter. When an outside user visits the website, it hands them the "Client Portal" webpage.
- **`admin_index`**: This is the VIP greeter. It hands the "Admin Dashboard" webpage only to the managers.
- **`init_scraper`**: This is a big red start button. When a manager clicks it, it yells at the robot in `core.py` to wake up.
- **`login`**: A button that yells at the robot to type in the LinkedIn password.
- **`search`**: A button that asks the robot to go search for someone.
- **`extract`**: A button that asks the robot to read a specific profile. Because reading a profile takes a long time, it takes this request and puts it in the "Pending" desk tray for a human Admin to look at first.
- **`search_and_extract`**: A button to tell the robot to search for someone and read their profile immediately, skipping the line.
- **`stats`**: A button to ask the robot for its health report.
- **`close`**: A big red stop button to force the robot to shut down completely.
- **`rank_profiles`**: A button that takes a massive list of profiles, walks over to the Judge in `ranker.py`, and says "Please grade these from best to worst."
- **`export_data`**: A button that takes all the saved profiles inside the Brain and downloads them directly into your computer as a beautiful Excel spreadsheet.
- **`export_text_pdf`**: A button that creates a professional-looking PDF document out of a single person's profile, making it look like a printed resume.
- **`save_to_persistent_db`**: This is the vault guard. The absolute second a robot finishes reading a profile, this guard grabs the data and locks it permanently into the master filing cabinet so it is never, ever lost, even if the power goes out.
- **`validate_api_key`**: This is the security guard at the front door. It checks the secret password provided by an outside client to make sure it isn't fake or expired.
- **`check_api_key`**: This is the security guard's assistant. It looks through the client's pockets (their web request data) to find the secret password, and hands it to the main security guard to verify.
- **`get_jobs_data`**: This worker constantly reads the `jobs.json` whiteboard to see the list of all tasks that are currently working, finished, or failed.
- **`update_job_status`**: This worker holds an eraser. It changes the label on a task on the whiteboard (for example, erasing "working on it" and writing "finished").
- **`create_job`**: This worker holds a pen. It writes a brand new task ticket on the whiteboard when a client asks the robot to do work.
- **`save_scraped_data_formats`**: Once a profile is read, this worker meticulously organizes the information and saves it into a specific spreadsheet meant *only* for the person who asked for it.
- **`perform_background_scrape`**: This is the foreman. It stands behind the robot and directly commands it to read a profile quietly behind the scenes.
- **`perform_background_scrape_by_name`**: Similar to the foreman above, but it tells the robot to search for the person by their name first before reading their profile.
- **`client_scrape`**: This is the digital drop-box. It is the specific endpoint where outside software programs can drop off a request ticket without talking to a human.
- **`client_retrieve`**: This is the digital pickup window. It is the specific place where outside software programs come back later to pick up their finished profile data.
- **`client_download_csv`**: This is a special pickup window meant only for downloading finished data as an Excel spreadsheet.
