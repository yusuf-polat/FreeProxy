import os
import json
import random
import time
import warnings
import requests
import socket
import socks
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from fake_useragent import UserAgent
import speech_recognition as sr
from pydub import AudioSegment
import subprocess
import sys
import logging

# Logging ayarları
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("ensemble_bot.log"),
        logging.StreamHandler()
    ]
)

# Import the temp-mail.org API wrapper
try:
    from tempmail import TempMail
except ImportError:
    logging.info("Installing tempmail package...")
    os.system("pip install git+https://github.com/Temp-Mail-API/Python.git")
    from tempmail import TempMail

# Suppress SSL warnings
warnings.filterwarnings('ignore', category=requests.packages.urllib3.exceptions.InsecureRequestWarning)

# Suppress TensorFlow warnings (if they appear)
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

# ASCII Art
print("""
██╗   ██╗██╗   ██╗███████╗██╗   ██╗███████╗    ██████╗  ██████╗ ██╗      █████╗ ████████╗
╚██╗ ██╔╝██║   ██║██╔════╝██║   ██║██╔════╝    ██╔══██╗██╔═══██╗██║     ██╔══██╗╚══██╔══╝
 ╚████╔╝ ██║   ██║███████╗██║   ██║█████╗      ██████╔╝██║   ██║██║     ███████║   ██║   
  ╚██╔╝  ██║   ██║╚════██║██║   ██║██╔══╝      ██╔═══╝ ██║   ██║██║     ██╔══██║   ██║   
   ██║   ╚██████╔╝███████║╚██████╔╝██║         ██║     ╚██████╔╝███████╗██║  ██║   ██║   
   ╚═╝    ╚═════╝ ╚══════╝ ╚═════╝ ╚═╝         ╚═╝      ╚═════╝ ╚══════╝╚═╝  ╚═╝   ╚═╝   
""")

