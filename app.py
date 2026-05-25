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

#Main App
@app.route('/')
def index():
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
    global scraper
    if not scraper or not scraper.is_authenticated:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    try:
        data = request.get_json(force=True)
        profile_url = data.get('profile_url', '').strip()
        if not profile_url:
            return jsonify({'success': False, 'error': 'Profile URL required'}), 400
        async def do_extract():
            return await scraper.extract_profile(profile_url)
        profile = run_async(do_extract())
        return jsonify({'success': True, 'profile': profile})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

#Combined search and extract
@app.route('/api/scraper/search-and-extract', methods=['POST'])
def search_and_extract():
    global scraper
    if not scraper or not scraper.is_authenticated:
        return jsonify({'success': False, 'error': 'Not authenticated'}), 401
    try:
        data = request.json
        first_name = data.get('first_name', '').strip()
        last_name = data.get('last_name', '').strip()
        company = data.get('company', '').strip()
        max_profiles = data.get('max_profiles', 3)
        if not first_name or not last_name:
            return jsonify({'success': False, 'error': 'Name required'}), 400
        async def do_both():
            return await scraper.search_and_extract(first_name, last_name, company, max_profiles)
        result = run_async(do_both())
        return jsonify(result)
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

# Run the Flask app
if __name__ == '__main__':
    print("Persona - LinkedIn Profile Scraper and Ranker")
    print("http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)