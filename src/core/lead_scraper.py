import re
import json
import time
import requests
from enum import Enum
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

logger = logging.getLogger(__name__)


class BusinessType(str, Enum):
    PRODUCT_COMPANY  = "Product Company"
    SERVICE_PROVIDER = "Service Provider"
    SAAS             = "SaaS / Software"
    ECOMMERCE        = "E-Commerce / Online Store"
    AGENCY           = "Agency"
    MARKETPLACE      = "Marketplace"
    MEDIA_PUBLISHER  = "Media / Publisher"
    NONPROFIT        = "Non-Profit / NGO"
    EDUCATION        = "Education / Training"
    GOVERNMENT       = "Government"
    PERSONAL_BLOG    = "Personal / Blog"
    UNKNOWN          = "Unknown"


BUSINESS_SIGNALS = {
    BusinessType.ECOMMERCE: {
        "keywords": [
            "add to cart", "buy now", "shop now", "shop all", "price", "checkout",
            "shipping", "free delivery", "order now", "in stock", "out of stock",
            "add to bag", "add to wishlist", "product details", "size chart",
            "customer reviews", "sale", "discount", "coupon",
        ],
        "meta_hints": ["shop", "store", "ecommerce", "buy", "products"],
        "tech_hints": ["shopify", "woocommerce", "magento", "bigcommerce", "prestashop", "opencart"],
    },
    BusinessType.SAAS: {
        "keywords": [
            "sign up", "free trial", "start free", "pricing plans", "per month",
            "/mo", "enterprise plan", "api", "dashboard", "integrations",
            "request demo", "book a demo", "schedule demo", "log in", "signin",
            "documentation", "changelog", "developer", "sdk", "webhook",
        ],
        "meta_hints": ["software", "platform", "saas", "cloud", "app", "tool"],
        "tech_hints": [],
    },
    BusinessType.SERVICE_PROVIDER: {
        "keywords": [
            "our services", "what we do", "we offer", "we provide", "solutions",
            "consulting", "hire us", "get a quote", "request quote", "free quote",
            "book a call", "schedule consultation", "our expertise", "our process",
            "how we work", "industries we serve", "why choose us",
        ],
        "meta_hints": ["services", "consulting", "solutions", "provider"],
        "tech_hints": [],
    },
    BusinessType.AGENCY: {
        "keywords": [
            "our work", "portfolio", "case studies", "case study", "clients",
            "we've worked with", "our team", "creative", "campaign", "branding",
            "our projects", "testimonials", "our clients", "partnerships",
            "full-service", "retainer",
        ],
        "meta_hints": ["agency", "creative", "marketing", "design", "digital agency", "studio"],
        "tech_hints": [],
    },
    BusinessType.MARKETPLACE: {
        "keywords": [
            "sell on", "become a seller", "vendor", "list your", "browse listings",
            "buyers and sellers", "find a", "near me", "top rated", "compare",
            "featured listings",
        ],
        "meta_hints": ["marketplace", "directory", "listings", "classifieds"],
        "tech_hints": [],
    },
    BusinessType.MEDIA_PUBLISHER: {
        "keywords": [
            "latest news", "breaking news", "editorial", "subscribe", "newsletter",
            "published on", "author", "contributor", "opinion", "trending",
            "read more", "article", "blog post", "journalist",
        ],
        "meta_hints": ["news", "media", "magazine", "blog", "publication", "journal"],
        "tech_hints": [],
    },
    BusinessType.EDUCATION: {
        "keywords": [
            "courses", "enroll", "curriculum", "syllabus", "certificate",
            "learn", "training", "workshop", "webinar", "instructor",
            "student", "admission", "tuition", "scholarship", "campus",
        ],
        "meta_hints": ["education", "training", "academy", "institute", "school", "university", "learning"],
        "tech_hints": [],
    },
    BusinessType.NONPROFIT: {
        "keywords": [
            "donate", "donation", "volunteer", "mission", "cause",
            "charity", "fundraiser", "impact", "community", "501(c)",
            "make a difference", "give now",
        ],
        "meta_hints": ["nonprofit", "ngo", "charity", "foundation", "non-profit"],
        "tech_hints": [],
    },
    BusinessType.GOVERNMENT: {
        "keywords": [
            "public notice", "government", "department of", "ministry",
            "citizen", "municipal", "federal", "official website",
        ],
        "meta_hints": ["government", "gov", "municipal", "public"],
        "tech_hints": [],
    },
    BusinessType.PERSONAL_BLOG: {
        "keywords": [
            "my journey", "about me", "personal", "i write", "my blog",
            "follow me", "my thoughts", "i am a",
        ],
        "meta_hints": ["blog", "personal", "portfolio"],
        "tech_hints": [],
    },
    BusinessType.PRODUCT_COMPANY: {
        "keywords": [
            "our products", "product line", "features", "specifications",
            "how it works", "built for", "designed for", "made with",
            "innovation", "technology", "patent",
        ],
        "meta_hints": ["product", "technology", "innovation", "hardware"],
        "tech_hints": [],
    },
}

