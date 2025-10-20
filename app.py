import asyncio
import json
import threading
import time
from datetime import datetime
from flask import Flask, jsonify
import os
from pathlib import Path

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

# History of all scraping sessions
scraping_history = []
history_file = "oxaam_scraping_history.json"

def load_history():
    """Load scraping history from file"""
    global scraping_history
    try:
        if Path(history_file).exists():
            with open(history_file, 'r') as f:
                scraping_history = json.load(f)
    except Exception as e:
        print(f"⚠️  Could not load history: {str(e)}")
        scraping_history = []

def save_to_history(session_data):
    """Save session data to history"""
    global scraping_history
    try:
        scraping_history.append(session_data)
        with open(history_file, 'w') as f:
            json.dump(scraping_history, f, indent=2)
    except Exception as e:
        print(f"⚠️  Could not save to history: {str(e)}")

# Load history on startup
load_history()

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
            "/latest": "Get the latest scraped results without running a new scrape",
            "/logs": "View all scraping history from the beginning"
        },
        "usage": {
            "accounts": "GET /accounts to start scraping and get results",
            "status": "GET /status to check if scraping is running",
            "health": "GET /health to check if the service is running",
            "latest": "GET /latest to get the most recent results",
            "logs": "GET /logs to view all scraping history"
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

@app.route('/logs')
def logs():
    """View all scraping history from the beginning"""
    if not scraping_history:
        return jsonify({
            "status": "info",
            "message": "No scraping history available yet",
            "total_sessions": 0,
            "history": []
        })
    
    # Sort history by timestamp (newest first)
    sorted_history = sorted(scraping_history, key=lambda x: x.get("timestamp", ""), reverse=True)
    
    # Calculate total accounts across all sessions
    total_accounts = sum(session.get("total_accounts", 0) for session in scraping_history)
    
    return jsonify({
        "status": "success",
        "message": "Returning complete scraping history",
        "total_sessions": len(scraping_history),
        "total_accounts_all_time": total_accounts,
        "history": sorted_history
    })

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
            
            # Save to history
            save_to_history(latest_results.copy())
            
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
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
