"""
Shared query utilities — parsing, sanitization, helpers.

Used by both MCP tools (core_tools_v2) and FastAPI DataService.
"""

import re
import unicodedata
from datetime import datetime, timedelta
from typing import Optional, List


def sanitize_text(text) -> str:
    """Clean illegal characters for safe JSON/markdown output."""
    if text is None:
        return "N/A"
    text = str(text)
    text = text.encode('utf-8', 'ignore').decode('utf-8')
    text = ''.join(
        char for char in text
        if unicodedata.category(char)[0] != 'C' or char in '\n\t\r'
    )
    text = text.replace('\x00', '').replace('|', ' ').replace('\n', ' ')
    return text.strip()


def parse_time_hint(time_hint: Optional[str]) -> tuple[str, str]:
    """Parse time hint into (start_date, end_date) strings."""
    end = datetime.now().date()

    if not time_hint:
        start = end - timedelta(days=7)
    elif time_hint == 'today':
        start = end
    elif time_hint == 'yesterday':
        start = end - timedelta(days=1)
        end = start
    elif time_hint == 'this_week':
        start = end - timedelta(days=7)
    elif time_hint == 'this_month':
        start = end - timedelta(days=30)
    elif len(time_hint) == 4 and time_hint.isdigit():
        start = datetime.strptime(time_hint + "-01-01", '%Y-%m-%d').date()
        end = datetime.strptime(time_hint + "-12-31", '%Y-%m-%d').date()
    elif len(time_hint) == 7:
        start = datetime.strptime(time_hint + "-01", '%Y-%m-%d').date()
        end = (start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    else:
        try:
            start = datetime.strptime(time_hint, '%Y-%m-%d').date()
            end = start
        except Exception:
            start = end - timedelta(days=7)

    return start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d')


def parse_region_input(region_input: str) -> list[str]:
    """Smart parse region input for index-friendly queries."""
    region = region_input.strip()
    results: set[str] = set()

    cn_to_en = {
        'Washington': ['Washington', 'DC'],
        'New York': ['New York', 'NYC'],
        'Los Angeles': ['Los Angeles', 'LA'],
        'zhiaddbrother': ['Chicago'],
        'xiusiton': ['Houston'],
        'oldGolden Hill': ['San Francisco', 'SF'],
        'westyamap': ['Seattle'],
        'waveshidun': ['Boston'],
        'maiasecret': ['Miami'],
        'reachpullsi': ['Dallas'],
        'aositin': ['Austin'],
        'Philadelphia': ['Philadelphia'],
        'Atlantabig': ['Atlanta'],
        'Denver': ['Denver'],
        'Phoenix': ['Phoenix'],
        'Detroit': ['Detroit'],
        'UScountry': ['United States', 'USA', 'US'],
        'incountry': ['China', 'CHN', 'CN'],
        'yingcountry': ['United Kingdom', 'UK', 'GBR', 'GB'],
        'methodcountry': ['France', 'FRA', 'FR'],
        'virtuecountry': ['Germany', 'DEU', 'DE'],
        'daythis': ['Japan', 'JPN', 'JP'],
        'Rusiasi': ['Russia', 'RUS', 'RU'],
        'addnabig': ['Canada', 'CAN', 'CA'],
        'mowestbrother': ['Mexico', 'MEX', 'MX'],
        'printdegree': ['India', 'IND', 'IN'],
        'aobiglia': ['Australia', 'AUS', 'AU'],
        'bawest': ['Brazil', 'BRA', 'BR'],
        'ineast': ['Middle East', 'Mideast'],
        'Europe': ['Europe', 'European'],
        'Asia': ['Asia', 'Asian'],
        'non-continent': ['Africa', 'African'],
        'virtuestate': ['Texas', 'TX'],
        'Texasi': ['Texas', 'TX'],
        'addstate': ['California', 'CA'],
        'addlifornia': ['California', 'CA'],
        'fostate': ['Florida', 'FL'],
        'foroherereach': ['Florida', 'FL'],
        'binstate': ['Pennsylvania', 'PA'],
        'binximethodvania': ['Pennsylvania', 'PA'],
        'Illinois': ['Illinois', 'IL'],
        'Ohio': ['Ohio', 'OH'],
        'secretxieroot': ['Michigan', 'MI'],
        'Georgia': ['Georgia', 'GA'],
        'northcard': ['North Carolina', 'NC'],
        'southcard': ['South Carolina', 'SC'],
        'Virgivania': ['Virginia', 'VA'],
        'maherelan': ['Maryland', 'MD'],
        'New Jersey': ['New Jersey', 'NJ'],
        'machusetts': ['Massachusetts', 'MA'],
        'Arizothat': ['Arizona', 'AZ'],
        'Colopullmulti': ['Colorado', 'CO'],
        'Utah': ['Utah', 'UT'],
        'withinhuareach': ['Nevada', 'NV'],
        'Oregon': ['Oregon', 'OR'],
        'Washingtonstate': ['Washington State', 'WA'],
        'xiathreatyi': ['Hawaii', 'HI'],
        'apullsiadd': ['Alaska', 'AK'],
    }

    if region in cn_to_en:
        results.update(cn_to_en[region])

    results.add(region)

    region_clean = re.sub(r'\s+(City|County|State)$', '', region, flags=re.IGNORECASE)
    if region_clean != region:
        results.add(region_clean)

    parts = re.split(r'[,\s]+', region)
    for part in parts:
        if part and len(part) > 1:
            results.add(part.strip())
            if part in cn_to_en:
                results.update(cn_to_en[part])

    us_states = {
        'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas',
        'CA': 'California', 'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware',
        'FL': 'Florida', 'GA': 'Georgia', 'HI': 'Hawaii', 'ID': 'Idaho',
        'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa', 'KS': 'Kansas',
        'KY': 'Kentucky', 'LA': 'Louisiana', 'ME': 'Maine', 'MD': 'Maryland',
        'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota', 'MS': 'Mississippi',
        'MO': 'Missouri', 'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada',
        'NH': 'New Hampshire', 'NJ': 'New Jersey', 'NM': 'New Mexico', 'NY': 'New York',
        'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio', 'OK': 'Oklahoma',
        'OR': 'Oregon', 'PA': 'Pennsylvania', 'RI': 'Rhode Island', 'SC': 'South Carolina',
        'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah',
        'VT': 'Vermont', 'VA': 'Virginia', 'WA': 'Washington', 'WV': 'West Virginia',
        'WI': 'Wisconsin', 'WY': 'Wyoming', 'DC': 'District of Columbia',
    }

    upper_region = region.upper()
    if upper_region in us_states:
        results.add(upper_region)
        results.add(us_states[upper_region])
        if upper_region == 'DC':
            results.add('Washington')

    return sorted(list(results))


def calculate_risk_level(intensity: float) -> str:
    if intensity > 7:
        return "extremehigh"
    elif intensity > 5:
        return "high"
    elif intensity > 3:
        return "medium"
    else:
        return "low"