INDUSTRY_KEYWORDS = {
    "Digital Marketing": ["seo", "ppc", "social media marketing", "google ads", "content marketing", "digital marketing"],
    "Web Development": ["web development", "web design", "website", "frontend", "backend", "full stack", "wordpress"],
    "IT Services": ["it services", "managed services", "cloud computing", "cybersecurity", "it support", "devops"],
    "Healthcare": ["healthcare", "medical", "hospital", "clinic", "patient", "doctor", "health", "pharma", "dental"],
    "Finance": ["finance", "banking", "investment", "insurance", "fintech", "accounting", "tax", "loan", "mortgage"],
    "Real Estate": ["real estate", "property", "homes for sale", "realty", "apartment", "rental", "broker"],
    "Legal": ["law firm", "attorney", "lawyer", "legal", "litigation", "counsel"],
    "Hospitality": ["hotel", "restaurant", "travel", "tourism", "booking", "resort", "hospitality"],
    "Retail": ["retail", "fashion", "clothing", "apparel", "accessories", "jewelry", "shoes"],
    "Food & Beverage": ["food", "beverage", "grocery", "organic", "restaurant", "catering", "bakery", "cafe"],
    "Construction": ["construction", "building", "contractor", "renovation", "architecture", "engineering"],
    "Automotive": ["automotive", "car dealer", "vehicle", "auto repair", "dealership", "auto parts", "car rental"],
    "Manufacturing": ["manufacturing", "factory", "industrial", "machinery", "production"],
    "Logistics": ["logistics", "shipping", "freight", "supply chain", "warehouse", "courier", "delivery"],
    "Telecommunications": ["telecom", "internet provider", "broadband", "wireless", "mobile network"],
    "Energy": ["energy", "solar", "renewable", "oil", "gas", "power", "electricity", "wind"],
    "Agriculture": ["agriculture", "farming", "agri", "crop", "livestock", "organic farming"],
    "Entertainment": ["entertainment", "gaming", "music", "movie", "streaming", "event", "concert"],
    "Fitness": ["fitness", "gym", "yoga", "wellness", "personal trainer", "workout", "sports"],
    "Beauty": ["beauty", "salon", "spa", "skincare", "cosmetic", "hair", "makeup"],
    "Photography": ["photography", "photographer", "photo studio", "videography", "wedding photography"],
    "E-Commerce": ["ecommerce", "online store", "online shop", "dropshipping"],
    "SaaS": ["saas", "software as a service", "cloud platform", "api platform"],
    "AI / Machine Learning": ["artificial intelligence", "machine learning", "deep learning", "data science", "neural network", "generative ai"],
    "Blockchain": ["blockchain", "crypto", "web3", "nft", "defi", "decentralized"],
    "HR / Recruitment": ["recruitment", "hiring", "hr", "human resources", "staffing", "talent", "jobs"],
    "Consulting": ["consulting", "consultancy", "advisory", "management consulting", "strategy"],
}

