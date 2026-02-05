#!/usr/bin/env python3
"""
Mail Screenshot RAG System

This system analyzes screenshots saved by the mail agent and generates a comprehensive report
summarizing email content, senders, types, and importance levels.
"""

import argparse
import os
import sys
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from collections import Counter

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agent.model import OpenAIAgent, QwenVLAgent
from agent.utils import image_to_base64


class MailScreenshotAnalyzer:
    """Analyzes individual email screenshots to extract email information."""
    
    def __init__(self, agent):
        self.agent = agent
    
    def analyze_email_screenshot(self, screenshot_path: str) -> Dict[str, Any]:
        """
        Analyze a single email screenshot and extract email information.
        
        Args:
            screenshot_path: Path to the screenshot image
            
        Returns:
            Dictionary containing extracted email information
        """
        prompt = """Please analyze this email screenshot carefully and extract the following information:

1. **Sender**: Who sent this email? (extract the sender's name and email address if visible)
2. **Subject**: What is the email subject line?
3. **Content Summary**: Provide a brief summary of the email content (2-3 sentences). For emails that you judge as very important (importance level 5), make this summary more detailed (3-5 sentences) and clearly describe the main request, deadlines, and required actions.
4. **Email Type**: Classify this email into one of these categories:
   - Work/Business
   - Personal/Social
   - Newsletter/Marketing
   - Notification/System
   - Spam/Junk
   - Other
5. **Importance Level**: Rate the importance on a scale of 1-5:
   - 5: Critical/Urgent (requires immediate attention)
   - 4: High (important, should respond soon)
   - 3: Medium (moderate importance)
   - 2: Low (can be handled later)
   - 1: Very Low/Informational (no action needed)
6. **Date/Time**: Extract the date and time if visible
7. **Key Information**: Any important details, deadlines, or action items mentioned

Please format your response as JSON with the following structure:
{
    "sender": "sender name and email",
    "subject": "email subject",
    "content_summary": "brief summary",
    "email_type": "one of the categories above",
    "importance_level": 1-5,
    "date_time": "date and time if visible",
    "key_information": "important details"
}

If any information is not visible or cannot be determined, use "N/A" or null."""

        try:
            # Create message with screenshot
            # messages = self.agent.prompt_to_message_cloud(prompt, [screenshot_path])
            messages = self.agent.prompt_to_message_visual(prompt, screenshot_path)
            
            # Add system prompt
            system_prompt = [{
                "role": "system",
                "content": "You are an expert email analyst. Analyze email screenshots carefully and extract structured information. Always respond with valid JSON format."
            }]
            
            # Get response from agent
            response = self.agent.act([*system_prompt, *messages])
            
            # Try to extract JSON from response
            email_info = self._parse_response(response)
            
            # Add screenshot path for reference
            email_info["screenshot_path"] = screenshot_path
            
            return email_info
            
        except Exception as e:
            print(f"Error analyzing screenshot {screenshot_path}: {e}")
            return {
                "sender": "N/A",
                "subject": "N/A",
                "content_summary": f"Error analyzing screenshot: {str(e)}",
                "email_type": "Other",
                "importance_level": 1,
                "date_time": "N/A",
                "key_information": "N/A",
                "screenshot_path": screenshot_path,
                "error": str(e)
            }
    
    def _parse_response(self, response: str) -> Dict[str, Any]:
        """Parse the agent's response to extract JSON."""
        # Try to find JSON in the response
        json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        
        # If no JSON found, try to extract information manually
        result = {
            "sender": "N/A",
            "subject": "N/A",
            "content_summary": response[:500],  # Use first 500 chars as summary
            "email_type": "Other",
            "importance_level": 3,
            "date_time": "N/A",
            "key_information": "N/A"
        }
        
        # Try to extract sender
        sender_match = re.search(r'sender[:\s]+([^\n]+)', response, re.IGNORECASE)
        if sender_match:
            result["sender"] = sender_match.group(1).strip()
        
        # Try to extract subject
        subject_match = re.search(r'subject[:\s]+([^\n]+)', response, re.IGNORECASE)
        if subject_match:
            result["subject"] = subject_match.group(1).strip()
        
        return result