class TorBrowserManager:
    """
    Manages Tor Browser connection for Selenium
    """
    def __init__(self, tor_browser_path=None):
        """
        Initialize TorBrowserManager
        
        Args:
            tor_browser_path (str): Path to Tor Browser installation folder
                                   If None, tries to find it automatically
        """
        self.tor_browser_path = tor_browser_path or self._find_tor_browser_path()
        self.tor_profile_path = None
        self.socks_port = 9150  # Default Tor Browser SOCKS port
        self.tor_process = None
        
    def _find_tor_browser_path(self):
        """Try to find Tor Browser installation path"""
        possible_paths = [
            # Windows paths
            "C:\\Program Files\\Tor Browser",
            "C:\\Program Files (x86)\\Tor Browser",
            os.path.join(os.environ.get('USERPROFILE', ''), "Desktop\\Tor Browser"),
            os.path.join(os.environ.get('USERPROFILE', ''), "Downloads\\Tor Browser"),
            # Linux paths
            "/usr/bin/tor-browser",
            os.path.join(os.environ.get('HOME', ''), "tor-browser"),
            # macOS paths
            "/Applications/Tor Browser.app/Contents/MacOS",
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                logging.info(f"Tor Browser found at: {path}")
                return path
                
        logging.warning("Tor Browser not found automatically. Please specify the path manually.")
        return None
        
    def _get_tor_profile_path(self):
        """Get path to Tor Browser profile"""
        if not self.tor_browser_path:
            return None
            
        # Different paths based on OS
        if os.name == 'nt':  # Windows
            profile_path = os.path.join(self.tor_browser_path, "Browser\\TorBrowser\\Data\\Browser\\profile.default")
        elif os.name == 'posix':  # Linux/Mac
            if 'Contents/MacOS' in self.tor_browser_path:  # macOS
                profile_path = os.path.join(self.tor_browser_path, "../Data/Browser/profile.default")
            else:  # Linux
                profile_path = os.path.join(self.tor_browser_path, "Browser/TorBrowser/Data/Browser/profile.default")
        else:
            return None
            
        if os.path.exists(profile_path):
            return profile_path
        return None
    
    def start_tor_browser(self):
        """Start Tor Browser in the background"""
        if not self.tor_browser_path:
            logging.error("Tor Browser path not specified.")
            return False
            
        try:
            # Find the Tor Browser executable
            if os.name == 'nt':  # Windows
                tor_exe = os.path.join(self.tor_browser_path, "Browser\\firefox.exe")
                if not os.path.exists(tor_exe):
                    tor_exe = os.path.join(self.tor_browser_path, "Browser\\TorBrowser\\Tor\\tor.exe")
            elif os.name == 'posix':  # Linux/Mac
                if 'Contents/MacOS' in self.tor_browser_path:  # macOS
                    tor_exe = os.path.join(self.tor_browser_path, "firefox")
                else:  # Linux
                    tor_exe = os.path.join(self.tor_browser_path, "Browser/firefox")
            else:
                logging.error("Unsupported operating system")
                return False
                
            if not os.path.exists(tor_exe):
                logging.error(f"Tor Browser executable not found at: {tor_exe}")
                return False
                
            logging.info(f"Starting Tor Browser from: {tor_exe}")
            
            # Start Tor Browser with arguments
            if os.name == 'nt':  # Windows
                # Tor Browser'ı başlatırken özel parametreler kullan
                self.tor_process = subprocess.Popen([tor_exe, "-no-remote"])
            else:  # Linux/Mac
                self.tor_process = subprocess.Popen([tor_exe, "-no-remote"])
                
            # Wait for Tor to connect
            logging.info("Waiting for Tor Browser to connect...")
            
            # Tor Browser'ın bağlanması için daha uzun süre bekle (2 dakika)
            for i in range(120):  # 120 saniye = 2 dakika
                if i % 10 == 0:  # Her 10 saniyede bir log yaz
                    logging.info(f"Waiting for Tor connection... {i} seconds passed")
                if self.check_tor_connection():
                    logging.info("Tor Browser connected successfully!")
                    return True
                time.sleep(1)
                
            logging.error("Timed out waiting for Tor Browser to connect")
            return False
        except Exception as e:
            logging.error(f"Error starting Tor Browser: {e}")
            return False
            
    def is_tor_browser_running(self):
        """Check if Tor Browser is already running"""
        try:
            # Try to connect to Tor SOCKS port
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex(('127.0.0.1', self.socks_port))
            sock.close()
            
            return result == 0
        except Exception as e:
            logging.error(f"Error checking if Tor Browser is running: {e}")
            return False
            
    def get_current_ip(self):
        """Get the current IP address through Tor"""
        try:
            # Configure socket to use Tor
            socks.set_default_proxy(socks.SOCKS5, "127.0.0.1", self.socks_port)
            socket.socket = socks.socksocket
            
            # Make request through Tor
            response = requests.get('https://api.ipify.org', timeout=30)  # Timeout arttırıldı
            ip = response.text
            logging.info(f"Current Tor IP: {ip}")
            
            # Reset socket
            socket.socket = socket._real_socket
            
            return ip
        except Exception as e:
            logging.error(f"Error getting current IP: {e}")
            # Reset socket
            socket.socket = socket._real_socket
            return None
            
    def check_tor_connection(self):
        """Check if Tor Browser is running and accessible"""
        try:
            # Try to connect to Tor SOCKS port
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)  # Timeout arttırıldı
            result = sock.connect_ex(('127.0.0.1', self.socks_port))
            sock.close()
            
            if result == 0:
                logging.info("Tor SOCKS port is accessible.")
                # Verify we can get an IP through Tor
                ip = self.get_current_ip()
                return ip is not None
            else:
                logging.warning(f"Tor SOCKS port {self.socks_port} is not accessible.")
                return False
        except Exception as e:
            logging.error(f"Error checking Tor connection: {e}")
            return False
            
    def setup_selenium_options(self):
        """Configure Selenium to use Tor Browser"""
        # Configure Chrome options
        options = webdriver.ChromeOptions()
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument(f'user-agent={UserAgent().random}')
        options.add_argument('--disable-infobars')
        options.add_argument('--disable-extensions')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--ignore-certificate-errors')
        options.add_argument('--ignore-ssl-errors')
        
        # Configure to use Tor SOCKS proxy
        options.add_argument(f'--proxy-server=socks5://127.0.0.1:{self.socks_port}')
        
        # Disable TensorFlow warnings
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        
        return options
        
    def stop_tor_browser(self):
        """Stop Tor Browser if it was started by this script"""
        if self.tor_process:
            try:
                self.tor_process.terminate()
                self.tor_process.wait(timeout=5)
                logging.info("Tor Browser stopped")
            except Exception as e:
                logging.error(f"Error stopping Tor Browser: {e}")
                try:
                    self.tor_process.kill()
                except:
                    pass

