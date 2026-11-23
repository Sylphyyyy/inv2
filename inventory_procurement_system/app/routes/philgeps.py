import requests
from bs4 import BeautifulSoup
from flask import Blueprint, render_template, request, flash, session, redirect, url_for
import urllib.parse
import urllib3
import re

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

philgeps_bp = Blueprint('philgeps', __name__, url_prefix='/philgeps')

BASE_URL = "https://notices.philgeps.gov.ph/GEPSNONPILOT/Tender/SplashOpportunitiesSearchUI.aspx?menuIndex=3"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Connection': 'keep-alive',
}

@philgeps_bp.before_request
def require_login():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

def fetch_philgeps_aspnet_handshake(keyword=""):
    results = []
    if not keyword:
        return results

    session = requests.Session()
    session.headers.update(HEADERS)

    direct_search_url = f"https://notices.philgeps.gov.ph/GEPSNONPILOT/Tender/SplashOpportunitiesSearchUI.aspx?menuIndex=3&searchStr={urllib.parse.quote_plus(keyword)}"

    try:
        init_resp = session.get(BASE_URL, timeout=12, verify=False)

        if init_resp.status_code == 200:
            soup_init = BeautifulSoup(init_resp.text, 'html.parser')

            viewstate_elem = soup_init.find('input', id='__VIEWSTATE') or soup_init.find('input', attrs={'name': '__VIEWSTATE'})
            viewstate_gen_elem = soup_init.find('input', id='__VIEWSTATEGENERATOR') or soup_init.find('input', attrs={'name': '__VIEWSTATEGENERATOR'})
            event_val_elem = soup_init.find('input', id='__EVENTVALIDATION') or soup_init.find('input', attrs={'name': '__EVENTVALIDATION'})

            viewstate = viewstate_elem['value'] if viewstate_elem and 'value' in viewstate_elem.attrs else ''
            viewstate_gen = viewstate_gen_elem['value'] if viewstate_gen_elem and 'value' in viewstate_gen_elem.attrs else ''
            event_val = event_val_elem['value'] if event_val_elem and 'value' in event_val_elem.attrs else ''

            search_input_name = 'txtSearch'
            for inp in soup_init.find_all('input'):
                inp_name = inp.get('name', '')
                if 'search' in inp_name.lower() or 'txt' in inp_name.lower():
                    search_input_name = inp_name
                    break

            search_resp = session.get(direct_search_url, timeout=12, verify=False)

            if "GridItem" not in search_resp.text and "dgItem" not in search_resp.text and viewstate:
                post_payload = {
                    '__VIEWSTATE': viewstate,
                    '__VIEWSTATEGENERATOR': viewstate_gen,
                    '__EVENTVALIDATION': event_val,
                    search_input_name: keyword,
                    'btnSearch': 'Search'
                }
                search_resp = session.post(BASE_URL, data=post_payload, timeout=12, verify=False)

            if search_resp.status_code == 200:
                soup_results = BeautifulSoup(search_resp.text, 'html.parser')
                
                rows = soup_results.find_all('tr', class_=['GridItem', 'GridAltItem', 'dgItem', 'dgAltItem'])

                for row in rows:
                    cols = row.find_all('td')
                    if len(cols) < 2:
                        continue

                    link_tag = row.find('a', href=True)
                    if not link_tag:
                        continue

                    raw_title = link_tag.get_text(strip=True)
                    href = link_tag['href']

                    if href.startswith("http"):
                        direct_link = href
                    elif href.startswith("javascript:"):
                        direct_link = direct_search_url
                    else:
                        direct_link = f"https://notices.philgeps.gov.ph/GEPSNONPILOT/Tender/{href.lstrip('/')}"

                    # Extract Procuring Entity from row links or cell text patterns
                    procuring_entity = "N/A"
                    for col in cols:
                        for lk in col.find_all('a'):
                            lk_text = lk.get_text(strip=True)
                            if re.search(r'(PROVINCE OF|CITY OF|MUNICIPALITY OF|DEPARTMENT OF|BUREAU OF|OFFICE OF|UNIVERSITY|COLLEGE|HOSPITAL|DISTRICT)', lk_text, re.IGNORECASE):
                                if lk != link_tag: # Ensure it's not the main project title link
                                    procuring_entity = lk_text
                                    break
                        if procuring_entity != "N/A":
                            break

                    # Fallback: scan all column text for agency keywords if separate link wasn't found
                    if procuring_entity == "N/A":
                        for col in cols:
                            col_text = col.get_text(strip=True)
                            match = re.search(r'(PROVINCE OF [A-Za-z\s]+|CITY OF [A-Za-z\s]+|MUNICIPALITY OF [A-Za-z\s]+)', col_text, re.IGNORECASE)
                            if match:
                                procuring_entity = match.group(1).strip()
                                break

                    clean_title = re.sub(r'^\d{2}/\d{2}/\d{4}(\s+\d{2}:\d{2}\s+(AM|PM))?', '', raw_title).strip()
                    clean_title = re.sub(r'\s*,\s*PROVINCE OF.*$', '', clean_title, flags=re.IGNORECASE)
                    clean_title = re.sub(r'\s*,\s*CITY OF.*$', '', clean_title, flags=re.IGNORECASE)

                    # Pre-Bid / Closing Date Extraction
                    pre_bid_date = "N/A"
                    date_matches = []
                    for col in cols:
                        text = col.get_text(strip=True)
                        found = re.findall(r'\b\d{2}/\d{2}/\d{4}(?:\s+\d{1,2}:\d{2}(?:\s*[AP]M)?)?\b', text, re.IGNORECASE)
                        date_matches.extend(found)

                    if len(date_matches) >= 2:
                        pre_bid_date = date_matches[1]
                    elif len(date_matches) == 1:
                        pre_bid_date = date_matches[0]

                    if clean_title:
                        results.append({
                            'procuring_entity': procuring_entity,
                            'title': clean_title,
                            'pre_bid_date': pre_bid_date,
                            'url': direct_link
                        })

    except Exception as e:
        print(f"[ERROR] ASP.NET Handshake failed: {e}")

    return results

@philgeps_bp.route('/', methods=['GET'])
@philgeps_bp.route('/search', methods=['GET'])
def search():
    keyword = request.args.get('keyword', '').strip() or request.args.get('q', '').strip()
    opportunities = []

    if keyword:
        opportunities = fetch_philgeps_aspnet_handshake(keyword)
        if opportunities:
            flash(f"Loaded {len(opportunities)} live procurement notices for '{keyword}'.", "success")
        else:
            flash(f"No live records found for '{keyword}'.", "warning")

    return render_template('philgeps/search.html', opportunities=opportunities, keyword=keyword)