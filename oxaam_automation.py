import asyncio
import random
import string
import json
import subprocess
import re
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

class OxaamAutomation:
    def __init__(self, headless=True, save_results=True):
        self.base_url = "https://www.oxaam.com/"
        self.headless = headless
        self.save_results = save_results
        self.account_credentials = {
            "oxaam_email": "",
            "oxaam_password": "",
            "oxaam_phone": "",
            "created_at": ""
        }
        self.free_accounts = []
        self.session_id = self.generate_session_id()
        self.catbox_url = ""
    
    def generate_session_id(self):
        """Generate unique session ID"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        return f"session_{timestamp}_{random_suffix}"
    
    def generate_random_phone(self):
        """Generate random phone number starting with 869"""
        random_digits = ''.join([str(random.randint(0, 9)) for _ in range(9)])
        return f"869{random_digits}"
    
    def generate_random_email(self):
        """Generate random email with timestamp for uniqueness"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        random_string = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        return f"user_{timestamp}_{random_string}@gmail.com"
    
    def generate_random_name(self):
        """Generate random name"""
        first_names = ["John", "Jane", "Mike", "Sarah", "David", "Emma", "Chris", "Lisa", 
                       "Alex", "Maria", "Ryan", "Sophie", "Tom", "Anna", "Jack", "Emily"]
        last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", 
                      "Davis", "Rodriguez", "Martinez", "Wilson", "Anderson", "Taylor"]
        return f"{random.choice(first_names)} {random.choice(last_names)}"
    
    def generate_strong_password(self):
        """Generate a strong random password"""
        length = random.randint(12, 16)
        chars = string.ascii_letters + string.digits + "!@#$%^&*"
        password = ''.join(random.choices(chars, k=length))
        if not any(c.isupper() for c in password):
            password = password[:-1] + random.choice(string.ascii_uppercase)
        if not any(c.isdigit() for c in password):
            password = password[:-1] + random.choice(string.digits)
        return password
    
    def upload_to_catbox(self, html_content, description="debug"):
        """Upload HTML content directly to catbox.moe and return URL"""
        try:
            print(f"\n📤 Uploading {description} HTML to catbox.moe...")
            
            # Create temp file in memory
            temp_filename = f"oxaam_{description}_{self.session_id}.html"
            temp_path = Path(temp_filename)
            
            # Write content temporarily
            with open(temp_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            # Use curl to upload
            result = subprocess.run(
                [
                    'curl', '-s', '-F', 'reqtype=fileupload',
                    '-F', f'fileToUpload=@{temp_filename}',
                    'https://catbox.moe/user/api.php'
                ],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # Delete temp file immediately
            temp_path.unlink(missing_ok=True)
            
            if result.returncode == 0 and result.stdout:
                url = result.stdout.strip()
                if url.startswith('http'):
                    print(f"✅ Upload successful!")
                    print(f"🔗 {description} URL: {url}")
                    return url
                else:
                    print(f"⚠️  Upload response: {result.stdout}")
                    return None
            else:
                print(f"❌ Upload failed: {result.stderr}")
                return None
                
        except subprocess.TimeoutExpired:
            print("❌ Upload timeout after 30 seconds")
            return None
        except Exception as e:
            print(f"❌ Upload error: {str(e)}")
            return None
        finally:
            # Ensure temp file is deleted
            try:
                temp_path.unlink(missing_ok=True)
            except:
                pass
    
    def extract_credentials_from_html(self, html_content):
        """Extract all credentials from HTML using regex"""
        print("\n🔍 Extracting credentials from HTML...")
        accounts = []
        
        # Find all <details> blocks
        details_pattern = r'<details[^>]*>(.*?)</details>'
        details_blocks = re.findall(details_pattern, html_content, re.DOTALL | re.IGNORECASE)
        
        print(f"📦 Found {len(details_blocks)} service blocks")
        
        for idx, block in enumerate(details_blocks, 1):
            try:
                # Extract service name from summary
                service_name_match = re.search(r'<strong>([^<]+?(?:Premium|PREMIUM|PRO|Plus|AI|TV\+|Music|Games)?[^<]*?)</strong>', block)
                service_name = service_name_match.group(1).strip() if service_name_match else f"Service_{idx}"
                
                print(f"\n{idx}. 🎯 Processing: {service_name}")
                
                # Try to find email
                email = ""
                email_patterns = [
                    r'Email\s*➜\s*<span>([^<]+)</span>',
                    r'Email\s*➜\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
                    r'data-copy="([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})"'
                ]
                
                for pattern in email_patterns:
                    match = re.search(pattern, block)
                    if match:
                        email = match.group(1).strip()
                        break
                
                # Try to find password
                password = ""
                password_patterns = [
                    r'Password\s*➜\s*<span>([^<]+)</span>',
                    r'Password\s*➜\s*([^\s<]+)',
                    r'data-copy="([^"]+)"[^>]*>📋</button>\s*</div>\s*<div[^>]*>.*?Password'
                ]
                
                for pattern in password_patterns:
                    matches = re.findall(pattern, block)
                    if matches:
                        for match in matches:
                            # Skip if it looks like email
                            if '@' not in match and match != email:
                                password = match.strip()
                                break
                    if password:
                        break
                
                # Try to find official website
                official_link = ""
                link_match = re.search(r'href="([^"]*official\.php[^"]*)"', block)
                if link_match:
                    official_link = link_match.group(1)
                    if not official_link.startswith('http'):
                        official_link = f"https://www.oxaam.com/{official_link}"
                
                # Check if this is a cookie-based service
                is_cookie_service = 'cookie' in block.lower() or 'cookiejson' in block.lower()
                
                if email or password or is_cookie_service:
                    account_info = {
                        "service": service_name,
                        "email": email if email else "Cookie-based login",
                        "password": password if password else "N/A",
                        "official_website": official_link if official_link else "N/A",
                        "type": "Cookie-based" if is_cookie_service else "Email/Password",
                        "retrieved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    accounts.append(account_info)
                    
                    print(f"   ✅ Email: {account_info['email']}")
                    print(f"   ✅ Password: {account_info['password']}")
                    print(f"   ✅ Type: {account_info['type']}")
                else:
                    print(f"   ⚠️  No credentials found")
            
            except Exception as e:
                print(f"   ❌ Error processing block: {str(e)}")
                continue
        
        return accounts
    
    async def register_account(self, page):
        """Register a new account on Oxaam with enhanced error handling"""
        print(f"\n{'='*60}")
        print(f"🆕 NEW REGISTRATION SESSION: {self.session_id}")
        print(f"{'='*60}")
        
        print("🔄 Navigating to Oxaam.com...")
        try:
            await page.goto(self.base_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(3000)
        except Exception as e:
            print(f"❌ Failed to load page: {str(e)}")
            return False
        
        # Generate random credentials
        name = self.generate_random_name()
        email = self.generate_random_email()
        phone = self.generate_random_phone()
        password = self.generate_strong_password()
        
        # Store credentials with timestamp
        self.account_credentials["oxaam_email"] = email
        self.account_credentials["oxaam_password"] = password
        self.account_credentials["oxaam_phone"] = phone
        self.account_credentials["created_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        print(f"\n📝 Registering with:")
        print(f"   👤 Name: {name}")
        print(f"   📧 Email: {email}")
        print(f"   📱 Phone: {phone}")
        print(f"   🔑 Password: {password}")
        
        try:
            # Try multiple selector patterns for registration form
            name_selectors = [
                'input[placeholder="Name"]',
                'input[name="name"]',
                'input[id="name"]',
                '#name'
            ]
            
            email_selectors = [
                'input[placeholder="Email"]',
                'input[name="email"]',
                'input[type="email"]',
                '#email'
            ]
            
            phone_selectors = [
                'input[placeholder="Contact No."]',
                'input[name="contact"]',
                'input[name="phone"]',
                '#contact'
            ]
            
            password_selectors = [
                'input[placeholder="Password"]',
                'input[name="password"]',
                'input[type="password"]',
                '#password'
            ]
            
            # Fill name
            for selector in name_selectors:
                try:
                    await page.fill(selector, name, timeout=5000)
                    print("   ✅ Name filled")
                    break
                except:
                    continue
            
            # Fill email
            for selector in email_selectors:
                try:
                    await page.fill(selector, email, timeout=5000)
                    print("   ✅ Email filled")
                    break
                except:
                    continue
            
            # Fill phone
            for selector in phone_selectors:
                try:
                    await page.fill(selector, phone, timeout=5000)
                    print("   ✅ Phone filled")
                    break
                except:
                    continue
            
            # Fill password
            for selector in password_selectors:
                try:
                    await page.fill(selector, password, timeout=5000)
                    print("   ✅ Password filled")
                    break
                except:
                    continue
            
            await page.wait_for_timeout(1000)
            
            # Click register button
            register_selectors = [
                'button:has-text("Register")',
                'button[type="submit"]',
                'input[type="submit"]',
                'button:has-text("Sign up")'
            ]
            
            for selector in register_selectors:
                try:
                    await page.click(selector, timeout=5000)
                    print("   ✅ Register button clicked")
                    break
                except:
                    continue
            
            await page.wait_for_timeout(4000)
            
            print("✅ Account registered successfully!")
            return True
            
        except Exception as e:
            print(f"❌ Error during registration: {str(e)}")
            return False
    
    async def browse_free_services(self, page):
        """Navigate to Browse Free Services with better error handling"""
        print("\n🔄 Navigating to Browse Free Services...")
        
        try:
            # Try multiple methods to find the link
            link_selectors = [
                'a:has-text("Browse Free Services")',
                'a:has-text("Free Services")',
                'text=/Browse.*Free.*Services/i',
                '[href*="free"]',
                'a[href*="browse"]'
            ]
            
            for selector in link_selectors:
                try:
                    await page.click(selector, timeout=5000)
                    await page.wait_for_timeout(3000)
                    print("✅ Navigated to Free Services page")
                    return True
                except:
                    continue
            
            print("⚠️  Could not find Free Services link, trying direct URL...")
            await page.goto(f"{self.base_url}freeservice.php", wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)
            return True
            
        except Exception as e:
            print(f"❌ Error navigating to free services: {str(e)}")
            return False
    
    async def extract_all_accounts(self, page):
        """Extract all accounts from the page HTML"""
        print("\n🎬 Extracting all free accounts from page...")
        
        try:
            # Get the full page HTML
            print("📸 Capturing page HTML...")
            html_content = await page.content()
            
            # Upload to catbox
            catbox_url = self.upload_to_catbox(html_content, "free_services_page")
            if catbox_url:
                self.catbox_url = catbox_url
            
            # Extract credentials from HTML
            accounts = self.extract_credentials_from_html(html_content)
            
            if accounts:
                print(f"\n✅ Successfully extracted {len(accounts)} accounts!")
                self.free_accounts.extend(accounts)
                
                # Add catbox URL to each account
                for account in self.free_accounts:
                    account['debug_html_url'] = catbox_url if catbox_url else "N/A"
            else:
                print("⚠️  No accounts found in HTML")
            
            return len(accounts) > 0
            
        except Exception as e:
            print(f"❌ Error extracting accounts: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    def save_to_file(self):
        """Save results to JSON file"""
        if not self.save_results:
            return
        
        try:
            filename = f"oxaam_results_{self.session_id}.json"
            data = {
                "session_id": self.session_id,
                "oxaam_account": self.account_credentials,
                "free_accounts": self.free_accounts,
                "total_accounts": len(self.free_accounts),
                "debug_html_url": self.catbox_url if self.catbox_url else "N/A"
            }
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            
            print(f"\n💾 Results saved to: {filename}")
        
        except Exception as e:
            print(f"⚠️  Could not save results: {str(e)}")
    
    def print_summary(self):
        """Print summary of all accounts"""
        print("\n" + "="*60)
        print("📊 AUTOMATION SUMMARY")
        print("="*60)
        print(f"🆔 Session ID: {self.session_id}")
        
        print("\n🔐 Oxaam Account Credentials:")
        print(f"   📧 Email: {self.account_credentials['oxaam_email']}")
        print(f"   🔑 Password: {self.account_credentials['oxaam_password']}")
        print(f"   📱 Phone: {self.account_credentials['oxaam_phone']}")
        print(f"   🕐 Created: {self.account_credentials['created_at']}")
        
        if self.catbox_url:
            print(f"\n🐛 Debug HTML URL: {self.catbox_url}")
        
        print(f"\n🎁 Free Accounts Retrieved: {len(self.free_accounts)}")
        print("-"*60)
        
        for i, account in enumerate(self.free_accounts, 1):
            print(f"\n{i}. {account['service']}")
            print(f"   📧 Email: {account['email']}")
            print(f"   🔑 Password: {account['password']}")
            print(f"   🔗 Website: {account['official_website']}")
            print(f"   📌 Type: {account['type']}")
        
        print("\n" + "="*60)
    
    async def run(self):
        """Main execution method"""
        async with async_playwright() as p:
            print(f"🚀 Starting Oxaam Automation (Headless: {self.headless})...")
            
            # Launch browser with enhanced settings
            browser = await p.chromium.launch(
                headless=self.headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-dev-shm-usage'
                ]
            )
            
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            
            page = await context.new_page()
            
            try:
                # Step 1: Register new account
                if not await self.register_account(page):
                    print("❌ Registration failed, aborting...")
                    return
                
                # Step 2: Navigate to free services
                if not await self.browse_free_services(page):
                    print("⚠️  Could not navigate to free services")
                    return
                
                # Step 3: Extract all accounts from HTML
                await self.extract_all_accounts(page)
                
                # Print summary
                self.print_summary()
                
                # Save to file
                self.save_to_file()
                
                # Wait before closing
                if not self.headless:
                    print("\n⏳ Waiting 5 seconds before closing...")
                    await page.wait_for_timeout(5000)
                
            except Exception as e:
                print(f"\n❌ Error during automation: {str(e)}")
                import traceback
                traceback.print_exc()
            
            finally:
                await browser.close()
                print("\n✅ Automation completed!")
