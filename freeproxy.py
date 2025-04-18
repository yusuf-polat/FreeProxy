print("""
██╗   ██╗██╗   ██╗███████╗██╗   ██╗███████╗    ██████╗  ██████╗ ██╗      █████╗ ████████╗
╚██╗ ██╔╝██║   ██║██╔════╝██║   ██║██╔════╝    ██╔══██╗██╔═══██╗██║     ██╔══██╗╚══██╔══╝
 ╚████╔╝ ██║   ██║███████╗██║   ██║█████╗      ██████╔╝██║   ██║██║     ███████║   ██║   
  ╚██╔╝  ██║   ██║╚════██║██║   ██║██╔══╝      ██╔═══╝ ██║   ██║██║     ██╔══██║   ██║   
   ██║   ╚██████╔╝███████║╚██████╔╝██║         ██║     ╚██████╔╝███████╗██║  ██║   ██║   
   ╚═╝    ╚═════╝ ╚══════╝ ╚═════╝ ╚═╝         ╚═╝      ╚═════╝ ╚══════╝╚═╝  ╚═╝   ╚═╝   
""")


import random
import time
from enum import Enum
from typing import List, Optional, Dict, Tuple

import requests
from lxml import html
from requests.exceptions import RequestException

class ProxyException(Exception):
    pass

class ProxyAnonymity(Enum):
    TRANSPARENT = 0
    ANONYMOUS = 1
    ELITE = 2

class Protocol(Enum):
    HTTP = 'http'
    HTTPS = 'https'
    SOCKS4 = 'socks4'
    SOCKS5 = 'socks5'

