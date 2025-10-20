import asyncio
import json
import threading
import time
from datetime import datetime
from flask import Flask, jsonify, request
from werkzeug.serving import make_server
import os

# Import your OxaamAutomation class
from oxaam_automation import OxaamAutomation

app = Flask(__name__)

# Global variables to track scraping status
scraping_status = {
    "is_running": False,
    "started_at": None,
    "completed_at": None,
    "current_task": "",
    "progress": 0,
    "error": None,
    "results": None
}

# Store the latest results
latest_results = {
    "session_id": None,
    "oxaam_account": None,
    "free_accounts": [],
    "total_accounts": 0,
    "debug_html_url": None,
    "timestamp": None
}

@app.route('/')
def index():
    """API documentation endpoint"""
    return jsonify({
        "title": "Oxaam Account Scraper API",
        "version": "1.0.0",
        "endpoints": {
            "/": "API documentation (this page)",
            "/accounts": "Run the scraping process and return accounts in JSON",
            "/status": "Check the current scraping status",
            "/health": "Health check endpoint",
            "/latest": "Get the latest scraped results without running a new scrape"
        },
        "usage": {
            "accounts": "GET /accounts to start scraping and get results",
            "status": "GET /status to check if scraping is running",
            "health": "GET /health to check if the service is running",
            "latest": "GET /latest to get the most recent results"
        }
    })

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "uptime": "Service is running"
    })

@app.route('/status')
def status():
    """Check scraping progress"""
    return jsonify(scraping_status)

@app.route('/latest')
def latest():
    """Get the latest scraped results without running a new scrape"""
    if latest_results["timestamp"]:
        return jsonify({
            "status": "success",
            "data": latest_results,
            "message": "Returning latest scraped results"
        })
    else:
        return jsonify({
            "status": "error",
            "message": "No results available yet. Please run /accounts first."
        }), 404

@app.route('/accounts')
def get_accounts():
    """Run the scraping process and return accounts in JSON"""
    global scraping_status, latest_results
    
    # Check if scraping is already running
    if scraping_status["is_running"]:
        return jsonify({
            "status": "error",
            "message": "Scraping is already in progress. Please check /status for progress."
        }), 409
    
    # Start scraping in a background thread
    def run_scraping():
        global scraping_status, latest_results
        
        try:
            # Update status
            scraping_status["is_running"] = True
            scraping_status["started_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            scraping_status["current_task"] = "Initializing"
            scraping_status["progress"] = 0
            scraping_status["error"] = None
            scraping_status["results"] = None
            
            # Create automation instance
            scraping_status["current_task"] = "Creating automation instance"
            scraping_status["progress"] = 10
            automation = OxaamAutomation(headless=True, save_results=False)
            
            # Override methods to update status
            original_register = automation.register_account
            async def register_with_status(page):
                scraping_status["current_task"] = "Registering new account"
                scraping_status["progress"] = 20
                return await original_register(page)
            automation.register_account = register_with_status
            
            original_browse = automation.browse_free_services
            async def browse_with_status(page):
                scraping_status["current_task"] = "Navigating to free services"
                scraping_status["progress"] = 40
                return await original_browse(page)
            automation.browse_free_services = browse_with_status
            
            original_extract = automation.extract_all_accounts
            async def extract_with_status(page):
                scraping_status["current_task"] = "Extracting accounts"
                scraping_status["progress"] = 60
                result = await original_extract(page)
                scraping_status["progress"] = 80
                return result
            automation.extract_all_accounts = extract_with_status
            
            # Run the automation
            scraping_status["current_task"] = "Starting browser automation"
            scraping_status["progress"] = 5
            asyncio.run(automation.run())
            
            # Update latest results
            latest_results = {
                "session_id": automation.session_id,
                "oxaam_account": automation.account_credentials,
                "free_accounts": automation.free_accounts,
                "total_accounts": len(automation.free_accounts),
                "debug_html_url": automation.catbox_url if hasattr(automation, 'catbox_url') else None,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            # Update status
            scraping_status["current_task"] = "Completed"
            scraping_status["progress"] = 100
            scraping_status["results"] = latest_results
            scraping_status["completed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
        except Exception as e:
            scraping_status["error"] = str(e)
            scraping_status["current_task"] = "Error occurred"
            scraping_status["completed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        finally:
            scraping_status["is_running"] = False
    
    # Start the background thread
    thread = threading.Thread(target=run_scraping)
    thread.daemon = True
    thread.start()
    
    # Return initial response
    return jsonify({
        "status": "started",
        "message": "Scraping process started. Check /status for progress.",
        "status_url": "/status"
    })

if __name__ == '__main__':
    # Install Playwright browsers on first run
    import subprocess
    try:
        print("Installing Playwright browsers...")
        subprocess.run(["playwright", "install", "chromium"], check=True)
        print("Playwright browsers installed successfully!")
    except Exception as e:
        print(f"Error installing Playwright browsers: {e}")
        print("Trying alternative installation method...")
        try:
            subprocess.run(["python", "-m", "playwright", "install", "chromium"], check=True)
            print("Playwright browsers installed successfully!")
        except Exception as e2:
            print(f"Error with alternative installation: {e2}")
            print("Please ensure Playwright browsers are installed manually.")
    
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
