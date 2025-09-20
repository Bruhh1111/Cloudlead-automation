#!/usr/bin/env python3
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
        """Get projects with status 'New' using Airtable filter"""
        try:
            logging.info("🔍 Checking for new projects...")
            
            # Use Airtable's filter to get ONLY "New" projects
            params = {
                "filterByFormula": "{Status} = 'New'"
            }
            
            response = requests.get(
                f"{self.base_url}/Projects", 
                headers=self.headers, 
                params=params
            )
            
            if response.status_code == 200:
                projects = response.json().get("records", [])
                logging.info(f"✅ Found {len(projects)} new projects")
                return projects
            else:
                logging.error(f"❌ Airtable API error: {response.status_code} - {response.text}")
                return []
                
        except Exception as e:
            logging.error(f"💥 Exception in get_new_projects: {str(e)}")
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
            if response.status_code == 200:
                logging.info(f"✅ Updated project {project_id} to {status}")
                return True
            else:
                logging.error(f"❌ Failed to update project: {response.text}")
                return False
        except Exception as e:
            logging.error(f"💥 Error updating project: {e}")
            return False
    
    def add_leads(self, project_id, leads):
        """Add leads to Airtable"""
        if not leads:
            logging.warning("⚠️ No leads to add")
            return True
            
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
            # Split into batches of 10 (Airtable limit)
            for i in range(0, len(records), 10):
                batch = records[i:i+10]
                response = requests.post(
                    f"{self.base_url}/Leads", 
                    headers=self.headers, 
                    json={"records": batch}
                )
                
                if response.status_code == 200:
                    logging.info(f"✅ Added batch of {len(batch)} leads")
                else:
                    logging.error(f"❌ Failed to add leads: {response.text}")
                    return False
                    
            return True
            
        except Exception as e:
            logging.error(f"💥 Error adding leads: {e}")
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
            ],
            "Healthcare": [
                {"company": "MedTech Solutions", "name": "Dr. James Wilson", "title": "Chief Medical Officer", "email": "james@medtech.com", "website": "medtech.com"},
                {"company": "BioHealth Labs", "name": "Lisa Anderson", "title": "Research Director", "email": "lisa@biohealth.com", "website": "biohealth.com"}
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
        project_name = fields.get("Project Name", "Unknown Project")
        
        logging.info(f"🚀 Processing project: {project_name}")
        
        # Update status to in progress
        if not self.update_project_status(project_id, "In Progress"):
            logging.error(f"❌ Failed to update project status to In Progress")
            return
        
        # Generate leads
        industry = fields.get("Industry", "Technology")
        lead_count = fields.get("Lead Count", 10) or 10
        leads = self.generate_leads(industry, lead_count)
        
        logging.info(f"📊 Generated {len(leads)} leads for {project_name}")
        
        # Add to Airtable
        if self.add_leads(project_id, leads):
            self.update_project_status(project_id, "Completed", len(leads))
            logging.info(f"✅ Completed project {project_name} with {len(leads)} leads")
        else:
            self.update_project_status(project_id, "Failed")
            logging.error(f"❌ Failed to process project {project_name}")

    def run(self):
        """Main automation loop"""
        logging.info("🏁 Starting CloudLead Production Automation")
        
        while True:
            try:
                projects = self.get_new_projects()
                
                if projects:
                    logging.info(f"🎯 Processing {len(projects)} new projects")
                    for project in projects:
                        self.process_project(project)
                else:
                    logging.info("⏰ No new projects found. Checking again in 60 seconds.")
                
                time.sleep(60)
                
            except KeyboardInterrupt:
                logging.info("🛑 Automation stopped by user")
                break
            except Exception as e:
                logging.error(f"💥 Error in main loop: {e}")
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
            logging.info("✅ Project created via webhook")
            return jsonify({"status": "success", "message": "Project created successfully"})
        else:
            logging.error(f"❌ Webhook error: {response.text}")
            return jsonify({"status": "error", "message": response.text}), 400
            
    except Exception as e:
        logging.error(f"💥 Webhook exception: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    # Start web server for webhooks
    from threading import Thread
    port = int(os.getenv('PORT', 5000))
    
    # Start both web server and automation
    Thread(target=lambda: app.run(host='0.0.0.0', port=port, debug=False)).start()
    
    # Give web server a moment to start
    time.sleep(2)
    
    # Start automation
    automation = CloudLeadProduction()
    automation.run()