TECH_STACK_SIGNATURES = {
    "WordPress": ['wp-content', 'wp-includes', 'wordpress'],
    "Shopify": ['cdn.shopify.com', 'shopify-section', 'Shopify.theme'],
    "Wix": ['wixsite.com', 'static.wixstatic.com', 'wix-iframe'],
    "Squarespace": ['squarespace.com', 'squarespace-cdn', 'Static.SQUARESPACE'],
    "React": ['_reactRootContainer', 'data-reactroot'],
    "Next.js": ['__NEXT_DATA__', '_next/static'],
    "Vue.js": ['vue-app', '__vue__', 'v-cloak'],
    "Angular": ['ng-version', 'ng-app'],
    "Gatsby": ['___gatsby', 'gatsby-image'],
    "Drupal": ['drupal.js', 'sites/default/files'],
    "Webflow": ['webflow.com', 'w-nav', 'w-slider'],
    "Ghost": ['ghost-portal', 'content/themes'],
    "Bootstrap": ['bootstrap.min.css', 'bootstrap.min.js'],
    "Tailwind CSS": ['tailwindcss'],
    "WooCommerce": ['woocommerce', 'wc-block'],
    "Magento": ['Magento', '/mage/', 'magento/static'],
    "HubSpot": ['hs-scripts.com', 'hubspot', 'hbspt.forms'],
    "Google Analytics": ['google-analytics.com', 'gtag', 'googletagmanager.com'],
}

SOCIAL_DOMAINS = {
    'facebook.com': 'facebook',
    'twitter.com': 'twitter',
    'x.com': 'twitter',
    'linkedin.com': 'linkedin',
    'instagram.com': 'instagram',
    'youtube.com': 'youtube',
    'github.com': 'github',
}

_OFFERING_NOISE = {
    "filter", "sort by", "sort", "filter and sort", "filter:",
    "item added to your cart", "collection", "collection:",
    "menu", "search", "close", "skip to content", "main menu",
    "home", "back", "next", "previous", "load more", "view all",
    "read more", "learn more", "see more", "show more",
    "subscribe", "sign up", "log in", "cart",
}

_EMAIL_IGNORE_DOMAINS = {
    'example.com', 'email.com', 'domain.com', 'yoursite.com',
    'yourdomain.com', 'company.com', 'sentry.io', 'wixpress.com',
    'test.com', 'placeholder.com',
}


class BusinessClassifier:

    def classify(self, pages_data):
        corpus = self._build_corpus(pages_data)
        html_blob = "\n".join(p.get("html_raw", "") for p in pages_data)

        business_type, confidence, secondary = self._score_business_type(corpus)
        industry = self._detect_industry(corpus)
        offerings = self._extract_offerings(pages_data)
        tech_stack = self._detect_tech_stack(html_blob)
        description = self._build_description(pages_data)

        return {
            "business_type": business_type.value,
            "business_confidence": confidence,
            "secondary_type": secondary.value if secondary else "",
            "industry": industry,
            "offerings": offerings,
            "tech_stack": tech_stack,
            "description": description,
        }

    def _build_corpus(self, pages_data):
        parts = []
        for p in pages_data:
            parts.append(p.get("title", "") * 3)
            parts.append(p.get("meta_description", "") * 2)
            for h in p.get("headings", []):
                parts.append(h * 3)
            parts.append(p.get("body_text", "")[:3000])
        return " ".join(parts).lower()

    def _score_business_type(self, corpus):
        scores = {}
        for btype, signals in BUSINESS_SIGNALS.items():
            score = 0
            for kw in signals["keywords"]:
                score += corpus.count(kw.lower()) * 2
            for hint in signals["meta_hints"]:
                if hint.lower() in corpus:
                    score += 5
            for tech in signals["tech_hints"]:
                if tech.lower() in corpus:
                    score += 10
            scores[btype] = score

        if not scores or max(scores.values()) == 0:
            return BusinessType.UNKNOWN, 0, None

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top_type, top_score = ranked[0]
        second_type, second_score = ranked[1] if len(ranked) > 1 else (None, 0)

        total = sum(scores.values()) or 1
        confidence = round((top_score / total) * 100, 1)

        secondary = second_type if (second_score > 0 and top_score - second_score <= top_score * 0.3) else None
        return top_type, confidence, secondary

    def _detect_industry(self, corpus):
        best_industry = "General"
        best_score = 0
        for industry, keywords in INDUSTRY_KEYWORDS.items():
            score = 0
            for kw in keywords:
                hits = corpus.count(kw)
                weight = len(kw.split()) + 1
                score += hits * weight
            if score > best_score:
                best_score = score
                best_industry = industry
        return best_industry if best_score >= 3 else "General"

    def _extract_offerings(self, pages_data):
        offerings = []
        service_page = None
        for p in pages_data:
            if p.get("page_type") in ("services", "products"):
                service_page = p
                break

        if service_page:
            for h in service_page.get("headings", []):
                cleaned = h.strip()
                if 3 < len(cleaned) < 80 and cleaned.lower().rstrip(":; ") not in _OFFERING_NOISE:
                    offerings.append(cleaned)

        if not offerings:
            trigger_words = ["service", "offer", "solution", "product", "what we do", "our expertise"]
            for p in pages_data:
                headings = p.get("headings", [])
                for i, h in enumerate(headings):
                    if any(tw in h.lower() for tw in trigger_words):
                        for sub_h in headings[i + 1: i + 8]:
                            cleaned = sub_h.strip()
                            if (3 < len(cleaned) < 80
                                    and cleaned.lower().rstrip(":; ") not in _OFFERING_NOISE
                                    and not any(tw in cleaned.lower() for tw in trigger_words)):
                                offerings.append(cleaned)

        seen = set()
        unique = []
        for o in offerings:
            key = o.lower().strip()
            if key not in seen:
                seen.add(key)
                unique.append(o)
        return unique[:15]

    def _detect_tech_stack(self, html_blob):
        html_lower = html_blob.lower()
        detected = []
        for tech, signatures in TECH_STACK_SIGNATURES.items():
            for sig in signatures:
                if sig.lower() in html_lower:
                    detected.append(tech)
                    break
        return detected

    def _build_description(self, pages_data):
        for p in pages_data:
            desc = p.get("meta_description", "").strip()
            if desc and len(desc) > 20:
                return desc
        for p in pages_data:
            if p.get("title", "").strip():
                return p["title"].strip()
        return ""