class FreeProxy:
    """
    Advanced free proxy scraper and validator with support for multiple sources,
    protocols, and advanced filtering options.
    
    Features:
    - 6 different proxy sources
    - HTTP/HTTPS/SOCKS support
    - Country/Region filtering
    - Anonymity levels
    - Google compatibility check
    - Speed/Timeout control
    - Proxy rotation
    - Connection validation
    - Custom test URLs
    """
    
    SOURCES = {
        'sslproxies': 'https://www.sslproxies.org/',
        'us-proxy': 'https://www.us-proxy.org/',
        'uk-proxy': 'https://free-proxy-list.net/uk-proxy.html',
        'socks-proxy': 'https://www.socks-proxy.net/',
        'anonymous-proxy': 'https://free-proxy-list.net/anonymous-proxy.html',
        'general': 'https://free-proxy-list.net/'
    }

    def __init__(
        self,
        countries: Optional[List[str]] = None,
        regions: Optional[List[str]] = None,
        protocol: Protocol = Protocol.HTTP,
        anonymity_level: ProxyAnonymity = ProxyAnonymity.TRANSPARENT,
        google_compatible: bool = False,
        timeout: float = 5.0,
        test_url: str = 'https://www.google.com',
        randomize: bool = True,
        max_proxies: int = 100,
        verify_ssl: bool = False,
        user_agent: Optional[str] = None
    ):
        self.countries = countries or []
        self.regions = regions or []
        self.protocol = protocol
        self.anonymity_level = anonymity_level
        self.google_compatible = google_compatible
        self.timeout = timeout
        self.test_url = test_url
        self.randomize = randomize
        self.max_proxies = max_proxies
        self.verify_ssl = verify_ssl
        self.user_agent = user_agent or 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
        
        self._session = requests.Session()
        self._session.headers.update({'User-Agent': self.user_agent})

    def get_proxy_list(self) -> List[Dict[str, str]]:
        """Retrieve and filter proxies from all sources"""
        proxies = []
        
        for source_name, source_url in self.SOURCES.items():
            try:
                page = self._session.get(source_url, timeout=self.timeout, verify=self.verify_ssl)
                page.raise_for_status()
                proxies += self._parse_source(page.content, source_name)
                time.sleep(1)  # Be polite
            except RequestException as e:
                continue
                
        return self._filter_proxies(proxies)[:self.max_proxies]

    def _parse_source(self, content: bytes, source_name: str) -> List[Dict[str, str]]:
        """Parse different proxy source formats"""
        tree = html.fromstring(content)
        rows = tree.xpath('//div[contains(@class, "fpl-list")]/table/tbody/tr')

        
        proxies = []
        for row in rows:
            try:
                cells = [cell.text_content().strip() for cell in row.xpath('./td')]
                proxy = self._parse_row(cells, source_name)
                if proxy:
                    proxies.append(proxy)
            except (IndexError, ValueError):
                continue
        return proxies

    def _parse_row(self, cells: List[str], source: str) -> Optional[Dict[str, str]]:
        """Parse individual proxy row with different formats"""
        proxy = {}
        
        try:
            if 'socks-proxy' in source:
                proxy = {
                    'ip': cells[0],
                    'port': cells[1],
                    'code': cells[2],
                    'country': cells[3],
                    'protocol': 'SOCKS5' if 'socks5' in cells[4].lower() else 'SOCKS4',
                    'anonymity': cells[5],
                    'https': 'yes' if 'socks' in cells[4].lower() else 'no',
                    'google': cells[6],
                    'last_checked': cells[7]
                }
            else:
                proxy = {
                    'ip': cells[0],
                    'port': cells[1],
                    'code': cells[2],
                    'country': cells[3],
                    'anonymity': cells[4],
                    'google': cells[5],
                    'https': cells[6],
                    'last_checked': cells[7],
                    'protocol': 'HTTPS' if cells[6] == 'yes' else 'HTTP'
                }
                
            proxy['region'] = self._detect_region(proxy['country'])
            return proxy
        except IndexError:
            return None

    def _filter_proxies(self, proxies: List[Dict]) -> List[Dict]:
        """Apply all filters to proxy list"""
        filtered = []
        
        for proxy in proxies:
            if self.countries and proxy['code'] not in self.countries:
                continue
                
            if self.regions and proxy['region'] not in self.regions:
                continue
                
            if not self._check_anonymity(proxy['anonymity']):
                continue
                
            if self.google_compatible and proxy['google'].lower() != 'yes':
                continue
                
            if self.protocol == Protocol.HTTPS and proxy['https'].lower() != 'yes':
                continue
                
            if self.protocol.value.upper() not in proxy['protocol']:
                continue
                
            filtered.append(proxy)
            
        return filtered

    def _check_anonymity(self, anonymity: str) -> bool:
        """Verify anonymity level"""
        anonymity = anonymity.lower()
        if self.anonymity_level == ProxyAnonymity.ELITE:
            return 'elite' in anonymity or 'high' in anonymity
        elif self.anonymity_level == ProxyAnonymity.ANONYMOUS:
            return 'anonymous' in anonymity
        return True

    def _detect_region(self, country: str) -> str:
        """Simple region detection (expand as needed)"""
        regions = {
            'North America': ['US', 'CA', 'MX'],
            'Europe': ['GB', 'DE', 'FR', 'IT', 'ES'],
            'Asia': ['CN', 'JP', 'KR', 'IN'],
            'South America': ['BR', 'AR', 'CL']
        }
        for region, codes in regions.items():
            if country in codes:
                return region
        return 'Other'

    def get(self, max_retries: int = 3) -> Optional[Dict]:
        """Get a working proxy with rotation and retries"""
        proxies = self.get_proxy_list()
        
        if self.randomize:
            random.shuffle(proxies)
            
        for proxy in proxies:
            if self._test_proxy(proxy):
                return proxy
                
        if max_retries > 0:
            self.randomize = True
            return self.get(max_retries - 1)
            
        raise ProxyException("No working proxies found")

    def _test_proxy(self, proxy: Dict) -> bool:
        """Test proxy connection with protocol support"""
        proxies = {
            'http': f"{self.protocol.value}://{proxy['ip']}:{proxy['port']}",
            'https': f"{self.protocol.value}://{proxy['ip']}:{proxy['port']}"
        }
        
        try:
            response = self._session.get(
                self.test_url,
                proxies=proxies,
                timeout=self.timeout,
                verify=self.verify_ssl
            )
            
            # Additional verification for Google compatibility
            if self.google_compatible:
                return 'google' in response.text.lower()
                
            return response.status_code == 200
        except Exception:
            return False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._session.close()

    def close(self):
        self._session.close()