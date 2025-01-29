import os
import time
import json
import cloudscraper
from bs4 import BeautifulSoup
from datetime import datetime
from colorama import Fore, Style
from prettytable import PrettyTable
from socks import SOCKS5, SOCKS4
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from requests.auth import HTTPProxyAuth
from requests import Session

BASE_URL = 'https://api.depined.org/api'

# Display banner
def display_banner():
    print(Fore.GREEN + """
    ╔══════════════════════════════════════════════════════════════════════════════╗
    ║                            AirdropInsiders Manager                          ║
    ╚══════════════════════════════════════════════════════════════════════════════╝
    """ + Style.RESET_ALL)

# Format timestamps
def get_timestamp():
    return datetime.now().strftime('%H:%M:%S')

# Create stats table
def create_stats_table(accounts):
    table = PrettyTable()
    table.field_names = ["Account", "Username", "Email", "Proxy", "Status", "Points Today", "Total Points", "Last Update"]
    for account in accounts:
        table.add_row([
            account['token'][:8] + '...',
            account.get('username', '-'),
            account.get('email', '-'),
            f"{account['proxy_config']['type']}://{account['proxy_config']['host']}:{account['proxy_config']['port']}" if account.get('proxy_config') else 'Direct',
            account['status'],
            f"{account.get('points_today', 0):.2f}",
            f"{account.get('total_points', 0):.2f}",
            account.get('last_update', '-')
        ])
    return table

# Log success
def log_success(account_id, message, points_today, total_points, username, email):
    print(Fore.GREEN + f"[{get_timestamp()}] Account {account_id}: {message}" +
          Fore.BLUE + f" | {username}" +
          Fore.YELLOW + f" | {email}" +
          Fore.MAGENTA + f" | Points Today: {points_today:.2f}" +
          Fore.CYAN + f" | Total Points: {total_points:.2f}" + Style.RESET_ALL)

# Parse proxy string
def parse_proxy_string(proxy_string):
    try:
        protocol, rest = proxy_string.strip().split('://')
        if not rest:
            raise ValueError('Invalid proxy format')

        credentials, host_port = rest.split('@') if '@' in rest else (None, rest)
        host, port = host_port.split(':') if ':' in host_port else (None, None)

        if not host or not port:
            raise ValueError('Invalid proxy host/port')

        auth = None
        if credentials:
            username, password = credentials.split(':')
            auth = HTTPProxyAuth(username, password)

        return {
            'type': protocol.lower(),
            'host': host,
            'port': int(port),
            'auth': auth
        }
    except Exception as e:
        raise ValueError(f"Failed to parse proxy string: {proxy_string} - {str(e)}")

