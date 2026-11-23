import requests
from bs4 import BeautifulSoup

def fetch_philgeps_aspnet_handshake(keyword=None):
    """
    Performs an ASP.NET handshake with PhilGEPS, harvests session cookies 
    and viewstates, and optionally queries live notices using the keyword.
    """
    base_url = "https://www.philgeps.gov.ph"
    session = requests.Session()
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/png,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    try:
        # Step 1: Initial GET request to establish session and grab viewstates
        response = session.get(base_url, headers=headers, timeout=12)
        
        if response.status_code != 200:
            return {
                "status": "Offline",
                "status_code": response.status_code,
                "notices": []
            }

        soup = BeautifulSoup(response.text, 'html.parser')
        
        viewstate = soup.find('input', {'id': '__VIEWSTATE'})
        viewstate_gen = soup.find('input', {'id': '__VIEWSTATEGENERATOR'})
        event_val = soup.find('input', {'id': '__EVENTVALIDATION'})

        handshake_data = {
            "status": "Connected",
            "status_code": response.status_code,
            "cookies": session.cookies.get_dict(),
            "notices": []
        }

        # Step 2: If a keyword is provided, attempt live search payload submission
        if keyword:
            # Preparing form payload for ASP.NET postback search
            payload = {
                "__VIEWSTATE": viewstate['value'] if viewstate else "",
                "__VIEWSTATEGENERATOR": viewstate_gen['value'] if viewstate_gen else "",
                "__EVENTVALIDATION": event_val['value'] if event_val else "",
                # Standard search button / keyword input field names used in portal structures
                "txtKeyword": keyword,
                "btnSearch": "Search"
            }
            
            # Post search request back to portal
            search_response = session.post(base_url, data=payload, headers=headers, timeout=12)
            
            if search_response.status_code == 200:
                search_soup = BeautifulSoup(search_response.text, 'html.parser')
                
                # Parse results table rows (adjusting selector based on typical portal grid structures)
                parsed_notices = []
                rows = search_soup.select('table tr') # Fallback generic row selector
                
                for row in rows[1:10]: # Limit to top 10 results
                    cols = row.find_all('td')
                    if len(cols) >= 3:
                        parsed_notices.append({
                            "title": cols[0].get_text(strip=True),
                            "reference_no": cols[1].get_text(strip=True),
                            "closing_date": cols[2].get_text(strip=True)
                        })
                
                handshake_data["notices"] = parsed_notices

        return handshake_data

    except requests.exceptions.RequestException as e:
        return {
            "status": "Error",
            "error": str(e),
            "notices": []
        }