class LeadScraper:

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })
        self.timeout = 15

        self.email_re = re.compile(
            r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', re.IGNORECASE
        )
        self.phone_patterns = [
            re.compile(r'\+?1?[\s.\-]?\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}'),
            re.compile(r'\+?\d{1,4}[\s.\-]?\(?\d{1,5}\)?[\s.\-]?\d{1,5}[\s.\-]?\d{1,5}[\s.\-]?\d{0,5}'),
            re.compile(r'\+91[\s.\-]?\d{5}[\s.\-]?\d{5}'),
            re.compile(r'\+44[\s.\-]?\d{4}[\s.\-]?\d{6}'),
        ]

        self._contact_kw = ['contact', 'contact-us', 'contactus', 'get-in-touch', 'reach-us', 'enquiry', 'support']
        self._about_kw = ['about', 'about-us', 'aboutus', 'who-we-are', 'our-story', 'company', 'team', 'our-team']
        self._services_kw = ['services', 'what-we-do', 'solutions', 'offerings', 'our-services', 'capabilities']
        self._products_kw = ['products', 'shop', 'store', 'catalog', 'collections', 'our-products']

        self.classifier = BusinessClassifier()

    def fetch_page(self, url):
        try:
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            resp = self.session.get(url, timeout=self.timeout, allow_redirects=True)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, 'lxml'), resp.url
        except requests.RequestException:
            try:
                if url.startswith('https://'):
                    url = url.replace('https://', 'http://')
                    resp = self.session.get(url, timeout=self.timeout, allow_redirects=True)
                    resp.raise_for_status()
                    return BeautifulSoup(resp.text, 'lxml'), resp.url
            except Exception:
                pass
            return None, url

    def _find_sub_pages(self, soup, base_url):
        pages = {'contact': [], 'about': [], 'services': [], 'products': []}
        if not soup:
            return pages

        base_netloc = urlparse(base_url).netloc
        for link in soup.find_all('a', href=True):
            href = link.get('href', '').strip()
            text = link.get_text(strip=True).lower()
            full_url = urljoin(base_url, href)

            if urlparse(full_url).netloc != base_netloc:
                continue

            combined = href.lower() + ' ' + text
            if any(kw in combined for kw in self._contact_kw):
                pages['contact'].append(full_url)
            elif any(kw in combined for kw in self._about_kw):
                pages['about'].append(full_url)
            elif any(kw in combined for kw in self._services_kw):
                pages['services'].append(full_url)
            elif any(kw in combined for kw in self._products_kw):
                pages['products'].append(full_url)

        for key in pages:
            pages[key] = list(set(pages[key]))
        return pages

    def _extract_page_metadata(self, soup, url, page_type="homepage"):
        html_raw = str(soup)

        title = ""
        title_tag = soup.find('title')
        if title_tag and title_tag.string:
            title = title_tag.string.strip()

        meta_desc = ""
        tag = soup.find('meta', attrs={'name': 'description'})
        if tag:
            meta_desc = tag.get('content', '').strip()
        if not meta_desc:
            og = soup.find('meta', attrs={'property': 'og:description'})
            if og:
                meta_desc = og.get('content', '').strip()

        headings = []
        for t in ['h1', 'h2', 'h3']:
            for el in soup.find_all(t):
                text = el.get_text(strip=True)
                if text and len(text) < 200:
                    headings.append(text)

        soup_copy = BeautifulSoup(html_raw, 'lxml')
        for s in soup_copy.find_all(['script', 'style', 'nav', 'footer', 'header']):
            s.decompose()
        body_text = soup_copy.get_text(separator=' ', strip=True)

        return {
            "title": title,
            "meta_description": meta_desc,
            "headings": headings,
            "body_text": body_text,
            "html_raw": html_raw,
            "page_type": page_type,
            "url": url,
        }

    def _extract_emails(self, soup, page_text):
        emails = set()
        emails.update(self.email_re.findall(page_text))

        for link in soup.find_all('a', href=True):
            href = link['href']
            if 'mailto:' in href:
                email = href.replace('mailto:', '').split('?')[0].strip()
                if self.email_re.match(email):
                    emails.add(email)

        return [
            e.lower() for e in emails
            if not any(ig in e.lower() for ig in _EMAIL_IGNORE_DOMAINS)
            and not e.endswith(('.png', '.jpg', '.gif', '.svg', '.css', '.js'))
        ]

    def _extract_phones(self, soup, page_text):
        phones = set()
        for pattern in self.phone_patterns:
            for phone in pattern.findall(page_text):
                cleaned = re.sub(r'[^\d+\-() ]', '', phone).strip()
                digits = re.sub(r'\D', '', cleaned)
                if 7 <= len(digits) <= 15:
                    phones.add(cleaned)

        for link in soup.find_all('a', href=True):
            if 'tel:' in link['href']:
                phone = link['href'].replace('tel:', '').strip()
                cleaned = re.sub(r'[^\d+\-() ]', '', phone).strip()
                digits = re.sub(r'\D', '', cleaned)
                if 7 <= len(digits) <= 15:
                    phones.add(cleaned)

        return list(phones)

    def _extract_org_name(self, soup, url):
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(script.string)
                if isinstance(data, list):
                    data = data[0]
                if isinstance(data, dict) and data.get('@type') in [
                    'Organization', 'LocalBusiness', 'Corporation', 'Company'
                ]:
                    name = data.get('name')
                    if name:
                        return name
            except (json.JSONDecodeError, TypeError):
                continue

        for selector, attr in [
            ('meta[property="og:site_name"]', 'content'),
            ('meta[name="application-name"]', 'content'),
            ('meta[property="og:title"]', 'content'),
        ]:
            tag = soup.select_one(selector)
            if tag and tag.get(attr):
                return tag[attr].strip()

        title = soup.find('title')
        if title and title.string:
            name = re.split(r'[|\-–—:]', title.string)[0].strip()
            if name and len(name) < 80:
                return name

        return urlparse(url).netloc.replace('www.', '')

    def _extract_social_links(self, soup):
        socials = {}
        for link in soup.find_all('a', href=True):
            href = link['href'].strip()
            for domain, name in SOCIAL_DOMAINS.items():
                if domain in href and name not in socials:
                    socials[name] = href
        return socials

    def _extract_address(self, soup, page_text):
        addresses = []
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(script.string)
                if isinstance(data, list):
                    data = data[0]
                if isinstance(data, dict):
                    addr = data.get('address', {})
                    if isinstance(addr, dict):
                        parts = [
                            addr.get('streetAddress', ''),
                            addr.get('addressLocality', ''),
                            addr.get('addressRegion', ''),
                            addr.get('postalCode', ''),
                            addr.get('addressCountry', ''),
                        ]
                        full = ', '.join(p for p in parts if p)
                        if full:
                            addresses.append(full)
            except (json.JSONDecodeError, TypeError):
                continue

        for addr_tag in soup.find_all('address'):
            text = addr_tag.get_text(separator=' ', strip=True)
            if len(text) > 10:
                addresses.append(text)

        seen = set()
        unique = []
        for a in addresses:
            cleaned = ' '.join(a.split())
            if cleaned not in seen and len(cleaned) > 10:
                seen.add(cleaned)
                unique.append(cleaned)
        return unique

    def _extract_from_page(self, soup, url):
        if not soup:
            return {}
        page_text = soup.get_text(separator=' ', strip=True)
        return {
            'emails': self._extract_emails(soup, page_text),
            'phones': self._extract_phones(soup, page_text),
            'addresses': self._extract_address(soup, page_text),
            'org_name': self._extract_org_name(soup, url),
            'social_links': self._extract_social_links(soup),
        }

    def process_url(self, url, progress_callback=None):
        result = {
            'url': url,
            'domain': urlparse('https://' + url if '://' not in url else url).netloc.replace('www.', ''),
            'org_name': '',
            'emails': [],
            'phones': [],
            'addresses': [],
            'social_links': {},
            'business_type': '',
            'secondary_type': '',
            'business_confidence': 0,
            'industry': '',
            'offerings': [],
            'tech_stack': [],
            'description': '',
            'pages_crawled': 0,
            'status': 'success',
        }

        soup, final_url = self.fetch_page(url)
        if not soup:
            result['status'] = 'failed'
            return result

        pages_meta = []

        page_data = self._extract_from_page(soup, final_url)
        self._merge(result, page_data)
        pages_meta.append(self._extract_page_metadata(soup, final_url, "homepage"))
        pages_crawled = 1

        sub_pages = self._find_sub_pages(soup, final_url)
        for page_type in ['contact', 'about', 'services', 'products']:
            for page_url in sub_pages[page_type][:2]:
                time.sleep(0.5)
                page_soup, page_final_url = self.fetch_page(page_url)
                if page_soup:
                    self._merge(result, self._extract_from_page(page_soup, page_final_url))
                    pages_meta.append(self._extract_page_metadata(page_soup, page_final_url, page_type))
                    pages_crawled += 1

        result['emails'] = list(set(result['emails']))
        result['phones'] = list(set(result['phones']))
        result['addresses'] = list(set(result['addresses']))
        result['pages_crawled'] = pages_crawled

        if pages_meta:
            cls = self.classifier.classify(pages_meta)
            result['business_type'] = cls['business_type']
            result['secondary_type'] = cls['secondary_type']
            result['business_confidence'] = cls['business_confidence']
            result['industry'] = cls['industry']
            result['offerings'] = cls['offerings']
            result['tech_stack'] = cls['tech_stack']
            result['description'] = cls['description']

        return result

    def _merge(self, result, new_data):
        result['emails'].extend(new_data.get('emails', []))
        result['phones'].extend(new_data.get('phones', []))
        result['addresses'].extend(new_data.get('addresses', []))
        result['social_links'].update(new_data.get('social_links', {}))
        if not result['org_name'] and new_data.get('org_name'):
            result['org_name'] = new_data['org_name']

    def process_urls(self, urls, max_workers=5, progress_callback=None):
        results = []
        total = len(urls)

        with ThreadPoolExecutor(max_workers=min(max_workers, total)) as executor:
            future_to_url = {executor.submit(self.process_url, url): url for url in urls}
            done = 0
            for future in as_completed(future_to_url):
                try:
                    results.append(future.result())
                except Exception as e:
                    results.append({
                        'url': future_to_url[future],
                        'status': 'error',
                        'org_name': '', 'emails': [], 'phones': [],
                        'addresses': [], 'social_links': {},
                        'business_type': '', 'secondary_type': '',
                        'business_confidence': 0, 'industry': '',
                        'offerings': [], 'tech_stack': [], 'description': '',
                        'pages_crawled': 0, 'domain': '',
                    })
                done += 1
                if progress_callback:
                    progress_callback(done, total)

        return results
