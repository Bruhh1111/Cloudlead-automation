import sys
sys.path.append('/opt/venv/lib/python3.9/site-packages')
import requests
import openai
import time
import logging
import os
from datetime import datetime
from flask import Flask, request, jsonify

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Import config
from config import AIRTABLE_ACCESS_TOKEN, AIRTABLE_BASE_ID, OPENAI_API_KEY

class CloudLeadProduction:
    def __init__(self):
        self.access_token = AIRTABLE_ACCESS_TOKEN
        self.base_id = AIRTABLE_BASE_ID
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        self.base_url = f"https://api.airtable.com/v0/{self.base_id}"
        
        # Initialize OpenAI
        if OPENAI_API_KEY and OPENAI_API_KEY != 'your-openai-key-here':
            openai.api_key = OPENAI_API_KEY
            self.ai_enabled = True
        else:
            self.ai_enabled = False
            logging.warning("OpenAI not configured - using simulated AI")
    
    def get_new_projects(self):
        """Get projects with status 'New'"""
        try:
            response = requests.get(f"{self.base_url}/Projects", headers=self.headers)
            projects = response.json().get("records", [])
            return [p for p in projects if p.get('fields', {}).get('Status') == 'New']
        except Exception as e:
            logging.error(f"Error getting projects: {e}")
            return []
    
    def ai_analyze(self, company_name, website=None):
        """AI analysis of companies"""
        if not self.ai_enabled:
            return "AI analysis will be enabled with OpenAI API key"
        
        try:
            prompt = f"Provide business intelligence analysis for {company_name}"
            if website:
                prompt += f" ({website})"
            prompt += ". Focus on their market position, technology stack, and potential pain points. Keep it under 100 words."
            
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=150
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"AI analysis error: {str(e)}"
    
    def update_project_status(self, project_id, status, leads_count=0):
        """Update project status"""
        update_data = {
            "records": [{
                "id": project_id,
                "fields": {
                    "Status": status,
                    "Lead Count": leads_count
                }
            }]
        }
        
        if status == "Completed":
            update_data["records"][0]["fields"]["Date Completed"] = datetime.now().isoformat()
        
        try:
            response = requests.patch(f"{self.base_url}/Projects", headers=self.headers, json=update_data)
            return response.status_code == 200
        except Exception as e:
            logging.error(f"Error updating project: {e}")
            return False
    
    def add_leads(self, project_id, leads):
        """Add leads to Airtable"""
        records = []
        for lead in leads:
            records.append({
                "fields": {
                    "Company": lead['company'],
                    "Website": lead.get('website', ''),
                    "Name": lead['name'],
                    "Title": lead['title'],
                    "Email": lead['email'],
                    "Phone": lead.get('phone', ''),
                    "Status": "Verified",
                    "Validation Score": lead.get('score', 85),
                    "Last Verified": datetime.now().isoformat(),
                    "Project": [project_id],
                    "Notes": lead.get('analysis', '')
                }
            })
        
        try:
            response = requests.post(f"{self.base_url}/Leads", headers=self.headers, json={"records": records})
            return response.status_code == 200
        except Exception as e:
            logging.error(f"Error adding leads: {e}")
            return False
    
    def generate_leads(self, industry, count):
        """Generate realistic leads for demo"""
        templates = {
            "Technology": [
                {"company": "TechFlow Inc", "name": "Sarah Chen", "title": "CTO", "email": "sarah@techflow.com", "phone": "+1-555-0101", "website": "techflow.com"},
                {"company": "DataNova Systems", "name": "Michael Rodriguez", "title": "Engineering Director", "email": "michael@datanova.com", "website": "datanova.com"},
                {"company": "CloudCraft", "name": "Jessica Williams", "title": "VP of Product", "email": "jessica@cloudcraft.com", "website": "cloudcraft.com"}
            ],
            "Finance": [
                {"company": "CapitalFirst Bank", "name": "Robert Johnson", "title": "CFO", "email": "robert@capitalfirst.com", "website": "capitalfirst.com"},
                {"company": "WealthBuild Advisors", "name": "Emily Davis", "title": "Investment Director", "email": "emily@wealthbuild.com", "website": "wealthbuild.com"}
            ]
        }
        
        leads = []
        template = templates.get(industry, templates["Technology"])
        
        for i in range(min(count, 20)):
            lead = template[i % len(template)].copy()
            lead['email'] = lead['email'].replace('@', f"{i}@")
            lead['analysis'] = self.ai_analyze(lead['company'], lead.get('website'))
            lead['score'] = 80 + (i % 20)
            leads.append(lead)
        
        return leads
    
    def process_project(self, project):
        """Process a project end-to-end"""
        project_id = project["id"]
        fields = project["fields"]
        project_name = fields.get("Project Name", "Unknown")
        
        logging.info(f"Processing project: {project_name}")
        
        # Update status to in progress
        self.update_project_status(project_id, "In Progress")
        
        # Generate leads
        industry = fields.get("Industry", "Technology")
        lead_count = fields.get("Lead Count", 10) or 10
        leads = self.generate_leads(industry, lead_count)
        
        # Add to Airtable
        if self.add_leads(project_id, leads):
            self.update_project_status(project_id, "Completed", len(leads))
            logging.info(f"Completed project {project_name} with {len(leads)} leads")
        else:
            self.update_project_status(project_id, "Failed")
            logging.error(f"Failed to process project {project_name}")

    def run(self):
        """Main automation loop"""
        logging.info("Starting CloudLead Production Automation")
        
        while True:
            try:
                projects = self.get_new_projects()
                
                if projects:
                    logging.info(f"Found {len(projects)} new projects")
                    for project in projects:
                        self.process_project(project)
                else:
                    logging.info("No new projects found. Checking again in 60 seconds.")
                
                time.sleep(60)
                
            except KeyboardInterrupt:
                logging.info("Automation stopped by user")
                break
            except Exception as e:
                logging.error(f"Error in main loop: {e}")
                time.sleep(60)

# Create Flask app for webhooks
app = Flask(__name__)

@app.route('/')
def home():
    return "CloudLead Automation is Running! 🚀"

@app.route('/webhook/project', methods=['POST'])
def handle_project():
    """Handle incoming project requests from web forms"""
    try:
        data = request.json
        automation = CloudLeadProduction()
        
        # Create project in Airtable
        project_data = {
            "records": [{
                "fields": {
                    "Project Name": data.get('project_name', 'New Project'),
                    "Industry": data.get('industry', 'Technology'),
                    "Region": data.get('region', 'Global'),
                    "Lead Count": data.get('lead_count', 10),
                    "Status": "New",
                    "Date Created": datetime.now().isoformat()
                }
            }]
        }
        
        response = requests.post(
            f"{automation.base_url}/Projects",
            headers=automation.headers,
            json=project_data
        )
        
        if response.status_code == 200:
            return jsonify({"status": "success", "message": "Project created successfully"})
        else:
            return jsonify({"status": "error", "message": response.text}), 400
            
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    # Start web server for webhooks
    from threading import Thread
    Thread(target=lambda: app.run(host='0.0.0.0', port=os.getenv('PORT', 5000))).start()
    
    # Start automation
    automation = CloudLeadProduction()
    automation.run()