class RecaptchaSolver:
    def __init__(self, driver, wait_time=10):
        """
        Initialize the RecaptchaSolver class.
        
        Args:
            driver: Selenium WebDriver instance
            wait_time (int): Default wait time for WebDriverWait
        """
        self.driver = driver
        self.wait_time = wait_time
        
    def download_audio(self, url, output_file="captcha_audio.mp3"):
        """
        Download audio file from URL
        
        Args:
            url (str): URL of the audio file
            output_file (str): Path to save the audio file
            
        Returns:
            str: Path to the downloaded file
        """
        response = requests.get(url, verify=False)
        with open(output_file, "wb") as f:
            f.write(response.content)
        return output_file
        
    def convert_mp3_to_wav(self, mp3_file, wav_file="captcha_audio.wav"):
        """
        Convert MP3 to WAV format
        
        Args:
            mp3_file (str): Path to MP3 file
            wav_file (str): Path to save the WAV file
            
        Returns:
            str: Path to the WAV file
        """
        sound = AudioSegment.from_mp3(mp3_file)
        sound.export(wav_file, format="wav")
        return wav_file
        
    def transcribe_audio(self, wav_file):
        """
        Transcribe audio file to text using Google Speech Recognition
        
        Args:
            wav_file (str): Path to WAV file
            
        Returns:
            str: Transcribed text
        """
        r = sr.Recognizer()
        with sr.AudioFile(wav_file) as source:
            audio_data = r.record(source)
            try:
                text = r.recognize_google(audio_data)
                return text
            except sr.UnknownValueError:
                logging.warning("Google Speech Recognition could not understand audio")
                return ""
            except sr.RequestError as e:
                logging.error(f"Could not request results from Google Speech Recognition service; {e}")
                return ""
        
    def solve_recaptcha(self, iframe_selector="iframe[title='reCAPTCHA']", 
                       checkbox_selector="div.recaptcha-checkbox-border",
                       challenge_iframe_selector="iframe[title='recaptcha challenge expires in two minutes']"):
        """
        Solve reCAPTCHA on the current page
        
        Args:
            iframe_selector (str): CSS selector for the reCAPTCHA iframe
            checkbox_selector (str): CSS selector for the reCAPTCHA checkbox
            challenge_iframe_selector (str): CSS selector for the challenge iframe
            
        Returns:
            bool: True if reCAPTCHA was solved successfully, False otherwise
        """
        try:
            # Wait for the reCAPTCHA iframe to load and switch to it
            logging.info("Waiting for reCAPTCHA to load...")
            WebDriverWait(self.driver, self.wait_time).until(
                EC.frame_to_be_available_and_switch_to_it((By.CSS_SELECTOR, iframe_selector))
            )
            
            # Click on the reCAPTCHA checkbox
            logging.info("Clicking on the reCAPTCHA checkbox...")
            WebDriverWait(self.driver, self.wait_time).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, checkbox_selector))
            ).click()
            
            # Switch back to the main content
            self.driver.switch_to.default_content()
            
            # Check if we need to solve a challenge
            time.sleep(2)
            try:
                # Wait for the audio challenge iframe to appear and switch to it
                logging.info("Checking for audio challenge...")
                WebDriverWait(self.driver, 5).until(
                    EC.frame_to_be_available_and_switch_to_it((By.CSS_SELECTOR, challenge_iframe_selector))
                )
                
                # Click on the audio challenge button
                logging.info("Clicking on the audio challenge button...")
                WebDriverWait(self.driver, self.wait_time).until(
                    EC.element_to_be_clickable((By.ID, "recaptcha-audio-button"))
                ).click()
                
                # Wait for the audio to be available
                logging.info("Waiting for audio to be available...")
                WebDriverWait(self.driver, self.wait_time).until(
                    EC.presence_of_element_located((By.ID, "audio-source"))
                )
                
                # Get the audio URL
                audio_url = self.driver.find_element(By.ID, "audio-source").get_attribute("src")
                logging.info(f"Audio URL: {audio_url}")
                
                # Process the audio file
                mp3_file = self.download_audio(audio_url)
                wav_file = self.convert_mp3_to_wav(mp3_file)
                audio_response = self.transcribe_audio(wav_file)
                
                # Clean up temporary files
                os.remove(mp3_file)
                os.remove(wav_file)
                
                if not audio_response:
                    logging.warning("Failed to transcribe audio")
                    return False
                    
                logging.info(f"Transcribed text: {audio_response}")
                
                # Enter the response in the text field
                logging.info("Entering the response...")
                self.driver.find_element(By.ID, "audio-response").send_keys(audio_response)
                
                # Click the verify button
                logging.info("Clicking verify button...")
                self.driver.find_element(By.ID, "recaptcha-verify-button").click()
                
                # Switch back to the main content
                self.driver.switch_to.default_content()
                
                # Wait for the reCAPTCHA to be solved
                logging.info("Waiting for reCAPTCHA to be solved...")
                time.sleep(3)
                
            except TimeoutException:
                # No challenge needed, reCAPTCHA was solved by just clicking the checkbox
                logging.info("No challenge needed, reCAPTCHA was solved directly")
                self.driver.switch_to.default_content()
                
            return True
                
        except Exception as e:
            logging.error(f"An error occurred during reCAPTCHA solving: {e}")
            self.driver.switch_to.default_content()
            return False