# Create session with proxy
def create_session(proxy_config=None):
    session = Session()
    retries = Retry(total=5, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    session.mount('http://', HTTPAdapter(max_retries=retries))
    session.mount('https://', HTTPAdapter(max_retries=retries))

    if proxy_config:
        proxies = {
            'http': f"{proxy_config['type']}://{proxy_config['host']}:{proxy_config['port']}",
            'https': f"{proxy_config['type']}://{proxy_config['host']}:{proxy_config['port']}"
        }
        session.proxies.update(proxies)
        if proxy_config.get('auth'):
            session.auth = proxy_config['auth']

    return session

# Get stats using cloudscraper
def get_stats(token, scraper, proxy_config=None):
    headers = {
        'Accept': 'application/json',
        'Authorization': f'Bearer {token}',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://depined.org/',
        'Origin': 'https://depined.org/',
        'Accept-Language': 'en-US,en;q=0.9',
        'Connection': 'keep-alive'
    }

    try:
        response = scraper.get(f"{BASE_URL}/stats/earnings", headers=headers)
        response.raise_for_status()
        data = response.json().get('data', {})
        return {
            'points_today': data.get('total_points_today', 0),
            'total_points': data.get('total_points_balance', 0)
        }
    except Exception as e:
        raise Exception(f"Failed to fetch stats: {str(e)}")

# Get user profile using cloudscraper
def get_user_profile(token, scraper, proxy_config=None):
    headers = {
        'Accept': 'application/json',
        'Authorization': f'Bearer {token}',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://depined.org/',
        'Origin': 'https://depined.org/',
        'Accept-Language': 'en-US,en;q=0.9',
        'Connection': 'keep-alive'
    }

    try:
        response = scraper.get(f"{BASE_URL}/user/overview/profile", headers=headers)
        response.raise_for_status()
        data = response.json().get('data', {})
        return {
            'username': data.get('profile', {}).get('username', '-'),
            'email': data.get('user_details', {}).get('email', '-')
        }
    except Exception as e:
        raise Exception(f"Failed to fetch user profile: {str(e)}")

# Ping function using cloudscraper
def ping(token, scraper, proxy_config=None):
    headers = {
        'Accept': 'application/json',
        'Authorization': f'Bearer {token}',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://depined.org/',
        'Origin': 'https://depined.org/',
        'Accept-Language': 'en-US,en;q=0.9',
        'Connection': 'keep-alive'
    }

    try:
        response = scraper.post(f"{BASE_URL}/user/widget-connect", headers=headers, json={'connected': True})
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise Exception(f"Failed to ping server: {str(e)}")

# Read and validate input files
def read_input_files():
    try:
        with open('data.txt', 'r') as file:
            tokens = [line.strip() for line in file if line.strip()]

        if not tokens:
            raise ValueError('No tokens found in data.txt')

        proxies = []
        try:
            with open('proxy.txt', 'r') as file:
                proxies = [parse_proxy_string(line.strip()) for line in file if line.strip()]
        except FileNotFoundError:
            print(Fore.YELLOW + "No proxy.txt found or error reading proxies. Running without proxies." + Style.RESET_ALL)

        return tokens, proxies
    except Exception as e:
        raise Exception(f"Failed to read input files: {str(e)}")

# Main function
def main():
    display_banner()
    tokens, proxies = read_input_files()

    accounts = []
    for i, token in enumerate(tokens):
        accounts.append({
            'token': token,
            'proxy_config': proxies[i % len(proxies)] if proxies else None,
            'status': 'Initializing',
            'username': None,
            'email': None,
            'points_today': 0,
            'total_points': 0,
            'last_update': None
        })

    scraper = cloudscraper.create_scraper()  # Reuse the same scraper for all requests

    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        display_banner()
        print(Fore.YELLOW + "Join Us : https://t.me/AirdropInsiderID\n" + Style.RESET_ALL)
        print(Fore.CYAN + "=== Depined Multi-Account Manager ===\n" + Style.RESET_ALL)
        print(create_stats_table(accounts))
        print(Fore.CYAN + "\n=== Activity Log ===" + Style.RESET_ALL)

        for i, account in enumerate(accounts):
            try:
                # Get user profile if not already fetched
                if not account['username'] or not account['email']:
                    profile = get_user_profile(account['token'], scraper, account['proxy_config'])
                    account['username'] = profile['username']
                    account['email'] = profile['email']

                # Ping server
                ping(account['token'], scraper, account['proxy_config'])
                account['status'] = Fore.GREEN + 'Connected' + Style.RESET_ALL

                # Get stats
                stats = get_stats(account['token'], scraper, account['proxy_config'])
                account['points_today'] = stats['points_today']
                account['total_points'] = stats['total_points']
                account['last_update'] = get_timestamp()

                log_success(i + 1, "Ping successful", stats['points_today'], stats['total_points'], account['username'], account['email'])
            except Exception as e:
                account['status'] = Fore.RED + 'Error' + Style.RESET_ALL
                account['last_update'] = get_timestamp()
                print(Fore.RED + f"[{get_timestamp()}] Account {i + 1}: Error - {str(e)}" + Style.RESET_ALL)

            time.sleep(1)  # Add delay between accounts

        time.sleep(30)  # Wait before next update

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(Fore.RED + f"Application error: {str(e)}" + Style.RESET_ALL)