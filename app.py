#Required Imports
from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import asyncio
import threading
import os
import sys
import json
from datetime import datetime
from pathlib import Path
import csv
import io

# Ensure current directory is in sys.path for module imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Local module imports
from core import LinkedInScraper
from ranker import rank_sri_lankan_profiles, get_score_tier

# Flask App Initialization
app = Flask(__name__)
app.secret_key = os.urandom(24)
CORS(app)

scraper = None

# Background event loop for Playwright operations (Chronium processes)
_bg_loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
threading.Thread(target=_bg_loop.run_forever, daemon=True, name="playwright-loop").start()

# Helper function to run async coroutines in the background loop and wait for results
def run_async(coro, timeout: int = 300):
    future = asyncio.run_coroutine_threadsafe(coro, _bg_loop)
    return future.result(timeout=timeout)

#Main App - Client Portal
@app.route('/')
def index():
    return render_template('client.html')

#Admin App Dashboard
@app.route('/admin')
def admin_index():
    return render_template('index.html')

#SCrapper Initial
@app.route('/api/scraper/init', methods=['POST'])
def init_scraper():
    global scraper
    try:
        if scraper:
            try:
                run_async(scraper.close())
            except:
                pass
            scraper = None
        data = request.json or {}
        async def init():
            global scraper
            scraper = LinkedInScraper(
                headless=data.get('headless', False),
                browser_type=data.get('browser_type', 'chromium'),
                session_name=data.get('session_name', 'default')
            )
            await scraper.initialize()
            return {'success': True, 'message': 'Browser initialized'}
        result = run_async(init())
        return jsonify(result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

# Scrapper Login
@app.route('/api/scraper/login', methods=['POST'])
def login():
    global scraper
    if not scraper:
        return jsonify({'success': False, 'error': 'Not initialized'}), 400
    try:
        data = request.json
        email = data.get('email', '').strip()
        password = data.get('password', '')
        if not email or not password:
            return jsonify({'success': False, 'error': 'Email and password required'}), 400
        async def do_login():
            return await scraper.login(email, password)
        success = run_async(do_login())
        return jsonify({'success': success, 'message': 'Login successful!' if success else 'Login failed'})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

#Search through the scrapper
@app.route('/api/scraper/search', methods=['POST'])
def search():
    global scraper
    if not scraper or not scraper.is_authenticated:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    try:
        data = request.json
        first_name = data.get('first_name', '').strip()
        last_name = data.get('last_name', '').strip()
        company = data.get('company', '').strip()
        max_results = data.get('max_results', 10)
        if not first_name and not last_name:
            return jsonify({'success': False, 'error': 'Name required'}), 400
        async def do_search():
            return await scraper.search_people(first_name, last_name, company, max_results)
        results = run_async(do_search())
        return jsonify({'success': True, 'results': results, 'total': len(results)})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

#Extract profile data through the scrapper
@app.route('/api/scraper/extract', methods=['POST'])
def extract():
    try:
        data = request.get_json(force=True)
        profile_url = data.get('profile_url', '').strip()
        if not profile_url:
            return jsonify({'success': False, 'error': 'Profile URL required'}), 400

        # Check Cache
        if ALL_PROFILES_JSON.exists():
            with open(ALL_PROFILES_JSON, 'r', encoding='utf-8') as f:
                try:
                    profiles = json.load(f)
                    for p in profiles:
                        if p.get('profile_url') == profile_url:
                            return jsonify({'success': True, 'cached': True, 'profile': p})
                except Exception:
                    pass

        # If not in cache, create a pending approval request
        import uuid
        request_id = str(uuid.uuid4())[:8].upper()
        
        with api_scrape_lock:
            data_store = {}
            if APPROVALS_FILE.exists():
                try:
                    with open(APPROVALS_FILE, 'r', encoding='utf-8') as f:
                        data_store = json.load(f)
                except Exception:
                    pass
            data_store[request_id] = {
                'api_key': request_id,
                'person_name': profile_url, # Storing URL as person_name so admin can click it
                'status': 'pending',
                'requested_at': datetime.now().isoformat(),
                'return_code': request_id
            }
            with open(APPROVALS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data_store, f, indent=2)

        return jsonify({'success': True, 'status': 'pending_approval', 'return_code': request_id, 'message': 'New profile requires Admin Approval.'})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

#Combined search and extract
@app.route('/api/scraper/search-and-extract', methods=['POST'])
def search_and_extract():
    try:
        data = request.json
        first_name = data.get('first_name', '').strip()
        last_name = data.get('last_name', '').strip()
        company = data.get('company', '').strip()
        max_profiles = data.get('max_profiles', 3)
        if not first_name and not last_name:
            return jsonify({'success': False, 'error': 'Name required'}), 400
            
        global scraper
        if not scraper or not scraper.is_authenticated:
            return jsonify({'success': False, 'error': 'Scraper not authenticated on backend.'}), 401
            
        async def do_search():
            return await scraper.search_people(first_name, last_name, company, max_profiles)
            
        search_results = run_async(do_search())
        
        cached_profiles = []
        pending_urls = []
        
        if ALL_PROFILES_JSON.exists():
            try:
                with open(ALL_PROFILES_JSON, 'r', encoding='utf-8') as f:
                    master_profiles = json.load(f)
                    master_urls = {p.get('profile_url'): p for p in master_profiles if p.get('profile_url')}
            except Exception:
                master_urls = {}
        else:
            master_urls = {}
            
        for res in search_results:
            url = res.get('profile_url')
            if url in master_urls:
                cached_profiles.append(master_urls[url])
            else:
                pending_urls.append(url)
                
        return_codes = []
        import uuid
        with api_scrape_lock:
            data_store = {}
            if APPROVALS_FILE.exists():
                try:
                    with open(APPROVALS_FILE, 'r', encoding='utf-8') as f:
                        data_store = json.load(f)
                except Exception:
                    pass
            for p_url in pending_urls:
                req_id = str(uuid.uuid4())[:8].upper()
                data_store[req_id] = {
                    'api_key': req_id,
                    'person_name': p_url,
                    'status': 'pending',
                    'requested_at': datetime.now().isoformat(),
                    'return_code': req_id
                }
                return_codes.append(req_id)
            with open(APPROVALS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data_store, f, indent=2)
                
        return jsonify({
            'success': True,
            'cached_profiles': cached_profiles,
            'pending_count': len(pending_urls),
            'return_codes': return_codes
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

#Get scrapper stats (Health and ETC)
@app.route('/api/scraper/stats', methods=['GET'])
def stats():
    global scraper
    if not scraper:
        return jsonify({'success': False, 'error': 'Not initialized'})
    try:
        async def get_stats():
            return await scraper.get_stats()
        stats_data = run_async(get_stats())
        return jsonify({'success': True, 'stats': stats_data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

#Close the scrapper and free resources (Chromium processes and ETC)
@app.route('/api/scraper/close', methods=['POST'])
def close():
    global scraper
    try:
        if scraper:
            run_async(scraper.close())
            scraper = None
        return jsonify({'success': True, 'message': 'Closed'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# Profile Ranking Endpoint [Still Under Construction - Not Fully Functional]
@app.route('/api/rank', methods=['POST'])
def rank_profiles():
    try:
        data = request.json or {}
        profiles = data.get('profiles', [])
        if not profiles:
            return jsonify({'success': False, 'error': 'No profiles provided'}), 400
        ranked = rank_sri_lankan_profiles(profiles)
        for item in ranked:
            item['tier'] = get_score_tier(item['scoring']['total_score'])
        return jsonify({
            'success': True,
            'total_input': len(profiles),
            'sri_lankan_count': len(ranked),
            'non_sri_lankan_filtered': len(profiles) - len(ranked),
            'ranked': ranked
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

#Data Export Endpoint (Supports JSON and CSV)
@app.route('/api/scraper/export', methods=['POST'])
def export_data():
    try:
        data = request.json
        export_payload = data.get('data', {})
        format_type = data.get('format', 'json')
        if not export_payload:
            return jsonify({'success': False, 'error': 'No data'}), 400
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        Path("exports").mkdir(exist_ok=True)
        if format_type == 'json':
            filename = f"linkedin_export_{timestamp}.json"
            filepath = Path("exports") / filename
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(export_payload, f, indent=2, ensure_ascii=False)
            return send_file(filepath, as_attachment=True, download_name=filename)
        elif format_type == 'csv':
            from flask import make_response
            filename = f"linkedin_export_{timestamp}.csv"
            output = io.StringIO()
            writer = csv.writer(output)
            profiles = export_payload.get('profiles', [])
            if not profiles:
                return jsonify({'success': False, 'error': 'No profiles in data'}), 400
            writer.writerow(['Name', 'About', 'Job Title', 'Company', 'Qualifications', 'Certifications', 'Profile URL', 'Scraped At'])
            for p in profiles:
                job = p.get('current_job', {}) or {}
                quals = '; '.join([f"{q.get('institution','')} - {q.get('degree','')}" for q in (p.get('qualifications') or [])])
                certs = '; '.join([f"{c.get('name','')} - {c.get('issuer','')}" for c in (p.get('certifications') or [])])
                writer.writerow([
                    p.get('name', ''),
                    (p.get('about', '') or '')[:2000],
                    job.get('title', ''),
                    job.get('company', ''),
                    quals,
                    certs,
                    p.get('profile_url', ''),
                    p.get('scraped_at', '')
                ])
            output.seek(0)
            resp = make_response(output.getvalue())
            resp.headers['Content-Type'] = 'text/csv; charset=utf-8'
            resp.headers['Content-Disposition'] = f'attachment; filename={filename}'
            return resp
        return jsonify({'success': False, 'error': 'Invalid format'}), 400
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

#Export text data as PDF (For Full Profile Text Export)
@app.route('/api/export-text-pdf', methods=['POST'])
def export_text_pdf():
    try:
        from fpdf import FPDF
        data = request.json
        text = data.get('text', '')
        if not text:
            return jsonify({'success': False, 'error': 'No text provided'}), 400
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        Path("exports").mkdir(exist_ok=True)
        filename = f"linkedin_full_profile_{timestamp}.pdf"
        filepath = Path("exports") / filename
        
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=10)
        for line in text.split('\n'):
            safe_line = line.encode('latin-1', 'replace').decode('latin-1')
            pdf.cell(0, 5, safe_line, ln=True)
        pdf.output(str(filepath))
        return send_file(filepath, as_attachment=True, download_name=filename)
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

# =====================================================================
# CLIENT API SYSTEM (Two-Step Background Scrape & 1-Min Retrieval Delay)
# =====================================================================

# Lock for thread safety on API registry files
api_scrape_lock = threading.Lock()

# Directory settings
API_SCRAPES_DIR = Path("exports/api_scrapes")
API_SCRAPES_DIR.mkdir(parents=True, exist_ok=True)
JOBS_FILE = API_SCRAPES_DIR / "jobs.json"
MASTER_CSV_FILE = API_SCRAPES_DIR / "scraped_profiles.csv"

# Persistent database settings
db_lock = threading.Lock()
ALL_PROFILES_JSON = Path("exports/all_scraped_profiles.json")
ALL_PROFILES_CSV = Path("exports/all_scraped_profiles.csv")

def save_to_persistent_db(profile):
    if not profile or 'error' in profile:
        return
        
    with db_lock:
        try:
            # Ensure parent directories exist
            ALL_PROFILES_JSON.parent.mkdir(parents=True, exist_ok=True)
            # 1. Update master JSON database
            profiles = []
            if ALL_PROFILES_JSON.exists():
                try:
                    with open(ALL_PROFILES_JSON, 'r', encoding='utf-8') as f:
                        profiles = json.load(f)
                except Exception:
                    profiles = []
                    
            # Avoid duplicate profile URLs in the master database (update if exists, otherwise append)
            url = profile.get('profile_url')
            updated = False
            for i, p in enumerate(profiles):
                if p.get('profile_url') == url:
                    profiles[i] = profile
                    updated = True
                    break
            if not updated:
                profiles.append(profile)
                
            with open(ALL_PROFILES_JSON, 'w', encoding='utf-8') as f:
                json.dump(profiles, f, indent=2, ensure_ascii=False)
                
            # 2. Rewrite master CSV database
            headers = [
                'name', 'headline', 'location', 'profile_picture', 'about', 
                'current_job', 'experience', 'qualifications', 'certifications', 
                'profile_url', 'scraped_at'
            ]
            
            with open(ALL_PROFILES_CSV, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                for p in profiles:
                    writer.writerow([
                        p.get('name', ''),
                        p.get('headline', ''),
                        p.get('location', ''),
                        p.get('profile_picture', ''),
                        p.get('about', ''),
                        json.dumps(p.get('current_job', {})),
                        json.dumps(p.get('experience', [])),
                        json.dumps(p.get('qualifications', [])),
                        json.dumps(p.get('certifications', [])),
                        p.get('profile_url', ''),
                        p.get('scraped_at', '')
                    ])
        except Exception as e:
            print(f"Error saving to master database: {e}")

# Initialize jobs.json if not present
if not JOBS_FILE.exists():
    with open(JOBS_FILE, 'w', encoding='utf-8') as f:
        json.dump({}, f)

def validate_api_key(api_key):
    if not api_key:
        return False
    try:
        keys_path = Path("api_keys.json")
        if keys_path.exists():
            with open(keys_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for item in data.get('api_keys', []):
                    if item.get('key') == api_key and item.get('status') == 'active':
                        return True
    except Exception as e:
        print(f"Error loading API keys: {e}")
    return False

def check_api_key():
    api_key = request.headers.get('X-API-Key')
    if not api_key:
        api_key = request.args.get('api_key')
    if not api_key and request.is_json:
        api_key = (request.json or {}).get('api_key')
    
    if not api_key or not validate_api_key(api_key):
        return None
    return api_key

def get_jobs_data():
    with api_scrape_lock:
        try:
            if JOBS_FILE.exists():
                with open(JOBS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
    return {}

def update_job_status(return_code, status, scraped_at=None, error=None):
    with api_scrape_lock:
        try:
            data = {}
            if JOBS_FILE.exists():
                with open(JOBS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            if return_code in data:
                data[return_code]['status'] = status
                if scraped_at:
                    data[return_code]['scraped_at'] = scraped_at
                if error:
                    data[return_code]['error'] = error
                with open(JOBS_FILE, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error updating job status: {e}")

def create_job(return_code, api_key, profile_url):
    with api_scrape_lock:
        try:
            data = {}
            if JOBS_FILE.exists():
                with open(JOBS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            data[return_code] = {
                'api_key': api_key,
                'profile_url': profile_url,
                'status': 'in_progress',
                'requested_at': datetime.now().isoformat(),
                'scraped_at': None,
                'error': None
            }
            with open(JOBS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error creating job: {e}")

def save_scraped_data_formats(profile, return_code):
    # Save JSON file
    json_path = API_SCRAPES_DIR / f"{return_code}.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)
        
    # Save CSV file (headers matching JSON keys)
    csv_path = API_SCRAPES_DIR / f"{return_code}.csv"
    headers = [
        'name', 'headline', 'location', 'profile_picture', 'about', 
        'current_job', 'experience', 'qualifications', 'certifications', 
        'profile_url', 'scraped_at', 'return_code'
    ]
    
    row_data = [
        profile.get('name', ''),
        profile.get('headline', ''),
        profile.get('location', ''),
        profile.get('profile_picture', ''),
        profile.get('about', ''),
        json.dumps(profile.get('current_job', {})),
        json.dumps(profile.get('experience', [])),
        json.dumps(profile.get('qualifications', [])),
        json.dumps(profile.get('certifications', [])),
        profile.get('profile_url', ''),
        profile.get('scraped_at', ''),
        return_code
    ]
    
    # Save individual CSV
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerow(row_data)
        
    # Append to master CSV file
    master_exists = MASTER_CSV_FILE.exists()
    with open(MASTER_CSV_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not master_exists:
            writer.writerow(headers)
        writer.writerow(row_data)

async def perform_background_scrape(profile_url, return_code):
    global scraper
    try:
        if not scraper:
            print("Auto-initializing scraper for background API request...")
            scraper = LinkedInScraper(headless=True, browser_type='chromium', session_name='default')
            await scraper.initialize()
            
        profile = await scraper.extract_profile(profile_url)
        
        if 'error' in profile:
            update_job_status(return_code, 'failed', error=profile['error'])
            print(f"Background scrape failed for {return_code}: {profile['error']}")
        else:
            scraped_at = datetime.now().isoformat()
            profile['scraped_at'] = scraped_at
            
            with api_scrape_lock:
                save_scraped_data_formats(profile, return_code)
                
            save_to_persistent_db(profile)
            update_job_status(return_code, 'completed', scraped_at=scraped_at)
            print(f"Background scrape succeeded for {return_code}")
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        update_job_status(return_code, 'failed', error=str(e))
        print(f"Background scrape exception for {return_code}: {e}")

async def perform_background_scrape_by_name(person_name, return_code, api_key):
    global scraper
    try:
        if not scraper:
            print("Auto-initializing scraper for background name-based request...")
            scraper = LinkedInScraper(headless=True, browser_type='chromium', session_name='default')
            await scraper.initialize()
            
        if person_name.startswith('http'):
            profile_url = person_name
            print(f"Direct URL provided: {profile_url}. Starting extraction...")
        else:
            print(f"Searching for person: '{person_name}'")
            results = await scraper.search_people(person_name, '', max_results=1, force_search=True)
            if not results:
                error_msg = f"No profile found for name: {person_name}"
                update_job_status(return_code, 'failed', error=error_msg)
                print(error_msg)
                return
                
            profile_url = results[0]['profile_url']
            print(f"Found profile URL for {person_name}: {profile_url}. Starting extraction...")
        
        with api_scrape_lock:
            try:
                data = {}
                if JOBS_FILE.exists():
                    with open(JOBS_FILE, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                if return_code in data:
                    data[return_code]['profile_url'] = profile_url
                    with open(JOBS_FILE, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=2)
            except Exception as e:
                print(f"Error updating job profile_url: {e}")
                
        profile = await scraper.extract_profile(profile_url)
        
        if 'error' in profile:
            update_job_status(return_code, 'failed', error=profile['error'])
            print(f"Background scrape failed for {return_code}: {profile['error']}")
        else:
            scraped_at = datetime.now().isoformat()
            profile['scraped_at'] = scraped_at
            
            with api_scrape_lock:
                save_scraped_data_formats(profile, return_code)
                
            save_to_persistent_db(profile)
            update_job_status(return_code, 'completed', scraped_at=scraped_at)
            print(f"Background scrape succeeded for {return_code}")
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        update_job_status(return_code, 'failed', error=str(e))
        print(f"Background scrape exception for {return_code}: {e}")

# Route to request a scrape
@app.route('/api/client/scrape', methods=['POST'])
def client_scrape():
    api_key = check_api_key()
    if not api_key:
        return jsonify({'success': False, 'error': 'Invalid or missing API key'}), 401
        
    data = request.json or {}
    profile_url = data.get('profile_url', '').strip()
    return_code = data.get('return_code', '').strip()
    
    if not profile_url or not return_code:
        return jsonify({'success': False, 'error': 'profile_url and return_code are required'}), 400
        
    jobs = get_jobs_data()
    if return_code in jobs:
        status = jobs[return_code].get('status')
        if status in ['in_progress', 'completed']:
            return jsonify({
                'success': True,
                'message': f'Scrape job is already {status}',
                'return_code': return_code,
                'status': status
            })
            
    # Create new job registry entry
    create_job(return_code, api_key, profile_url)
    
    # Run scraping process on background thread
    asyncio.run_coroutine_threadsafe(perform_background_scrape(profile_url, return_code), _bg_loop)
    
    return jsonify({
        'success': True,
        'message': 'Scrape request received and queued in background.',
        'return_code': return_code,
        'status': 'in_progress'
    }), 202

# Route to retrieve scraped profile data
@app.route('/api/client/retrieve', methods=['GET', 'POST'])
def client_retrieve():
    # Support both GET query parameters and POST JSON body
    if request.method == 'POST':
        data = request.json or {}
        return_code = data.get('return_code', '').strip()
    else:
        return_code = request.args.get('return_code', '').strip()
        
    if not return_code:
        return jsonify({'success': False, 'error': 'return_code is required'}), 400
        
    jobs = get_jobs_data()
    if return_code not in jobs:
        # Check if it's still pending admin approval
        pending_approvals = {}
        with api_scrape_lock:
            if APPROVALS_FILE.exists():
                try:
                    with open(APPROVALS_FILE, 'r', encoding='utf-8') as f:
                        pending_approvals = json.load(f)
                except Exception:
                    pass
        if return_code in pending_approvals:
            return jsonify({
                'success': False,
                'status': 'pending',
                'message': 'Profile is pending Admin Approval.'
            })
        return jsonify({'success': False, 'error': 'No scrape request found for the provided return_code'}), 404
        
    job = jobs[return_code]
    
    status = job.get('status')
    if status == 'in_progress':
        return jsonify({
            'success': False,
            'status': 'in_progress',
            'message': 'Profile is still being scraped. Please try again later.'
        })

    elif status == 'failed':
        return jsonify({
            'success': False,
            'status': 'failed',
            'error': job.get('error', 'Unknown scraping error')
        })
    elif status == 'completed':
        # Enforce 1-minute retrieval delay policy from scrape completion time
        scraped_at_str = job.get('scraped_at')
        if not scraped_at_str:
            return jsonify({'success': False, 'error': 'Invalid job state (missing completion time)'}), 500
            
        scraped_time = datetime.fromisoformat(scraped_at_str)
        elapsed_seconds = (datetime.now() - scraped_time).total_seconds()
        
        if elapsed_seconds < 60:
            remaining = 60 - elapsed_seconds
            return jsonify({
                'success': False,
                'status': 'waiting_delay',
                'message': f'Scrape completed, but data cannot be retrieved yet. Under the 1-minute delay policy, you must wait another {int(remaining)} seconds.',
                'remaining_seconds': int(remaining)
            })
            
        # Load and return JSON profile data
        json_path = API_SCRAPES_DIR / f"{return_code}.json"
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                profile_data = json.load(f)
            return jsonify({
                'success': True,
                'status': 'completed',
                'profile': profile_data,
                'csv_url': f"/api/client/download/csv?return_code={return_code}"
            })
        except Exception as e:
            return jsonify({'success': False, 'error': f'Error loading profile data: {str(e)}'}), 500

# Route to download the specific CSV file
@app.route('/api/client/download/csv', methods=['GET'])
def client_download_csv():
    return_code = request.args.get('return_code', '').strip()
    if not return_code:
        return jsonify({'success': False, 'error': 'return_code is required'}), 400
        
    jobs = get_jobs_data()
    if return_code not in jobs:
        return jsonify({'success': False, 'error': 'No scrape request found for the provided return_code'}), 404
        
    job = jobs[return_code]
        
    status = job.get('status')
    if status != 'completed':
        return jsonify({'success': False, 'error': f'Cannot download CSV. Job is in state: {status}'}), 400
        
    # Enforce 1-minute retrieval delay policy for CSV download as well
    scraped_at_str = job.get('scraped_at')
    scraped_time = datetime.fromisoformat(scraped_at_str)
    elapsed_seconds = (datetime.now() - scraped_time).total_seconds()
    
    if elapsed_seconds < 60:
        remaining = 60 - elapsed_seconds
        return jsonify({
            'success': False,
            'status': 'waiting_delay',
            'error': f'Under the 1-minute delay policy, you must wait another {int(remaining)} seconds to download this CSV.'
        }), 403
        
    csv_path = API_SCRAPES_DIR / f"{return_code}.csv"
    if not csv_path.exists():
        return jsonify({'success': False, 'error': 'CSV file does not exist on disk'}), 404
        
    return send_file(csv_path, as_attachment=True, download_name=f"{return_code}.csv", mimetype='text/csv')

# Route to download the specific PDF file
@app.route('/api/client/download/pdf', methods=['GET'])
def client_download_pdf():
    return_code = request.args.get('return_code', '').strip()
    if not return_code:
        return jsonify({'success': False, 'error': 'return_code is required'}), 400
        
    jobs = get_jobs_data()
    if return_code not in jobs:
        return jsonify({'success': False, 'error': 'No scrape request found for the provided return_code'}), 404
        
    job = jobs[return_code]
        
    status = job.get('status')
    if status != 'completed':
        return jsonify({'success': False, 'error': f'Cannot download PDF. Job is in state: {status}'}), 400
        
    # Enforce 1-minute retrieval delay policy for PDF download as well
    scraped_at_str = job.get('scraped_at')
    scraped_time = datetime.fromisoformat(scraped_at_str)
    elapsed_seconds = (datetime.now() - scraped_time).total_seconds()
    
    if elapsed_seconds < 60:
        remaining = 60 - elapsed_seconds
        return jsonify({
            'success': False,
            'status': 'waiting_delay',
            'error': f'Under the 1-minute delay policy, you must wait another {int(remaining)} seconds to download this PDF.'
        }), 403
        
    # Load and generate PDF on the fly
    json_path = API_SCRAPES_DIR / f"{return_code}.json"
    if not json_path.exists():
        return jsonify({'success': False, 'error': 'Data file does not exist on disk'}), 404
        
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            p = json.load(f)
            
        from fpdf import FPDF
        
        text = f"PROFILE: {p.get('name', 'Unknown')}\n"
        text += f"URL: {p.get('profile_url', 'N/A')}\n"
        text += f"Headline: {p.get('headline', 'N/A')}\n"
        text += f"Location: {p.get('location', 'N/A')}\n\n"
        text += f"--- ABOUT ---\n{p.get('about', 'N/A')}\n\n"
        
        job_info = p.get('current_job', {}) or {}
        text += f"--- CURRENT JOB ---\n"
        text += f"Title: {job_info.get('title', 'N/A')}\n"
        text += f"Company: {job_info.get('company', 'N/A')}\n"
        text += f"Duration: {job_info.get('duration', 'N/A')}\n"
        text += f"Location: {job_info.get('location', 'N/A')}\n\n"
        
        text += f"--- EXPERIENCE ---\n"
        for exp in p.get('experience', []):
            text += f"- {exp.get('title', 'N/A')} at {exp.get('company', 'N/A')} ({exp.get('duration', 'N/A')})\n"
        text += "\n"
        
        text += f"--- QUALIFICATIONS ---\n"
        for q in p.get('qualifications', []):
            text += f"- {q.get('institution', 'N/A')} - {q.get('degree', 'N/A')} ({q.get('dates', 'N/A')})\n"
        text += "\n"
        
        text += f"--- CERTIFICATIONS ---\n"
        for c in p.get('certifications', []):
            text += f"- {c.get('name', 'N/A')} - {c.get('issuer', 'N/A')} ({c.get('date', 'N/A')})\n"
            
        pdf_path = API_SCRAPES_DIR / f"{return_code}.pdf"
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=10)
        for line in text.split('\n'):
            safe_line = line.encode('latin-1', 'replace').decode('latin-1')
            pdf.cell(0, 5, safe_line, ln=True)
        pdf.output(str(pdf_path))
        
        return send_file(pdf_path, as_attachment=True, download_name=f"{return_code}.pdf", mimetype='application/pdf')
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'success': False, 'error': f'Error generating PDF: {str(e)}'}), 500

# =====================================================================
# API APPROVALS FLOW & PERSONA BULK SCRAPER
# =====================================================================

APPROVALS_FILE = API_SCRAPES_DIR / "approvals.json"
if not APPROVALS_FILE.exists():
    with open(APPROVALS_FILE, 'w', encoding='utf-8') as f:
        json.dump({}, f)

def get_approvals_data():
    with api_scrape_lock:
        try:
            if APPROVALS_FILE.exists():
                with open(APPROVALS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
    return {}

# Client: Request verification/approval for API Key & Person Name
@app.route('/api/client/request-approval', methods=['POST'])
def client_request_approval():
    api_key = check_api_key()
    if not api_key:
        return jsonify({'success': False, 'error': 'Invalid or missing API key'}), 401
        
    data = request.json or {}
    person_name = data.get('person_name', '').strip()
    if not person_name:
        return jsonify({'success': False, 'error': 'person_name is required'}), 400
        
    with api_scrape_lock:
        try:
            data_store = {}
            if APPROVALS_FILE.exists():
                with open(APPROVALS_FILE, 'r', encoding='utf-8') as f:
                    data_store = json.load(f)
            
            data_store[api_key] = {
                'api_key': api_key,
                'person_name': person_name,
                'status': 'pending',
                'return_code': None,
                'requested_at': datetime.now().isoformat()
            }
            with open(APPROVALS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data_store, f, indent=2)
                
            return jsonify({'success': True, 'message': 'Approval request submitted successfully', 'status': 'pending'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

# Client: Check request approval status
@app.route('/api/client/check-approval', methods=['GET', 'POST'])
def client_check_approval():
    api_key = check_api_key()
    if not api_key:
        return jsonify({'success': False, 'error': 'Invalid or missing API key'}), 401
        
    approvals = get_approvals_data()
    if api_key not in approvals:
        return jsonify({'success': False, 'status': 'not_found', 'message': 'No approval request found for this API key'}), 404
        
    req = approvals[api_key]
    return jsonify({
        'success': True,
        'status': req.get('status'),
        'return_code': req.get('return_code'),
        'person_name': req.get('person_name')
    })

# Admin: List all approval requests
@app.route('/api/admin/approvals', methods=['GET'])
def admin_list_approvals():
    approvals = get_approvals_data()
    return jsonify({'success': True, 'approvals': list(approvals.values())})

# Admin: Approve a pending request and assign return code
@app.route('/api/admin/approve', methods=['POST'])
def admin_approve():
    data = request.json or {}
    api_key_to_approve = data.get('api_key', '').strip()
    return_code = data.get('return_code', '').strip()
    
    if not api_key_to_approve or not return_code:
        return jsonify({'success': False, 'error': 'api_key and return_code are required'}), 400
        
    with api_scrape_lock:
        try:
            data_store = {}
            if APPROVALS_FILE.exists():
                with open(APPROVALS_FILE, 'r', encoding='utf-8') as f:
                    data_store = json.load(f)
                    
            if api_key_to_approve not in data_store:
                return jsonify({'success': False, 'error': 'No request found for the provided API key'}), 404
                
            req = data_store[api_key_to_approve]
            
            # Update status and return code
            req['status'] = 'approved'
            req['return_code'] = return_code
            
            with open(APPROVALS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data_store, f, indent=2)
                
            # Create a job in jobs.json
            jobs_data = {}
            if JOBS_FILE.exists():
                with open(JOBS_FILE, 'r', encoding='utf-8') as f:
                    jobs_data = json.load(f)
            jobs_data[return_code] = {
                'api_key': api_key_to_approve,
                'profile_url': None,
                'person_name': req.get('person_name', ''),
                'status': 'in_progress',
                'requested_at': datetime.now().isoformat(),
                'scraped_at': None,
                'error': None
            }
            with open(JOBS_FILE, 'w', encoding='utf-8') as f:
                json.dump(jobs_data, f, indent=2)
                
            # Start background scraping process
            asyncio.run_coroutine_threadsafe(
                perform_background_scrape_by_name(req.get('person_name', ''), return_code, api_key_to_approve),
                _bg_loop
            )
                
            return jsonify({'success': True, 'message': f'Request approved. Return code {return_code} assigned.'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

# Admin: Scrape a requested person name using the active scraper session
@app.route('/api/admin/scrape-requested-name', methods=['POST'])
def admin_scrape_requested_name():
    global scraper
    if not scraper or not scraper.is_authenticated:
        return jsonify({'success': False, 'error': 'Scraper is not initialized or logged in. Please go to the Setup tab and configure it.'}), 400
        
    data = request.json or {}
    api_key_to_approve = data.get('api_key', '').strip()
    return_code = data.get('return_code', '').strip()
    person_name = data.get('person_name', '').strip()
    
    if not api_key_to_approve or not return_code or not person_name:
        return jsonify({'success': False, 'error': 'api_key, return_code, and person_name are required'}), 400
        
    # 1. Search for the person using active scraper
    try:
        async def do_search_and_extract():
            if person_name.startswith('http'):
                profile_url = person_name
            else:
                results = await scraper.search_people(person_name, '', max_results=1, force_search=True)
                if not results:
                    return {'success': False, 'error': f"No profile found for name: {person_name}"}
                profile_url = results[0]['profile_url']
                
            profile = await scraper.extract_profile(profile_url)
            return {'success': True, 'profile': profile, 'profile_url': profile_url}
            
        result = run_async(do_search_and_extract())
        if not result['success']:
            return jsonify({'success': False, 'error': result['error']}), 404
            
        profile = result['profile']
        profile_url = result['profile_url']
        
        if 'error' in profile:
            return jsonify({'success': False, 'error': profile['error']}), 500
            
        # 2. Save scraped data formats
        scraped_at = datetime.now().isoformat()
        profile['scraped_at'] = scraped_at
        
        with api_scrape_lock:
            save_scraped_data_formats(profile, return_code)
            
        save_to_persistent_db(profile)
        
        with api_scrape_lock:
            # 3. Create job in jobs.json
            jobs_data = {}
            if JOBS_FILE.exists():
                with open(JOBS_FILE, 'r', encoding='utf-8') as f:
                    jobs_data = json.load(f)
            jobs_data[return_code] = {
                'api_key': api_key_to_approve,
                'profile_url': profile_url,
                'person_name': person_name,
                'status': 'completed',
                'requested_at': datetime.now().isoformat(),
                'scraped_at': scraped_at,
                'error': None
            }
            with open(JOBS_FILE, 'w', encoding='utf-8') as f:
                json.dump(jobs_data, f, indent=2)
                
            # 4. Update approval in approvals.json
            data_store = {}
            if APPROVALS_FILE.exists():
                with open(APPROVALS_FILE, 'r', encoding='utf-8') as f:
                    data_store = json.load(f)
            if api_key_to_approve in data_store:
                data_store[api_key_to_approve]['status'] = 'approved'
                data_store[api_key_to_approve]['return_code'] = return_code
                with open(APPROVALS_FILE, 'w', encoding='utf-8') as f:
                    json.dump(data_store, f, indent=2)
                    
        return jsonify({'success': True, 'profile': profile})
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

# Admin: download master JSON database
@app.route('/api/admin/download-db/json', methods=['GET'])
def admin_download_db_json():
    if not ALL_PROFILES_JSON.exists():
        return jsonify({'success': False, 'error': 'Database is empty or does not exist yet.'}), 404
    try:
        return send_file(ALL_PROFILES_JSON, as_attachment=True, download_name="all_scraped_profiles.json", mimetype='application/json')
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Admin: download master CSV database
@app.route('/api/admin/download-db/csv', methods=['GET'])
def admin_download_db_csv():
    if not ALL_PROFILES_CSV.exists():
        return jsonify({'success': False, 'error': 'Database is empty or does not exist yet.'}), 404
    try:
        return send_file(ALL_PROFILES_CSV, as_attachment=True, download_name="all_scraped_profiles.csv", mimetype='text/csv')
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Admin: get all master database profiles
@app.route('/api/admin/db-profiles', methods=['GET'])
def admin_db_profiles():
    profiles = []
    if ALL_PROFILES_JSON.exists():
        with db_lock:
            try:
                with open(ALL_PROFILES_JSON, 'r', encoding='utf-8') as f:
                    profiles = json.load(f)
            except Exception as e:
                return jsonify({'success': False, 'error': f'Error reading database: {str(e)}'}), 500
    return jsonify({'success': True, 'profiles': profiles})

# Admin: destroy master database
@app.route('/api/admin/destroy-db', methods=['POST'])
def destroy_db():
    try:
        with db_lock:
            if ALL_PROFILES_JSON.exists():
                ALL_PROFILES_JSON.unlink()
            if ALL_PROFILES_CSV.exists():
                ALL_PROFILES_CSV.unlink()
        with api_scrape_lock:
            if JOBS_FILE.exists():
                JOBS_FILE.unlink()
            if APPROVALS_FILE.exists():
                APPROVALS_FILE.unlink()
            if API_SCRAPES_DIR.exists():
                for f in API_SCRAPES_DIR.glob('*'):
                    if f.is_file():
                        try:
                            f.unlink()
                        except Exception:
                            pass
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# Background Bulk scraping worker
async def perform_background_bulk_scrape(profile_urls, return_code):
    global scraper
    try:
        if not scraper:
            print("Auto-initializing scraper for background bulk API request...")
            scraper = LinkedInScraper(headless=True, browser_type='chromium', session_name='default')
            await scraper.initialize()
            
        scraped_profiles = []
        errors = []
        
        for idx, url in enumerate(profile_urls):
            print(f"Bulk scraping {idx+1}/{len(profile_urls)}: {url}")
            profile = await scraper.extract_profile(url)
            if 'error' in profile:
                errors.append(f"{url}: {profile['error']}")
            else:
                scraped_profiles.append(profile)
            
            if idx < len(profile_urls) - 1:
                await asyncio.sleep(4)
        
        scraped_at = datetime.now().isoformat()
        
        with api_scrape_lock:
            # Save JSON containing list of profiles
            json_path = API_SCRAPES_DIR / f"{return_code}.json"
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump({'profiles': scraped_profiles}, f, indent=2, ensure_ascii=False)
                
            # Save CSV file containing all scraped profiles
            csv_path = API_SCRAPES_DIR / f"{return_code}.csv"
            headers = [
                'name', 'headline', 'location', 'profile_picture', 'about', 
                'current_job', 'experience', 'qualifications', 'certifications', 
                'profile_url', 'scraped_at', 'return_code'
            ]
            
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                for profile in scraped_profiles:
                    profile['scraped_at'] = scraped_at
                    writer.writerow([
                        profile.get('name', ''),
                        profile.get('headline', ''),
                        profile.get('location', ''),
                        profile.get('profile_picture', ''),
                        profile.get('about', ''),
                        json.dumps(profile.get('current_job', {})),
                        json.dumps(profile.get('experience', [])),
                        json.dumps(profile.get('qualifications', [])),
                        json.dumps(profile.get('certifications', [])),
                        profile.get('profile_url', ''),
                        profile.get('scraped_at', ''),
                        return_code
                    ])
            
            # Append each to master CSV
            master_exists = MASTER_CSV_FILE.exists()
            with open(MASTER_CSV_FILE, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                if not master_exists:
                    writer.writerow(headers)
                for profile in scraped_profiles:
                    writer.writerow([
                        profile.get('name', ''),
                        profile.get('headline', ''),
                        profile.get('location', ''),
                        profile.get('profile_picture', ''),
                        profile.get('about', ''),
                        json.dumps(profile.get('current_job', {})),
                        json.dumps(profile.get('experience', [])),
                        json.dumps(profile.get('qualifications', [])),
                        json.dumps(profile.get('certifications', [])),
                        profile.get('profile_url', ''),
                        profile.get('scraped_at', ''),
                        return_code
                    ])
                    
        for profile in scraped_profiles:
            save_to_persistent_db(profile)
        
        if not scraped_profiles and errors:
            update_job_status(return_code, 'failed', error="All profile scrapes failed: " + "; ".join(errors))
        else:
            update_job_status(return_code, 'completed', scraped_at=scraped_at, error="; ".join(errors) if errors else None)
            
        print(f"Background bulk scrape completed for {return_code}")
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        update_job_status(return_code, 'failed', error=str(e))
        print(f"Background bulk scrape exception for {return_code}: {e}")

# Bulk Scraper Route (Branded as PERSONA)
@app.route('/api/persona/bulk-scrape', methods=['POST'])
def persona_bulk_scrape():
    api_key = check_api_key()
    if not api_key:
        return jsonify({'success': False, 'error': 'Invalid or missing API key'}), 401
        
    data = request.json or {}
    profile_urls = data.get('profile_urls', [])
    return_code = data.get('return_code', '').strip()
    
    if not profile_urls or not return_code:
        return jsonify({'success': False, 'error': 'profile_urls (list) and return_code are required'}), 400
        
    if not isinstance(profile_urls, list):
        return jsonify({'success': False, 'error': 'profile_urls must be a list of URLs'}), 400
        
    jobs = get_jobs_data()
    if return_code in jobs:
        status = jobs[return_code].get('status')
        if status in ['in_progress', 'completed']:
            return jsonify({
                'success': True,
                'message': f'Bulk scrape job is already {status}',
                'return_code': return_code,
                'status': status
            })
            
    with api_scrape_lock:
        try:
            data_store = {}
            if JOBS_FILE.exists():
                with open(JOBS_FILE, 'r', encoding='utf-8') as f:
                    data_store = json.load(f)
            data_store[return_code] = {
                'api_key': api_key,
                'profile_url': profile_urls[0] if profile_urls else "",
                'profile_urls': profile_urls,
                'is_bulk': True,
                'status': 'in_progress',
                'requested_at': datetime.now().isoformat(),
                'scraped_at': None,
                'error': None
            }
            with open(JOBS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data_store, f, indent=2)
        except Exception as e:
            return jsonify({'success': False, 'error': f'Error creating bulk job: {str(e)}'}), 500
            
    asyncio.run_coroutine_threadsafe(perform_background_bulk_scrape(profile_urls, return_code), _bg_loop)
    
    return jsonify({
        'success': True,
        'message': 'Bulk scrape request queued successfully in background.',
        'return_code': return_code,
        'status': 'in_progress'
    }), 202

# Bulk Retrieval Route (Branded as PERSONA)
@app.route('/api/persona/bulk-retrieve', methods=['GET', 'POST'])
def persona_bulk_retrieve():
    api_key = check_api_key()
    if not api_key:
        return jsonify({'success': False, 'error': 'Invalid or missing API key'}), 401
        
    if request.method == 'POST':
        data = request.json or {}
        return_code = data.get('return_code', '').strip()
    else:
        return_code = request.args.get('return_code', '').strip()
        
    if not return_code:
        return jsonify({'success': False, 'error': 'return_code is required'}), 400
        
    jobs = get_jobs_data()
    if return_code not in jobs:
        return jsonify({'success': False, 'error': 'No bulk scrape request found for the provided return_code'}), 404
        
    job = jobs[return_code]
    if job.get('api_key') != api_key:
        return jsonify({'success': False, 'error': 'Access denied: return_code belongs to a different API key'}), 403
        
    status = job.get('status')
    if status == 'in_progress':
        return jsonify({
            'success': False,
            'status': 'in_progress',
            'message': 'Bulk profile scraping is still in progress. Please try again later.'
        })
    elif status == 'failed':
        return jsonify({
            'success': False,
            'status': 'failed',
            'error': job.get('error', 'Unknown scraping error')
        })
    elif status == 'completed':
        scraped_at_str = job.get('scraped_at')
        if not scraped_at_str:
            return jsonify({'success': False, 'error': 'Invalid job state (missing completion time)'}), 500
            
        scraped_time = datetime.fromisoformat(scraped_at_str)
        elapsed_seconds = (datetime.now() - scraped_time).total_seconds()
        
        if elapsed_seconds < 60:
            remaining = 60 - elapsed_seconds
            return jsonify({
                'success': False,
                'status': 'waiting_delay',
                'message': f'Bulk scrape completed, but data cannot be retrieved yet. Under the 1-minute delay policy, you must wait another {int(remaining)} seconds.',
                'remaining_seconds': int(remaining)
            })
            
        json_path = API_SCRAPES_DIR / f"{return_code}.json"
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                bulk_data = json.load(f)
            return jsonify({
                'success': True,
                'status': 'completed',
                'profiles': bulk_data.get('profiles', []),
                'csv_url': f"/api/client/download/csv?api_key={api_key}&return_code={return_code}",
                'pdf_url': f"/api/client/download/pdf?api_key={api_key}&return_code={return_code}"
            })
        except Exception as e:
            return jsonify({'success': False, 'error': f'Error loading bulk profile data: {str(e)}'}), 500

# Run the Flask app
if __name__ == '__main__':
    print("Persona - LinkedIn Profile Scraper and Ranker")
    print("http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)