class TempMailWrapper:
    """
    Wrapper for the temp-mail.org API using the TempMail package
    """
    def __init__(self):
        # Define known domains from temp-mail.org
        self.available_domains = [
            "temp-mail.org",
            "temp-mail.io",
            "tempmail.com",
            "tmpmail.org",
            "tmpmail.net",
            "tmpmail.io",
            "mail-temp.org",
            "mail-temp.com"
        ]
        
        # Use a fixed domain to avoid None issues
        self.domain = self.available_domains[0]
        
        # Initialize with a random name
        random_name = ''.join(random.choice('abcdefghijklmnopqrstuvwxyz') for _ in range(10))
        
        try:
            # Try to initialize with the default domain
            self.tm = TempMail(login=random_name, domain=self.domain)
            logging.info(f"Using domain: {self.domain}")
        except Exception as e:
            logging.error(f"Error initializing TempMail with domain {self.domain}: {e}")
            # Try each domain until one works
            for domain in self.available_domains[1:]:
                try:
                    self.tm = TempMail(login=random_name, domain=domain)
                    self.domain = domain
                    logging.info(f"Successfully initialized with domain: {domain}")
                    break
                except Exception as e:
                    logging.error(f"Error with domain {domain}: {e}")
            else:
                # If all domains fail, create a custom implementation
                logging.warning("All domains failed, using custom implementation")
                self.tm = None
                self.domain = "temp-mail.org"  # Default fallback
        
        self.email = f"{random_name}@{self.domain}"
        logging.info(f"Initialized temp-mail with address: {self.email}")
        
    def generate_email(self):
        """Generate a random email using the API"""
        # Email is already generated in __init__
        return self.email
        
    def get_messages(self):
        """Get all messages for the current email"""
        try:
            if self.tm is None:
                # Custom implementation if TempMail failed to initialize
                return self._custom_get_messages()
                
            messages = self.tm.get_mailbox()
            # Convert to a format similar to what we were using before
            formatted_messages = []
            for msg in messages:
                formatted_messages.append({
                    'id': msg.get('mail_id'),
                    'subject': msg.get('mail_subject', ''),
                    'from': msg.get('mail_from', ''),
                    'date': msg.get('mail_timestamp', '')
                })
            return formatted_messages
        except Exception as e:
            logging.error(f"Error getting messages: {e}")
            return []
        
    def get_message_content(self, message_id):
        """Get content of a specific message"""
        try:
            if self.tm is None:
                # Custom implementation if TempMail failed to initialize
                return self._custom_get_message_content(message_id)
                
            message = self.tm.get_message(message_id)
            # Convert to a format similar to what we were using before
            return {
                'id': message.get('mail_id'),
                'subject': message.get('mail_subject', ''),
                'from': message.get('mail_from', ''),
                'date': message.get('mail_timestamp', ''),
                'body': message.get('mail_text', ''),
                'html_body': message.get('mail_html', '')
            }
        except Exception as e:
            logging.error(f"Error getting message content: {e}")
            return None
            
    def _custom_get_messages(self):
        """Custom implementation to get messages if TempMail fails"""
        try:
            # Extract username and domain from email
            username, domain = self.email.split('@')
            
            # Make direct API request
            url = f"https://api.temp-mail.org/request/mail/id/{username}/{domain}"
            response = requests.get(url)
            
            if response.status_code == 200:
                messages = response.json()
                formatted_messages = []
                for msg in messages:
                    formatted_messages.append({
                        'id': msg.get('mail_id'),
                        'subject': msg.get('mail_subject', ''),
                        'from': msg.get('mail_from', ''),
                        'date': msg.get('mail_timestamp', '')
                    })
                return formatted_messages
            else:
                logging.warning(f"API request failed with status code: {response.status_code}")
                return []
        except Exception as e:
            logging.error(f"Error in custom get_messages: {e}")
            return []
            
    def _custom_get_message_content(self, message_id):
        """Custom implementation to get message content if TempMail fails"""
        try:
            # Make direct API request
            url = f"https://api.temp-mail.org/request/one_mail/id/{message_id}"
            response = requests.get(url)
            
            if response.status_code == 200:
                message = response.json()
                return {
                    'id': message.get('mail_id'),
                    'subject': message.get('mail_subject', ''),
                    'from': message.get('mail_from', ''),
                    'date': message.get('mail_timestamp', ''),
                    'body': message.get('mail_text', ''),
                    'html_body': message.get('mail_html', '')
                }
            else:
                logging.warning(f"API request failed with status code: {response.status_code}")
                return None
        except Exception as e:
            logging.error(f"Error in custom get_message_content: {e}")
            return None