class MailRAGSystem:
    """Main RAG system for analyzing mail screenshots and generating reports."""
    
    def __init__(self, agent, screenshot_dir: str):
        self.agent = agent
        self.screenshot_dir = screenshot_dir
        self.analyzer = MailScreenshotAnalyzer(agent)
        self.email_data: List[Dict[str, Any]] = []
    
    def find_email_screenshots(self) -> List[str]:
        """
        Find all email content screenshots (not labeled screenshots, not list screenshots).
        
        Returns:
            List of screenshot paths
        """
        screenshot_paths = []
        
        if not os.path.exists(self.screenshot_dir):
            print(f"Warning: Screenshot directory does not exist: {self.screenshot_dir}")
            return screenshot_paths
        
        # Get all PNG files
        for file in sorted(os.listdir(self.screenshot_dir)):
            if file.endswith('.png') and not file.endswith('_labeled.png'):
                # Skip the "end" screenshot and very early screenshots (likely not email content)
                if 'end' not in file.lower():
                    file_path = os.path.join(self.screenshot_dir, file)
                    screenshot_paths.append(file_path)
        
        # Filter to likely email content screenshots
        # Typically, email content screenshots are in the middle-to-late part of the sequence
        # We'll analyze all non-labeled screenshots and let the model determine if it's email content
        return screenshot_paths
    
    def analyze_screenshots(self, max_screenshots: Optional[int] = None):
        """Analyze all email screenshots."""
        screenshots = self.find_email_screenshots()
        
        if max_screenshots:
            screenshots = screenshots[:max_screenshots]
        
        print(f"Found {len(screenshots)} screenshots to analyze")
        
        for i, screenshot_path in enumerate(screenshots, 1):
            print(f"\nAnalyzing screenshot {i}/{len(screenshots)}: {os.path.basename(screenshot_path)}")
            
            # Analyze the screenshot
            email_info = self.analyzer.analyze_email_screenshot(screenshot_path)
            
            # Filter out screenshots that are clearly not email content
            # (e.g., home screen, mail list, etc.)
            if self._is_email_content(email_info):
                self.email_data.append(email_info)
                print(f"  ✓ Extracted email: {email_info.get('subject', 'N/A')[:50]}")
            else:
                print(f"  ⊘ Skipped (not email content)")
    
    def _is_email_content(self, email_info: Dict[str, Any]) -> bool:
        """Check if the analyzed content is actually an email (not a list or other screen)."""
        subject = email_info.get('subject', '').lower()
        summary = email_info.get('content_summary', '').lower()
        
        # If it has a clear subject and summary, it's likely email content
        if subject and subject != 'n/a' and len(subject) > 3:
            return True
        
        # If summary mentions email-specific terms
        email_indicators = ['email', 'mail', 'message', 'sent', 'received', 'subject', 'from']
        if any(indicator in summary for indicator in email_indicators):
            return True
        
        # If it's clearly not email content
        list_indicators = ['list', 'inbox', 'folder', 'mail list', 'email list']
        if any(indicator in summary for indicator in list_indicators) and not subject:
            return False
        
        # Default: assume it's email content if we got some information
        return len(summary) > 20
    
    def remove_duplicates(self):
        """Remove duplicate emails based on sender and subject combination."""
        if not self.email_data:
            return
        
        seen_emails = {}
        unique_emails = []
        duplicates_count = 0
        
        for email in self.email_data:
            sender = email.get('sender', 'N/A').strip()
            subject = email.get('subject', 'N/A').strip()
            
            # Create a key from sender and subject
            # Normalize: remove extra spaces, convert to lowercase for comparison
            sender_normalized = ' '.join(sender.lower().split()) if sender != 'N/A' else 'N/A'
            subject_normalized = ' '.join(subject.lower().split()) if subject != 'N/A' else 'N/A'
            
            # Skip if both are N/A (likely invalid email)
            if sender_normalized == 'n/a' and subject_normalized == 'n/a':
                # Keep it but mark as potential duplicate
                unique_emails.append(email)
                continue
            
            # Create unique key
            email_key = f"{sender_normalized}|||{subject_normalized}"
            
            if email_key in seen_emails:
                duplicates_count += 1
                # Keep the one with more information (longer content summary)
                existing = seen_emails[email_key]
                existing_summary_len = len(existing.get('content_summary', ''))
                new_summary_len = len(email.get('content_summary', ''))
                
                if new_summary_len > existing_summary_len:
                    # Replace with more detailed version
                    idx = unique_emails.index(existing)
                    unique_emails[idx] = email
                    seen_emails[email_key] = email
            else:
                seen_emails[email_key] = email
                unique_emails.append(email)
        
        if duplicates_count > 0:
            print(f"\nRemoved {duplicates_count} duplicate email(s)")
            print(f"Before deduplication: {len(self.email_data)} emails")
            print(f"After deduplication: {len(unique_emails)} emails")
        
        self.email_data = unique_emails
    
    def generate_report(self) -> str:
        """Generate a comprehensive report from analyzed email data."""
        if not self.email_data:
            return "No email data found. Please analyze screenshots first."
        
        # Note: Duplicates should be removed before calling generate_report
        # (called in main() after analyze_screenshots)
        
        # Group emails by type
        emails_by_type = {}
        for email in self.email_data:
            email_type = email.get('email_type', 'Other')
            if email_type not in emails_by_type:
                emails_by_type[email_type] = []
            emails_by_type[email_type].append(email)
        
        # Sort by importance
        sorted_emails = sorted(self.email_data, key=lambda x: x.get('importance_level', 3), reverse=True)
        
        # Generate report
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("MAIL CONTENT ANALYSIS REPORT")
        report_lines.append("=" * 80)
        report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"Total Emails Analyzed: {len(self.email_data)}")
        report_lines.append("")
        
        # Summary by type
        report_lines.append("SUMMARY BY EMAIL TYPE")
        report_lines.append("-" * 80)
        for email_type, emails in sorted(emails_by_type.items()):
            report_lines.append(f"{email_type}: {len(emails)} email(s)")
        report_lines.append("")
        
        # Summary by importance
        report_lines.append("SUMMARY BY IMPORTANCE LEVEL")
        report_lines.append("-" * 80)
        importance_counts = {5: 0, 4: 0, 3: 0, 2: 0, 1: 0}
        for email in self.email_data:
            level = email.get('importance_level', 3)
            if level in importance_counts:
                importance_counts[level] += 1
        
        importance_labels = {
            5: "Critical/Urgent",
            4: "High",
            3: "Medium",
            2: "Low",
            1: "Very Low/Informational"
        }
        
        for level in sorted(importance_counts.keys(), reverse=True):
            count = importance_counts[level]
            if count > 0:
                report_lines.append(f"Level {level} ({importance_labels[level]}): {count} email(s)")
        report_lines.append("")

        # Highlight highest-importance emails (level 5) in a dedicated section
        highest_importance_emails = [
            e for e in sorted_emails if e.get('importance_level', 3) == 5
        ]
        if highest_importance_emails:
            report_lines.append("HIGHEST IMPORTANCE EMAILS (LEVEL 5)")
            report_lines.append("-" * 80)
            for i, email in enumerate(highest_importance_emails, 1):
                report_lines.append(f"\nHigh-Priority Email #{i}")
                report_lines.append(f"  Sender: {email.get('sender', 'N/A')}")
                report_lines.append(f"  Subject: {email.get('subject', 'N/A')}")
                report_lines.append(f"  Type: {email.get('email_type', 'N/A')}")
                report_lines.append(f"  Date/Time: {email.get('date_time', 'N/A')}")
                report_lines.append(f"  Importance: {email.get('importance_level', 'N/A')}/5")
                report_lines.append(f"  Content Summary: {email.get('content_summary', 'N/A')}")
                if email.get('key_information'):
                    report_lines.append(f"  Key Information: {email.get('key_information', 'N/A')}")
                if email.get('screenshot_path'):
                    report_lines.append(f"  Screenshot: {email.get('screenshot_path')}")
                report_lines.append("")
            report_lines.append("")
        
        # Detailed email information
        report_lines.append("DETAILED EMAIL INFORMATION")
        report_lines.append("-" * 80)
        
        for i, email in enumerate(sorted_emails, 1):
            report_lines.append(f"\nEmail #{i}")
            report_lines.append(f"  Sender: {email.get('sender', 'N/A')}")
            report_lines.append(f"  Subject: {email.get('subject', 'N/A')}")
            report_lines.append(f"  Type: {email.get('email_type', 'N/A')}")
            report_lines.append(f"  Importance: {email.get('importance_level', 'N/A')}/5")
            report_lines.append(f"  Date/Time: {email.get('date_time', 'N/A')}")
            report_lines.append(f"  Content Summary: {email.get('content_summary', 'N/A')}")
            if email.get('key_information'):
                report_lines.append(f"  Key Information: {email.get('key_information', 'N/A')}")
            report_lines.append("")
        
        # Statistics
        report_lines.append("STATISTICS")
        report_lines.append("-" * 80)
        if self.email_data:
            avg_importance = sum(e.get('importance_level', 3) for e in self.email_data) / len(self.email_data)
            report_lines.append(f"Average Importance Level: {avg_importance:.2f}/5")
            
            # Most common sender
            senders = [e.get('sender', 'N/A') for e in self.email_data if e.get('sender') != 'N/A']
            if senders:
                sender_counts = Counter(senders)
                most_common = sender_counts.most_common(1)[0]
                report_lines.append(f"Most Common Sender: {most_common[0]} ({most_common[1]} email(s))")
        
        report_lines.append("")
        report_lines.append("=" * 80)
        
        return "\n".join(report_lines)
    
    def save_report(self, output_path: str):
        """Save the report to a file."""
        report = self.generate_report()
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"\nReport saved to: {output_path}")
    
    def save_json_data(self, output_path: str):
        """Save the email data as JSON."""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.email_data, f, indent=2, ensure_ascii=False)
        print(f"Email data saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Mail Screenshot RAG System - Analyze email screenshots and generate reports",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument(
        "--screenshot-dir",
        type=str,
        required=True,
        help="Directory containing email screenshots (e.g., ios_logs/mail_task_xxx/screenshots)",
    )
    
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Directory to save the report (default: same as screenshot-dir)",
    )
    
    parser.add_argument(
        "--max-screenshots",
        type=int,
        default=None,
        help="Maximum number of screenshots to analyze (default: all)",
    )
    
    parser.add_argument(
        "--api-base",
        type=str,
        default=os.getenv("API_BASE", "http://localhost:8003/v1"),
        help="API base URL for LLM (default: from API_BASE env var or http://localhost:8003/v1)",
    )
    
    parser.add_argument(
        "--api-key",
        type=str,
        default=os.getenv("API_KEY", "EMPTY"),
        help="API key for LLM (default: from API_KEY env var or EMPTY, not required for local agent)",
    )
    
    parser.add_argument(
        "--model-name",
        type=str,
        default=os.getenv("MODEL_NAME", "Qwen3-VL-4B-Instruct"),
        help="Model name for LLM (default: from MODEL_NAME env var or Qwen3-VL-4B-Instruct)",
    )
    
    parser.add_argument(
        "--agent-type",
        type=str,
        default=os.getenv("AGENT_TYPE", "OpenAIAgent"),
        choices=["OpenAIAgent", "QwenVLAgent"],
        help="Agent type to use (default: OpenAIAgent)",
    )
    
    args = parser.parse_args()
    
    # Validate screenshot directory
    if not os.path.exists(args.screenshot_dir):
        print(f"Error: Screenshot directory does not exist: {args.screenshot_dir}")
        sys.exit(1)
    
    # Determine output directory
    output_dir = args.output_dir or os.path.dirname(args.screenshot_dir)
    os.makedirs(output_dir, exist_ok=True)
    
    # Initialize agent
    print("Initializing LLM agent...")
    if args.agent_type == "QwenVLAgent":
        agent = QwenVLAgent(
            api_key=args.api_key,
            api_base=args.api_base,
            model_name=args.model_name,
        )
    else:
        agent = OpenAIAgent(
            api_key=args.api_key,
            api_base=args.api_base,
            model_name=args.model_name,
        )
    
    print(f"Using agent: {args.agent_type}")
    print(f"API Base: {args.api_base}")
    print(f"Model: {args.model_name}")
    print(f"API Key: {'Not required (local agent)' if args.api_key == 'EMPTY' or not args.api_key else 'Set'}")
    print()
    
    # Initialize RAG system
    rag_system = MailRAGSystem(agent, args.screenshot_dir)
    
    # Analyze screenshots
    print("Starting screenshot analysis...")
    rag_system.analyze_screenshots(max_screenshots=args.max_screenshots)
    
    # Remove duplicates
    print("\nRemoving duplicate emails...")
    rag_system.remove_duplicates()
    
    # Generate and save report
    report_path = os.path.join(output_dir, "mail_analysis_report.txt")
    rag_system.save_report(report_path)
    
    # Save JSON data
    json_path = os.path.join(output_dir, "mail_analysis_data.json")
    rag_system.save_json_data(json_path)
    
    # Print report to console
    print("\n" + "=" * 80)
    print("REPORT PREVIEW")
    print("=" * 80)
    print(rag_system.generate_report())
    
    print(f"\n✅ Analysis complete!")
    print(f"   Report: {report_path}")
    print(f"   Data: {json_path}")


if __name__ == "__main__":
    main()