class EnsembleDataBot:
    def __init__(self, use_tor=True, tor_browser_path=None):
        self.ua = UserAgent()
        self.temp_mail = TempMailWrapper()
        self.use_tor = use_tor
        self.tor_browser = TorBrowserManager(tor_browser_path) if use_tor else None
        self.driver = None
        self.api_token = None
        self.account_data = {}
        
    def setup_driver(self):
        if self.use_tor:
            # Check if Tor Browser is running
            if not self.tor_browser.is_tor_browser_running():
                logging.info("Tor Browser is not running. Please start it manually.")
                logging.info("1. Open Tor Browser")
                logging.info("2. Connect to the Tor network")
                logging.info("3. Keep it running in the background")
                logging.info("4. Press Enter to continue once Tor Browser is running...")
                input()  # Wait for user to start Tor Browser
                
                # Check again after user confirmation
                if not self.tor_browser.is_tor_browser_running():
                    logging.error("Tor Browser still not detected. Please make sure it's running.")
                    return False
                
            # Get Selenium options configured for Tor
            options = self.tor_browser.setup_selenium_options()
        else:
            # Standard Selenium setup without Tor
            options = webdriver.ChromeOptions()
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument(f'user-agent={self.ua.random}')
            options.add_argument('--disable-infobars')
            options.add_argument('--disable-extensions')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--ignore-certificate-errors')
            options.add_argument('--ignore-ssl-errors')
            options.add_experimental_option('excludeSwitches', ['enable-logging'])
            
        try:
            self.driver = webdriver.Chrome(options=options)
            self.driver.set_window_size(1920, 1080)
            return True
        except Exception as e:
            logging.error(f"Error setting up WebDriver: {e}")
            return False
        
    
    def create_account(self):
        try:
            # Temp mail oluştur
            email = self.temp_mail.generate_email()
            if not email:
                raise Exception("Geçici e-posta oluşturulamadı")
                
            password = f"TempPass{random.randint(1000, 9999)}!"
            
            # Web sürücüsünü ayarla
            if not self.setup_driver():
                raise Exception("WebDriver ayarlanamadı")
            
            # Kayıt sayfasına git
            self.driver.get("https://dashboard.ensembledata.com/register")
            
            # Sayfanın yüklenmesini bekle
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.TAG_NAME, "body")))
            
            # Sayfanın HTML'ini kontrol et
            logging.info(f"Sayfa başlığı: {self.driver.title}")
            
            # Form elemanlarını bul
            try:
                email_field = WebDriverWait(self.driver, 20).until(
                    EC.presence_of_element_located((By.NAME, "email")))
                email_field.send_keys(email)
                
                # Şifre alanlarını bul
                password_fields = self.driver.find_elements(By.XPATH, "//input[@type='password']")
                if len(password_fields) >= 2:
                    password_fields[0].send_keys(password)
                    password_fields[1].send_keys(password)
                else:
                    raise Exception(f"Şifre alanları bulunamadı, bulunan alanlar: {len(password_fields)}")
                
                # Şartları kabul et
                try:
                    terms_checkbox = self.driver.find_element(By.NAME, "terms")
                    terms_checkbox.click()
                except NoSuchElementException:
                    # Alternatif yöntem dene
                    terms_checkbox = self.driver.find_element(By.XPATH, "//input[@type='checkbox']")
                    terms_checkbox.click()
                
                # reCAPTCHA'yı çöz
                recaptcha_solver = RecaptchaSolver(self.driver)
                if not recaptcha_solver.solve_recaptcha():
                    raise Exception("reCAPTCHA çözülemedi")
                    
                # Kayıt butonuna tıkla
                submit_button = self.driver.find_element(By.XPATH, "//button[@type='submit']")
                submit_button.click()
                
                # Popup kontrolü ve işleme
                try:
                    # Popup'ın görünmesini bekle (maksimum 5 saniye)
                    logging.info("Olası popup için bekleniyor...")
                    
                    # Popup içindeki "Sign up now" düğmesini bulmaya çalış
                    sign_up_now_button = None
                    try:
                        # Farklı olası selektörler deneniyor
                        selectors = [
                            "//button[contains(text(), 'Sign up now')]",
                            "//a[contains(text(), 'Sign up now')]",
                            "//button[contains(@class, 'signup')]",
                            "//button[contains(@class, 'register')]",
                            "//button[contains(text(), 'Continue')]",
                            "//button[contains(text(), 'Confirm')]"
                        ]
                        
                        for selector in selectors:
                            try:
                                sign_up_now_button = WebDriverWait(self.driver, 5).until(
                                    EC.element_to_be_clickable((By.XPATH, selector))
                                )
                                logging.info(f"Popup düğmesi bulundu: {selector}")
                                break
                            except:
                                continue
                                
                        if sign_up_now_button:
                            logging.info("'Sign up now' düğmesine tıklanıyor...")
                            sign_up_now_button.click()
                            
                            # 15 saniye bekle ve URL kontrolü yap
                            logging.info("Welcome sayfasına yönlendirme için 15 saniye bekleniyor...")
                            start_time = time.time()
                            redirected = False
                            
                            while time.time() - start_time < 15:
                                if "welcome" in self.driver.current_url:
                                    logging.info("Welcome sayfasına başarıyla yönlendirildi!")
                                    redirected = True
                                    break
                                time.sleep(1)
                                
                            # Eğer hala welcome sayfasına yönlendirilmediyse, tekrar tıkla
                            if not redirected:
                                logging.info("Welcome sayfasına yönlendirme olmadı, tekrar tıklanıyor...")
                                try:
                                    # Düğmeyi tekrar bul (sayfa yenilenmiş olabilir)
                                    for selector in selectors:
                                        try:
                                            sign_up_now_button = WebDriverWait(self.driver, 5).until(
                                                EC.element_to_be_clickable((By.XPATH, selector))
                                            )
                                            sign_up_now_button.click()
                                            logging.info("Düğmeye tekrar tıklandı.")
                                            break
                                        except:
                                            continue
                                except Exception as e:
                                    logging.warning(f"Düğmeye tekrar tıklanamadı: {e}")
                    except Exception as e:
                        logging.info(f"Popup düğmesi bulunamadı veya gerekli değil: {e}")
                except Exception as e:
                    logging.info(f"Popup işleme hatası (önemli değil): {e}")
                
                # URL değişikliğini bekle ve kontrol et
                try:
                    # Başarılı kayıt durumunda welcome sayfasına yönlendirilir
                    WebDriverWait(self.driver, 20).until(
                        lambda driver: "welcome" in driver.current_url or 
                                      "verify" in driver.current_url or 
                                      "dashboard" in driver.current_url
                    )
                    
                    current_url = self.driver.current_url
                    logging.info(f"Yönlendirilen URL: {current_url}")
                    
                    if "welcome" in current_url:
                        logging.info("Hesap başarıyla oluşturuldu! Welcome sayfasına yönlendirildi.")
                        # API token'ını almaya çalış
                        self._get_api_token()
                    elif "verify" in current_url:
                        logging.info("E-posta doğrulaması gerekiyor.")
                    elif "dashboard" in current_url:
                        logging.info("Hesap başarıyla oluşturuldu! Dashboard sayfasına yönlendirildi.")
                        # API token'ını almaya çalış
                        self._get_api_token()
                    
                except TimeoutException:
                    # Eğer yönlendirme olmadıysa, sayfadaki mesajları kontrol et
                    if "verify your email" in self.driver.page_source:
                        logging.info("E-posta doğrulaması gerekiyor.")
                    else:
                        # Sayfanın ekran görüntüsünü al
                        self.driver.save_screenshot("redirect_failed.png")
                        logging.warning("Yönlendirme başarısız oldu. Ekran görüntüsü kaydedildi: redirect_failed.png")
                        
                        # Doğrudan welcome sayfasına gitmeyi dene
                        try:
                            logging.info("Welcome sayfasına doğrudan gitmeye çalışılıyor...")
                            self.driver.get("https://dashboard.ensembledata.com/welcome")
                            time.sleep(2)
                            
                            if "welcome" in self.driver.current_url:
                                logging.info("Welcome sayfasına manuel olarak gidildi.")
                            else:
                                logging.warning("Welcome sayfasına manuel olarak gidilemedi.")
                        except Exception as e:
                            logging.error(f"Welcome sayfasına manuel gitme hatası: {e}")
                    
                # Hesap bilgilerini kaydet
                self.account_data = {
                    "email": email,
                    "password": password,
                    "registration_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                
                return True
            except Exception as e:
                logging.error(f"Form doldurma hatası: {e}")
                # Hata durumunda sayfanın ekran görüntüsünü al
                self.driver.save_screenshot("error_screenshot.png")
                logging.info("Hata ekran görüntüsü kaydedildi: error_screenshot.png")
                return False
                
        except Exception as e:
            logging.error(f"Hesap oluşturma hatası: {e}")
            return False
        
    
    def _get_api_token(self):
        """API token'ını almak için yardımcı metod"""
        try:
            # Account sayfasına git
            self.driver.get("https://dashboard.ensembledata.com/account")
            
            # API token'ını bul
            self.api_token = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//code"))).text
            
            logging.info(f"API Token başarıyla alındı: {self.api_token}")
            
            # Token süre bilgilerini al
            try:
                trial_info = self.driver.find_element(By.XPATH, "//*[contains(text(), 'trial')]").text
                start_date = datetime.now()
                end_date = start_date + timedelta(days=7)
            except NoSuchElementException:
                start_date = datetime.now()
                end_date = start_date + timedelta(days=30)  # Varsayılan
            
            # Hesap bilgilerini güncelle
            self.account_data.update({
                "api_token": self.api_token,
                "token_start_date": start_date.strftime("%Y-%m-%d %H:%M:%S"),
                "token_end_date": end_date.strftime("%Y-%m-%d %H:%M:%S"),
                "verification_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            
            return True
        except Exception as e:
            logging.error(f"API token alınamadı: {e}")
            return False
            
    def verify_email(self):
        try:
            # Eğer zaten API token'ı alınmışsa, doğrulama gerekmiyor demektir
            if self.api_token:
                logging.info("API token zaten alınmış, e-posta doğrulaması gerekmiyor.")
                return True
                
            logging.info("Doğrulama maili bekleniyor...")
            message_id = None
            start_time = time.time()
            
            # Mail kontrolü (max 3 dakika bekle)
            while time.time() - start_time < 180:
                messages = self.temp_mail.get_messages()
                if messages:
                    for msg in messages:
                        subject = msg.get('subject', '')
                        if "EnsembleData" in subject or "verify" in subject.lower() or "confirm" in subject.lower():
                            message_id = msg.get('id')
                            logging.info(f"Doğrulama maili bulundu: {subject}")
                            break
                    if message_id:
                        break
                logging.info("Mesaj bekleniyor...")
                time.sleep(10)
                
            if not message_id:
                # Doğrulama maili gelmedi, belki hesap otomatik doğrulanmıştır
                logging.info("Doğrulama maili alınamadı, dashboard'a gidiliyor...")
                self.driver.get("https://dashboard.ensembledata.com/dashboard")
                
                # URL'yi kontrol et
                if "dashboard" in self.driver.current_url:
                    logging.info("Dashboard sayfasına erişilebildi, hesap doğrulanmış olabilir.")
                    return self._get_api_token()
                else:
                    raise Exception("Doğrulama maili alınamadı ve dashboard'a erişilemedi")
                
            # Mail içeriğini al
            message = self.temp_mail.get_message_content(message_id)
            if not message:
                raise Exception("Mail içeriği alınamadı")
                
            # HTML içeriğini kontrol et
            html_content = message.get('html_body') or message.get('body')
            if not html_content:
                raise Exception("Mail HTML içeriği bulunamadı")
                
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Doğrulama linkini bul
            verify_link = None
            for link in soup.find_all('a'):
                href = link.get('href', '')
                if "dashboard.ensembledata.com" in href and ("verify" in href or "confirm" in href):
                    verify_link = href
                    break
                    
            if not verify_link:
                raise Exception("Doğrulama linki bulunamadı")
                
            logging.info(f"Doğrulama linki bulundu: {verify_link}")
                
            # Doğrulama linkine git
            self.driver.get(verify_link)
            
            # Doğrulama sonrası URL'yi kontrol et
            WebDriverWait(self.driver, 20).until(
                lambda driver: "dashboard.ensembledata.com" in driver.current_url
            )
            
            logging.info(f"Doğrulama sonrası URL: {self.driver.current_url}")
            
            # API token'ını al
            return self._get_api_token()
            
        except Exception as e:
            logging.error(f"Mail doğrulama hatası: {e}")
            
            # Hata durumunda yine de dashboard'a gitmeyi dene
            try:
                self.driver.get("https://dashboard.ensembledata.com/dashboard")
                if "dashboard" in self.driver.current_url:
                    logging.info("Dashboard sayfasına erişilebildi, hesap doğrulanmış olabilir.")
                    return self._get_api_token()
            except:
                pass
                
            return False
            
    def save_account_data(self):
        try:
            # JSON dosyasına kaydet
            filename = f"ensemble_account_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(filename, 'w') as f:
                json.dump(self.account_data, f, indent=4)
            logging.info(f"Hesap bilgileri {filename} dosyasına kaydedildi")
            return True
        except Exception as e:
            logging.error(f"Kayıt hatası: {e}")
            return False
    
    def run(self, max_retries=3):
        """
        Bot'u çalıştır ve hesap oluştur
        
        Args:
            max_retries (int): Başarısız olursa maksimum deneme sayısı
        """
        retry_count = 0
        success = False
        
        while not success and retry_count < max_retries:
            try:
                logging.info(f"Deneme {retry_count + 1}/{max_retries} başlatılıyor...")
                
                if not self.create_account():
                    retry_count += 1
                    logging.warning(f"Hesap oluşturma başarısız oldu, tekrar deneniyor ({retry_count}/{max_retries})...")
                    continue
                    
                # URL'yi kontrol et - eğer welcome sayfasındaysa veya API token zaten alındıysa
                # doğrulama adımını atlayabiliriz
                if "welcome" in self.driver.current_url or self.api_token:
                    logging.info("Hesap başarıyla oluşturuldu, doğrulama adımı atlanıyor.")
                else:
                    if not self.verify_email():
                        logging.warning("E-posta doğrulaması başarısız oldu, ancak devam ediliyor...")
                    
                # API token kontrolü
                if not self.api_token:
                    logging.info("API token alınamadı, tekrar deneniyor...")
                    self._get_api_token()
                    
                if not self.save_account_data():
                    logging.warning("Hesap bilgileri kaydedilemedi, ancak devam ediliyor...")
                    
                logging.info("Hesap başarıyla oluşturuldu ve doğrulandı!")
                logging.info(f"Email: {self.account_data['email']}")
                logging.info(f"Password: {self.account_data['password']}")
                logging.info(f"API Token: {self.account_data.get('api_token', 'Alınamadı')}")
                success = True
                
            except Exception as e:
                logging.error(f"Hata oluştu: {e}")
                retry_count += 1
                logging.info(f"Tekrar deneniyor ({retry_count}/{max_retries})...")
            finally:
                if self.driver and not success:
                    self.driver.quit()
                    self.driver = None
        
        if self.driver:
            self.driver.quit()
            
        return success

def create_multiple_accounts(count=1, use_tor=True, tor_browser_path=None):
    """
    Birden fazla hesap oluştur
    
    Args:
        count (int): Oluşturulacak hesap sayısı
        use_tor (bool): Tor kullanılsın mı?
        tor_browser_path (str): Tor Browser'ın yolu
    """
    successful_accounts = []
    
    for i in range(count):
        logging.info(f"\n{'='*50}")
        logging.info(f"Hesap {i+1}/{count} oluşturuluyor...")
        logging.info(f"{'='*50}\n")
        
        bot = EnsembleDataBot(use_tor=use_tor, tor_browser_path=tor_browser_path)
        if bot.run():
            successful_accounts.append(bot.account_data)
        
        # Hesaplar arası bekleme süresi
        if i < count - 1:
            wait_time = random.randint(30, 60)
            logging.info(f"Sonraki hesap için {wait_time} saniye bekleniyor...")
            time.sleep(wait_time)
    
    # Tüm başarılı hesapları tek bir dosyaya kaydet
    if successful_accounts:
        filename = f"ensemble_accounts_batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(successful_accounts, f, indent=4)
        logging.info(f"\nToplam {len(successful_accounts)}/{count} hesap başarıyla oluşturuldu.")
        logging.info(f"Tüm hesap bilgileri {filename} dosyasına kaydedildi.")
    else:
        logging.warning("\nHiçbir hesap oluşturulamadı.")

if __name__ == "__main__":
    # Kullanıcıdan girdi al
    print("\nEnsembleData Hesap Oluşturma Botu")
    print("--------------------------------")
    
    try:
        account_count = int(input("Kaç hesap oluşturmak istiyorsunuz? (varsayılan: 1): ") or "1")
        use_tor_input = input("Tor Browser kullanmak istiyor musunuz? (e/h) (varsayılan: e): ").lower()
        use_tor = use_tor_input != 'h' and use_tor_input != 'hayır'
        
        tor_browser_path = None
        if use_tor:
            print("\nTor Browser'ın yolunu belirtin (boş bırakırsanız otomatik bulunmaya çalışılacak):")
            tor_browser_path = input("Tor Browser yolu: ").strip() or None
            
            if tor_browser_path and not os.path.exists(tor_browser_path):
                print(f"Uyarı: Belirtilen yol ({tor_browser_path}) bulunamadı.")
                continue_anyway = input("Devam etmek istiyor musunuz? (e/h): ").lower()
                if continue_anyway != 'e' and continue_anyway != 'evet':
                    print("İşlem iptal edildi.")
                    sys.exit()
            
            # Tor Browser'ı manuel olarak başlatma talimatları
            print("\n*** ÖNEMLİ: Tor Browser'ı Manuel Olarak Başlatma ***")
            print("1. Tor Browser'ı açın")
            print("2. 'Connect' (Bağlan) düğmesine tıklayın")
            print("3. Tor ağına bağlanmasını bekleyin")
            print("4. Tor Browser'ı arka planda çalışır durumda bırakın")
            print("5. Bu pencereye geri dönün ve Enter tuşuna basın")
            input("\nTor Browser başlatıldıktan sonra Enter tuşuna basın...")
        
        if account_count > 1:
            create_multiple_accounts(account_count, use_tor, tor_browser_path)
        else:
            bot = EnsembleDataBot(use_tor=use_tor, tor_browser_path=tor_browser_path)
            bot.run()
    except KeyboardInterrupt:
        logging.info("\nProgram kullanıcı tarafından durduruldu.")
    except Exception as e:
        logging.error(f"\nBeklenmeyen bir hata oluştu: {e}")