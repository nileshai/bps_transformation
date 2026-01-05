"""
BPS Transformation Demo
=======================
End-to-End Business Process Services Transformation
Powered by NVIDIA NIM

Three Pillars:
1. Document Extraction (IDP with NVIDIA OCR)
2. Rule Matching (Configurable Business Rules)
3. Action Automation (Workflow Orchestration)

For GSI Partners: Wipro, TCS, Infosys, Accenture, etc.
Demo for Enterprise Customers
"""

import json
import os
import io
import time
from datetime import datetime
from typing import Dict, Any, List, Optional

import streamlit as st
from dotenv import load_dotenv
from PIL import Image

# Import our BPS modules
from modules.document_extractor import DocumentExtractor, ExtractionResult
from modules.rule_engine import RuleEngine, INSURANCE_CLAIM_RULES, INVOICE_PROCESSING_RULES, LOAN_APPLICATION_RULES
from modules.action_engine import ActionEngine, ActionStatus

load_dotenv()

# === CONFIGURATION ===

# NVIDIA API Key
def get_api_key():
    key = os.getenv("NGC_API_KEY", os.getenv("NVIDIA_API_KEY", ""))
    if key:
        return key
    try:
        if hasattr(st, 'secrets') and 'NVIDIA_API_KEY' in st.secrets:
            return st.secrets['NVIDIA_API_KEY']
    except:
        pass
    return ""

NVIDIA_API_KEY = get_api_key()

# === MODEL CONFIGURATIONS ===

# OCR Models
OCR_MODELS = {
    "NemoRetriever OCR v1 (Default)": {
        "model": "nvidia/nemoretriever-ocr-v1",
        "description": "NVIDIA's optimized OCR model",
    },
    "Llama 3.2 90B Vision": {
        "model": "meta/llama-3.2-90b-vision-instruct",
        "description": "Meta's vision-language model",
    },
}

# LLM Models for Entity Extraction & AI Rules
LLM_MODELS = {
    "Nemotron 3 Nano 30B (Default)": {
        "model": "nvidia/nemotron-3-nano-30b-a3b",
        "description": "30B model • Great balance of speed & quality",
    },
    "Nemotron Super 49B": {
        "model": "nvidia/llama-3.3-nemotron-super-49b-v1",
        "description": "49B model • High accuracy for complex docs",
    },
    "Llama 3.1 8B Instruct": {
        "model": "meta/llama-3.1-8b-instruct",
        "description": "8B model • Fast responses",
    },
    "Llama 3.1 70B Instruct": {
        "model": "meta/llama-3.1-70b-instruct",
        "description": "70B model • High quality",
    },
    "Mistral Large 2": {
        "model": "mistralai/mistral-large-2-instruct",
        "description": "Mistral's flagship model",
    },
}

# Color scheme - Professional enterprise theme
PRIMARY_COLOR = "#76B900"  # NVIDIA Green
DARK_BG = "#0a0a0a"
CARD_BG = "#1a1a2e"
ACCENT_BLUE = "#3B82F6"
ACCENT_PURPLE = "#8B5CF6"
ACCENT_ORANGE = "#F59E0B"
ACCENT_RED = "#EF4444"
ACCENT_GREEN = "#10B981"

# Pre-defined rule sets for demo with editable defaults
# Field names MUST match the entity keys from sample data
DEFAULT_RULES = {
    "Insurance Claims": [
        {"id": "HIGH_VALUE", "name": "🔴 High Value Claim", "field": "requested_amount", "operator": ">", "value": "50000", "action": "Route to Senior Adjuster", "enabled": True},
        {"id": "AUTO_APPROVE", "name": "✅ Auto-Approve Small", "field": "requested_amount", "operator": "<", "value": "500", "action": "Auto Approve", "enabled": True},
        {"id": "FRAUD_LATE", "name": "🚨 Late Reporting Flag", "field": "days_since_incident", "operator": ">", "value": "30", "action": "Flag for Fraud Review", "enabled": True},
        {"id": "MEDICAL", "name": "🏥 Medical Claim", "field": "claim_type", "operator": "==", "value": "medical", "action": "Route to Medical Team", "enabled": True},
        {"id": "MISSING_SIG", "name": "📝 Missing Signature", "field": "signature_present", "operator": "==", "value": "no", "action": "Request Documents", "enabled": True},
    ],
    "Invoice Processing": [
        {"id": "AUTO_PAY", "name": "✅ Auto-Pay Small", "field": "total_amount", "operator": "<", "value": "1000", "action": "Auto Pay", "enabled": True},
        {"id": "MANAGER_APPROVAL", "name": "👤 Manager Approval", "field": "total_amount", "operator": ">", "value": "5000", "action": "Route to Manager", "enabled": True},
        {"id": "EXEC_APPROVAL", "name": "👔 Executive Approval", "field": "total_amount", "operator": ">", "value": "50000", "action": "Route to CFO", "enabled": True},
        {"id": "PAST_DUE", "name": "⏰ Past Due Priority", "field": "days_past_due", "operator": ">", "value": "0", "action": "Urgent Payment", "enabled": True},
        {"id": "NEW_VENDOR", "name": "🆕 New Vendor Review", "field": "vendor_approved", "operator": "==", "value": "false", "action": "Vendor Verification", "enabled": True},
    ],
    "Loan Applications": [
        {"id": "HIGH_INCOME", "name": "💰 High Income Fast Track", "field": "annual_income", "operator": ">", "value": "150000", "action": "Fast Track Approval", "enabled": True},
        {"id": "LOW_AMOUNT", "name": "✅ Auto-Approve Small", "field": "requested_amount", "operator": "<", "value": "5000", "action": "Auto Approve", "enabled": True},
        {"id": "HIGH_DTI", "name": "⚠️ High Debt-to-Income", "field": "debt_to_income_ratio", "operator": ">", "value": "0.4", "action": "Additional Review", "enabled": True},
        {"id": "EMPLOYED", "name": "💼 Employment Check", "field": "employment_status", "operator": "==", "value": "employed", "action": "Standard Processing", "enabled": True},
        {"id": "LARGE_LOAN", "name": "🏦 Large Loan Committee", "field": "requested_amount", "operator": ">", "value": "100000", "action": "Committee Review", "enabled": True},
    ],
    "Account Opening": [
        {"id": "KYC_COMPLETE", "name": "✅ KYC Complete", "field": "kyc_verified", "operator": "==", "value": "yes", "action": "Proceed to Account Setup", "enabled": True},
        {"id": "FINANCIAL_INST", "name": "🏦 Financial Institution", "field": "is_financial_institution", "operator": "==", "value": "yes", "action": "Enhanced Due Diligence", "enabled": True},
        {"id": "ACTIVELY_TRADING", "name": "📈 Actively Trading", "field": "actively_trading", "operator": "==", "value": "yes", "action": "Standard Business Account", "enabled": True},
        {"id": "HIGH_RISK_COUNTRY", "name": "🚨 High Risk Country", "field": "country", "operator": "!=", "value": "Ireland", "action": "Additional Compliance Review", "enabled": True},
        {"id": "NEW_COMPANY", "name": "🆕 New Company", "field": "years_in_business", "operator": "<", "value": "2", "action": "Enhanced Verification", "enabled": True},
        {"id": "DIGITAL_BANKING", "name": "📱 Digital Banking", "field": "banking_type", "operator": "==", "value": "digital", "action": "Setup Online Access", "enabled": True},
    ],
}

# Account Opening rules for the engine
ACCOUNT_OPENING_RULES = {
    "rules": [
        {
            "id": "KYC_VERIFIED",
            "name": "KYC Verification Complete",
            "category": "compliance",
            "priority": "high",
            "conditions": [{"field": "kyc_verified", "operator": "equals", "value": "yes"}],
            "action": "proceed_to_setup",
            "action_params": {"route_to": "account_setup_team"}
        },
        {
            "id": "FINANCIAL_INSTITUTION",
            "name": "Financial Institution - Enhanced Due Diligence",
            "category": "compliance",
            "priority": "critical",
            "conditions": [{"field": "is_financial_institution", "operator": "equals", "value": "yes"}],
            "action": "enhanced_due_diligence",
            "action_params": {"route_to": "compliance_team", "flag": "financial_institution"}
        },
        {
            "id": "ACTIVELY_TRADING",
            "name": "Actively Trading Company",
            "category": "routing",
            "priority": "medium",
            "conditions": [{"field": "actively_trading", "operator": "equals", "value": "yes"}],
            "action": "standard_business_account",
            "action_params": {"account_type": "business_current"}
        },
        {
            "id": "DIGITAL_BANKING",
            "name": "Digital Banking Setup",
            "category": "setup",
            "priority": "low",
            "conditions": [{"field": "banking_type", "operator": "equals", "value": "digital"}],
            "action": "setup_digital_access",
            "action_params": {"enable_online": True, "enable_mobile": True}
        },
    ]
}

# Original rule sets for the engine
RULE_SETS = {
    "Insurance Claims": INSURANCE_CLAIM_RULES,
    "Invoice Processing": INVOICE_PROCESSING_RULES,
    "Loan Applications": LOAN_APPLICATION_RULES,
    "Account Opening": ACCOUNT_OPENING_RULES,
}


def inject_css():
    """Clean LIGHT theme - professional enterprise look, no visibility issues."""
    pass  # No custom CSS - use Streamlit's default light theme


def render_header():
    """Render the hero header using Streamlit native components."""
    col1, col2 = st.columns([3, 1])
    with col1:
        st.title("🚀 BPS Transformation")
    with col2:
        st.success("Powered by NVIDIA NIM")
    st.markdown("**End-to-End Business Process Automation: Document Extraction → Rule Matching → Action Automation**")
    st.divider()


def render_rules_editor(doc_type: str) -> List[Dict]:
    """Render the rules editor for the selected business process."""
    st.subheader("⚖️ Business Rules Configuration")
    st.markdown(f"**Active rules for {doc_type}** - Toggle to enable/disable, edit values as needed")
    
    # Initialize session state for rules if not exists
    if f"rules_{doc_type}" not in st.session_state:
        st.session_state[f"rules_{doc_type}"] = DEFAULT_RULES.get(doc_type, []).copy()
    
    rules = st.session_state[f"rules_{doc_type}"]
    updated_rules = []
    
    # Create editable rules table
    for idx, rule in enumerate(rules):
        with st.container(border=True):
            col1, col2, col3, col4, col5, col6 = st.columns([0.5, 2, 1.5, 1, 1.5, 2])
            
            with col1:
                enabled = st.checkbox("", value=rule.get("enabled", True), key=f"rule_enabled_{doc_type}_{idx}", label_visibility="collapsed")
            
            with col2:
                st.markdown(f"**{rule['name']}**")
            
            with col3:
                field = st.text_input("Field", value=rule['field'], key=f"rule_field_{doc_type}_{idx}", label_visibility="collapsed")
            
            with col4:
                operator = st.selectbox("Op", options=["<", ">", "==", "!=", "<=", ">="], 
                                       index=["<", ">", "==", "!=", "<=", ">="].index(rule.get('operator', '>')),
                                       key=f"rule_op_{doc_type}_{idx}", label_visibility="collapsed")
            
            with col5:
                value = st.text_input("Value", value=str(rule['value']), key=f"rule_val_{doc_type}_{idx}", label_visibility="collapsed")
            
            with col6:
                action = st.text_input("Action", value=rule['action'], key=f"rule_action_{doc_type}_{idx}", label_visibility="collapsed")
            
            updated_rules.append({
                "id": rule['id'],
                "name": rule['name'],
                "field": field,
                "operator": operator,
                "value": value,
                "action": action,
                "enabled": enabled
            })
    
    # Update session state
    st.session_state[f"rules_{doc_type}"] = updated_rules
    
    # Show legend
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("**Operators:** < > == != <= >=")
    with col2:
        st.markdown("**Fields:** From extracted entities")
    with col3:
        if st.button("🔄 Reset to Defaults", key=f"reset_rules_{doc_type}"):
            st.session_state[f"rules_{doc_type}"] = DEFAULT_RULES.get(doc_type, []).copy()
            st.session_state[f"custom_llm_rules_{doc_type}"] = []
            st.rerun()
    
    # Custom LLM-based rules section
    st.markdown("---")
    st.markdown("### 🤖 Custom AI Rules (Evaluated by Nemotron LLM)")
    st.markdown("Add natural language rules - the LLM will evaluate if they match the document")
    
    # Initialize custom LLM rules in session state
    if f"custom_llm_rules_{doc_type}" not in st.session_state:
        st.session_state[f"custom_llm_rules_{doc_type}"] = []
    
    # Display existing custom rules
    custom_llm_rules = st.session_state[f"custom_llm_rules_{doc_type}"]
    
    for idx, custom_rule in enumerate(custom_llm_rules):
        col1, col2, col3 = st.columns([0.5, 5, 1])
        with col1:
            enabled = st.checkbox("", value=custom_rule.get("enabled", True), 
                                 key=f"custom_enabled_{doc_type}_{idx}", label_visibility="collapsed")
            custom_llm_rules[idx]["enabled"] = enabled
        with col2:
            st.text_area("Rule", value=custom_rule.get("rule_text", ""), 
                        key=f"custom_text_{doc_type}_{idx}", height=60, disabled=True,
                        label_visibility="collapsed")
        with col3:
            if st.button("🗑️", key=f"delete_custom_{doc_type}_{idx}"):
                custom_llm_rules.pop(idx)
                st.rerun()
    
    # Add new custom rule
    with st.container(border=True):
        st.markdown("**➕ Add New AI Rule**")
        new_rule_text = st.text_area(
            "Describe your rule in plain English:",
            placeholder="Example: If the claim amount is more than 3 times the estimated damage, flag for fraud review",
            key=f"new_rule_input_{doc_type}",
            height=80
        )
        new_rule_action = st.text_input(
            "Action to take if rule matches:",
            placeholder="Example: Flag for Manager Review",
            key=f"new_rule_action_{doc_type}"
        )
        
        if st.button("➕ Add Rule", key=f"add_custom_rule_{doc_type}"):
            if new_rule_text and new_rule_action:
                custom_llm_rules.append({
                    "id": f"CUSTOM_{len(custom_llm_rules)+1}",
                    "rule_text": new_rule_text,
                    "action": new_rule_action,
                    "enabled": True
                })
                st.session_state[f"custom_llm_rules_{doc_type}"] = custom_llm_rules
                st.rerun()
    
    st.session_state[f"custom_llm_rules_{doc_type}"] = custom_llm_rules
    
    return [r for r in updated_rules if r.get("enabled", True)]


def evaluate_llm_rules(entities: Dict, custom_rules: List[Dict], api_key: str, model: str = "nvidia/nemotron-3-nano-30b-a3b") -> List[Dict]:
    """Use LLM to evaluate custom text-based rules against entities."""
    import re
    from openai import OpenAI
    
    if not custom_rules or not api_key:
        return []
    
    enabled_rules = [r for r in custom_rules if r.get("enabled", True)]
    if not enabled_rules:
        return []
    
    # Build the prompt
    entities_text = json.dumps(entities, indent=2, default=str)
    rules_text = "\n".join([f"{i+1}. {r['rule_text']} → Action: {r['action']}" 
                           for i, r in enumerate(enabled_rules)])
    
    prompt = f"""You are a business rules evaluation system. Given the extracted document data and a list of rules, determine which rules match.

EXTRACTED DOCUMENT DATA:
{entities_text}

RULES TO EVALUATE:
{rules_text}

For each rule, respond with:
- MATCH if the rule condition is satisfied by the data
- NO MATCH if the rule condition is not satisfied

Respond ONLY with this exact JSON format (no other text):
{{
  "evaluations": [
    {{"rule_index": 1, "matches": true, "reason": "brief explanation"}},
    {{"rule_index": 2, "matches": false, "reason": "brief explanation"}}
  ]
}}

Evaluate each rule carefully based on the actual data values."""

    try:
        # Use OpenAI client with NVIDIA API
        client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=api_key
        )
        
        # Check if using Nemotron model (supports reasoning)
        is_nemotron = "nemotron" in model.lower()
        
        # Build extra body for Nemotron models
        extra_body = {}
        if is_nemotron and "nano" in model.lower():
            extra_body = {
                "reasoning_budget": 1024,
                "chat_template_kwargs": {"enable_thinking": True}
            }
        
        # Call selected LLM model
        completion = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=1024,
            extra_body=extra_body if extra_body else None
        )
        
        # Get the response content
        if not completion.choices:
            st.warning("LLM returned no choices in response")
            return []
        
        content = completion.choices[0].message.content
        
        if not content:
            st.warning("LLM returned empty content")
            return []
        
        # Parse JSON from response
        json_match = re.search(r'\{[\s\S]*\}', content)
        if not json_match:
            st.warning(f"Could not parse LLM response as JSON. Response: {content[:200]}")
            return []
        
        result = json.loads(json_match.group())
        matched_rules = []
        
        for eval_item in result.get("evaluations", []):
            if eval_item.get("matches", False):
                rule_idx = eval_item.get("rule_index", 1) - 1
                if 0 <= rule_idx < len(enabled_rules):
                    rule_text = enabled_rules[rule_idx]['rule_text']
                    display_text = rule_text[:50] + "..." if len(rule_text) > 50 else rule_text
                    matched_rules.append({
                        "name": f"🤖 AI Rule: {display_text}",
                        "action": enabled_rules[rule_idx]['action'],
                        "matched_conditions": [eval_item.get("reason", "LLM matched")],
                        "is_llm_rule": True
                    })
        
        return matched_rules
        
    except json.JSONDecodeError as e:
        st.warning(f"Failed to parse LLM JSON response: {str(e)}")
    except Exception as e:
        st.warning(f"LLM rule evaluation error: {str(e)}")
    
    return []


def render_three_pillars(active_pillars: List[int] = []):
    """Render the three pillars of BPS transformation using Streamlit native components."""
    pillars = [
        ("1", "Document Extraction", "NVIDIA OCR + LLM", "📄"),
        ("2", "Rule Matching", "Business Rules Engine", "⚖️"),
        ("3", "Action Automation", "Workflow Orchestration", "⚡"),
    ]
    
    cols = st.columns(3)
    for idx, (num, title, tech, icon) in enumerate(pillars):
        with cols[idx]:
            is_active = (idx + 1) in active_pillars
            
            # Use a container with custom styling
            container = st.container(border=True)
            with container:
                if is_active:
                    st.success(f"✓ Pillar {num} Active")
                st.markdown(f"### {icon}")
                st.markdown(f"**{title}**")
                st.success(tech)


def render_pipeline_status(stages: List[Dict]):
    """Render the pipeline flow status using Streamlit native components."""
    cols = st.columns(len(stages))
    
    for idx, stage in enumerate(stages):
        status = stage.get("status", "")
        with cols[idx]:
            if status == "completed":
                st.success(f"{stage['icon']} {stage['name']}")
            elif status == "active":
                st.warning(f"{stage['icon']} {stage['name']} ⏳")
            else:
                st.info(f"{stage['icon']} {stage['name']}")


def render_metrics(metrics: Dict[str, Any]):
    """Render metrics grid using Streamlit native metrics."""
    cols = st.columns(len(metrics))
    for idx, (label, value) in enumerate(metrics.items()):
        with cols[idx]:
            st.metric(label=label, value=value)


def render_extraction_result(result: ExtractionResult):
    """Render document extraction results using Streamlit native components."""
    st.subheader("📄 Document Extraction Results")
    
    # Show model info if available
    if result.metadata:
        if result.metadata.get("ocr_model"):
            st.caption(f"🔍 OCR: {result.metadata.get('ocr_model')} | 🤖 LLM: {result.metadata.get('llm_model', 'N/A')}")
    
    # Show entities with confidence
    if not result.entities:
        st.warning("⚠️ No entities extracted. Try enabling 'Use Sample Data' for demo, or check if OCR/LLM is working.")
        return
    
    if result.entities:
        # Create a dataframe-like display
        for key, value in list(result.entities.items())[:15]:  # Show top 15
            conf = result.confidence_scores.get(key, 0.85)
            
            # Handle list values
            display_value = str(value) if not isinstance(value, list) else ", ".join(str(v) for v in value[:3])
            if len(display_value) > 50:
                display_value = display_value[:47] + "..."
            
            # Confidence indicator
            if conf >= 0.9:
                conf_indicator = "🟢"
            elif conf >= 0.7:
                conf_indicator = "🟡"
            else:
                conf_indicator = "🔴"
            
            col1, col2, col3 = st.columns([2, 3, 1])
            with col1:
                st.markdown(f"**{key}**")
            with col2:
                st.code(display_value, language=None)
            with col3:
                st.markdown(f"{conf_indicator} **{conf:.0%}**")


def render_rule_results(rule_results: List[Dict]):
    """Render rule matching results using Streamlit native components."""
    st.subheader("⚖️ Rule Matching Results")
    
    if not rule_results:
        st.info("No rules matched for this document.")
        return
    
    for rule in rule_results:
        is_warning = rule.get("action") in ["flag_for_investigation", "reject"]
        matched_conds = rule.get('matched_conditions', [])[:2]
        matched_str = ', '.join(matched_conds) if matched_conds else 'All conditions met'
        
        with st.container(border=True):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"**{rule.get('name', 'Rule')}**")
                st.markdown(f"Matched: {matched_str}")
            with col2:
                if is_warning:
                    st.warning(rule.get('action', 'N/A'))
                else:
                    st.success(rule.get('action', 'N/A'))


def render_action_results(action_executions: List):
    """Render action execution results using Streamlit native components."""
    st.subheader("⚡ Automated Actions Executed")
    
    action_icons = {
        "route": "📁",
        "approve": "✅",
        "reject": "❌",
        "flag": "🚩",
        "notify": "📧",
        "create_ticket": "🎫",
        "send_email": "📨",
        "escalate": "⬆️",
        "request_info": "📋",
        "schedule_review": "📅",
    }
    
    for execution in action_executions:
        icon = action_icons.get(execution.action_type.value, "⚡")
        is_success = execution.status == ActionStatus.COMPLETED
        result_msg = execution.result.get("message", "") if execution.result else execution.error or ""
        
        with st.container(border=True):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"**{icon} {execution.action_name}**")
                st.markdown(f"{result_msg}")
            with col2:
                if is_success:
                    st.success(execution.status.value)
                else:
                    st.error(execution.status.value)


def create_sample_entities_for_demo(doc_type: str) -> Dict[str, Any]:
    """Create sample entities for demo - designed to trigger multiple rules."""
    
    if doc_type == "Insurance Claims":
        # This sample triggers: HIGH_VALUE (>50k), FRAUD_LATE (>30 days), MEDICAL claim type
        return {
            "claim_number": "CLM-2024-889234",
            "policy_number": "POL-AUTO-2023-445566",
            "claimant_name": "John M. Smith",
            "claimant_email": "john.smith@email.com",
            "claimant_phone": "(555) 123-4567",
            "incident_date": "2024-01-15",
            "claim_date": "2024-03-01",
            "incident_type": "Medical Emergency",
            "incident_location": "Downtown Medical Center",
            "claim_type": "medical",  # Triggers MEDICAL rule
            "damage_description": "Emergency surgery and hospitalization",
            "estimated_amount": 55000,
            "requested_amount": 72500,  # Triggers HIGH_VALUE rule (>50000)
            "witnesses": [],
            "signature_present": "no",  # Triggers MISSING_SIG rule
            "supporting_documents": ["Medical Records", "Hospital Bills"],
            "days_since_incident": 45,  # Triggers FRAUD_LATE rule (>30)
        }
    elif doc_type == "Invoice Processing":
        # This sample triggers: MANAGER_APPROVAL (>5k), PAST_DUE (>0), NEW_VENDOR
        return {
            "invoice_number": "INV-2024-00567",
            "invoice_date": "2024-01-20",
            "due_date": "2024-02-20",
            "vendor_name": "NewTech Solutions LLC",
            "vendor_tax_id": "98-7654321",
            "vendor_approved": "false",  # Triggers NEW_VENDOR rule
            "purchase_order_number": "PO-2024-1234",
            "expense_category": "IT services",
            "line_items": [
                {"description": "Enterprise Software License", "amount": 4500},
                {"description": "Implementation Services", "amount": 3800},
            ],
            "subtotal": 8300,
            "tax_amount": 664,
            "total_amount": 8964,  # Triggers MANAGER_APPROVAL rule (>5000)
            "days_past_due": 12,  # Triggers PAST_DUE rule (>0)
            "early_pay_discount": 0,
            "days_to_discount_deadline": 0,
        }
    elif doc_type == "Account Opening":
        # This sample triggers: KYC_COMPLETE, ACTIVELY_TRADING, NEW_COMPANY, DIGITAL_BANKING
        return {
            "application_id": "ACC-2024-00892",
            "application_date": "2024-01-22",
            "name": "John Murphy",  # Primary contact name
            "company_name": "Emerald Tech Limited",
            "company_registration_no": "CRO/2025/IE/004512",
            "country": "Ireland",
            "incorporation_date": "12-Mar-2020",
            "years_in_business": 4,  # Calculated from incorporation date
            "registered_address": "1 Grand Canal Square, Dublin 2, D02 A342",
            "contact_phone": "+353 1234 5678",
            "contact_email": "info@emerald-tech.ie",
            "source_of_wealth": "Business Income",
            "actively_trading": "yes",  # Triggers ACTIVELY_TRADING rule
            "is_financial_institution": "no",
            "banking_type": "digital",  # Triggers DIGITAL_BANKING rule
            "kyc_verified": "yes",  # Triggers KYC_COMPLETE rule
            "fatca_compliant": "yes",
            "crs_compliant": "yes",
            "authorized_signatories": ["John Murphy - Director", "Sarah O'Brien - CFO"],
            "expected_monthly_turnover": 250000,
            "signature_present": "yes",
        }
    else:  # Loan Applications
        # This sample triggers: HIGH_INCOME (>150k), LARGE_LOAN (>100k), EMPLOYED, HIGH_DTI
        return {
            "application_id": "LOAN-2024-78901",
            "application_date": "2024-01-22",
            "applicant_name": "Sarah Johnson",
            "date_of_birth": "1985-06-15",
            "ssn_last4": "4567",
            "address": "123 Main St, Anytown, ST 12345",
            "phone": "(555) 987-6543",
            "email": "sarah.j@email.com",
            "employment_status": "employed",  # Triggers EMPLOYED rule
            "employer_name": "Tech Giants Inc",
            "annual_income": 175000,  # Triggers HIGH_INCOME rule (>150000)
            "requested_amount": 125000,  # Triggers LARGE_LOAN rule (>100000)
            "loan_purpose": "Investment Property Purchase",
            "signature_present": "yes",
            "debt_to_income_ratio": 0.45,  # Triggers HIGH_DTI rule (>0.4)
        }


def main():
    st.set_page_config(
        page_title="BPS Transformation Demo | NVIDIA NIM",
        page_icon="🚀",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    inject_css()
    
    # === SIDEBAR ===
    with st.sidebar:
        st.markdown("### 📋 Demo Configuration")
        
        # Document type / Rule set selection
        doc_type = st.selectbox(
            "Business Process",
            options=list(RULE_SETS.keys()),
            index=0,
            help="Select the business process to demo"
        )
        
        st.markdown("### 🔑 NVIDIA API Key")
        api_key = st.text_input(
            "API Key",
            value=NVIDIA_API_KEY,
            type="password",
            help="From build.nvidia.com"
        )
        
        if api_key and len(api_key) > 20:
            st.success("✅ API Key Configured")
        else:
            st.warning("⚠️ Enter API key for document processing")
        
        st.markdown("---")
        
        # Model Selection
        st.markdown("### 🤖 Model Selection")
        
        ocr_model_name = st.selectbox(
            "OCR Model",
            options=list(OCR_MODELS.keys()),
            index=0,
            help="Model for document text extraction"
        )
        ocr_model = OCR_MODELS[ocr_model_name]["model"]
        st.caption(f"_{OCR_MODELS[ocr_model_name]['description']}_")
        
        llm_model_name = st.selectbox(
            "LLM Model",
            options=list(LLM_MODELS.keys()),
            index=0,
            help="Model for entity extraction & AI rules"
        )
        llm_model = LLM_MODELS[llm_model_name]["model"]
        st.caption(f"_{LLM_MODELS[llm_model_name]['description']}_")
        
        st.markdown("---")
        
        st.markdown("### 📊 Scenario Metrics")
        st.markdown(f"""
        **{doc_type}**
        - 📄 Documents/day: 2,500+
        - ⏱️ Avg processing: 4.7s
        - ✅ Accuracy: 98.5%
        - 💰 Cost savings: 82%
        """)
        
        st.markdown("---")
    
    # === MAIN CONTENT ===
    render_header()
    
    # Initialize session state for multi-step workflow
    if "extracted_entities" not in st.session_state:
        st.session_state.extracted_entities = None
    if "extraction_result" not in st.session_state:
        st.session_state.extraction_result = None
    if "rule_decision" not in st.session_state:
        st.session_state.rule_decision = None
    if "action_executions" not in st.session_state:
        st.session_state.action_executions = None
    
    # ========================================
    # STEP 1: DOCUMENT EXTRACTION
    # ========================================
    st.markdown("## 📄 Step 1: Document Extraction")
    st.markdown("Extract text and entities from your document using NVIDIA OCR + LLM")
    
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        uploaded = st.file_uploader(
            "Upload document (PDF, PNG, JPG)",
            type=["pdf", "png", "jpg", "jpeg"],
            help="Upload a document to process, or leave empty to use sample data"
        )
        if not uploaded:
            st.caption("💡 No file uploaded - will use sample data for demo")
    
    with col2:
        st.markdown("**OCR Model:**")
        st.caption(f"🔍 {ocr_model_name}")
    
    with col3:
        extract_btn = st.button(
            "🔍 Extract Document",
            type="primary",
            use_container_width=True
        )
    
    # Run extraction when button clicked
    if extract_btn:
        with st.spinner(f"🔍 Extracting with {ocr_model_name}..."):
            # If file is uploaded, process it (regardless of demo mode)
            if uploaded:
                # Real extraction from uploaded file
                if not api_key or len(api_key) < 20:
                    st.error("❌ Please enter a valid NVIDIA API key to process real documents")
                    st.stop()
                
                st.info(f"📄 Processing uploaded file: {uploaded.name} with {ocr_model_name}")
                
                # Read file bytes
                file_bytes = uploaded.read()
                if not file_bytes:
                    st.error("❌ Failed to read uploaded file")
                    st.stop()
                st.caption(f"File size: {len(file_bytes):,} bytes")
                
                extractor = DocumentExtractor(api_key, ocr_model=ocr_model, llm_model=llm_model)
                
                try:
                    extraction_result = extractor.extract(
                        file_bytes,
                        uploaded.name,
                        document_type=doc_type.lower().replace(" ", "_")
                    )
                    extraction_result.metadata["ocr_model"] = ocr_model_name
                    extraction_result.metadata["llm_model"] = llm_model_name
                    extraction_result.metadata["source"] = "uploaded_file"
                    
                    # Show OCR details
                    if extraction_result.metadata.get("page_details"):
                        for pd in extraction_result.metadata["page_details"]:
                            if not pd.get("success"):
                                st.warning(f"⚠️ Page {pd.get('page')}: {pd.get('error', 'Unknown error')}")
                    
                    if not extraction_result.entities:
                        st.warning("⚠️ OCR completed but no entities were extracted. The document may be difficult to read.")
                        if extraction_result.raw_text:
                            with st.expander("📝 Raw OCR Text"):
                                st.text(extraction_result.raw_text[:2000])
                        
                except Exception as e:
                    import traceback
                    st.error(f"❌ Extraction failed: {str(e)}")
                    with st.expander("Error Details"):
                        st.code(traceback.format_exc())
                    st.stop()
            else:
                # Use sample data for demo (no file uploaded)
                time.sleep(1.0)
                entities = create_sample_entities_for_demo(doc_type)
                confidence_scores = {k: 0.85 + (hash(k) % 15) / 100 for k in entities.keys()}
                
                extraction_result = ExtractionResult(
                    document_id="DEMO-001",
                    filename="sample_document.pdf",
                    timestamp=datetime.now().isoformat(),
                    pages_processed=3,
                    raw_text="[Sample document text for demonstration]",
                    entities=entities,
                    confidence_scores=confidence_scores,
                    metadata={
                        "demo_mode": True,
                        "ocr_model": ocr_model_name,
                        "llm_model": llm_model_name,
                        "source": "sample_data"
                    }
                )
            
            # Store in session state
            st.session_state.extracted_entities = extraction_result.entities
            st.session_state.extraction_result = extraction_result
            st.session_state.confidence_scores = extraction_result.confidence_scores
            st.session_state.rule_decision = None  # Reset rules when new extraction
            st.session_state.action_executions = None
            st.success(f"✅ Extracted {len(extraction_result.entities)} entities!")
    
    # Show extraction results if available
    if st.session_state.extraction_result:
        with st.container(border=True):
            result = st.session_state.extraction_result
            
            col1, col2, col3 = st.columns([1, 1, 1])
            with col1:
                st.metric("Entities Extracted", len(result.entities))
            with col2:
                st.metric("Pages Processed", result.pages_processed)
            with col3:
                st.metric("Avg Confidence", f"{result.average_confidence:.0%}")
            
            st.markdown("#### 📋 Extracted Entities")
            
            if result.entities:
                # Display entities in a clean table format
                for key, value in list(result.entities.items()):
                    conf = result.confidence_scores.get(key, 0.85)
                    display_value = str(value) if not isinstance(value, list) else ", ".join(str(v) for v in value[:3])
                    if len(display_value) > 60:
                        display_value = display_value[:57] + "..."
                    
                    conf_color = "🟢" if conf >= 0.9 else ("🟡" if conf >= 0.7 else "🔴")
                    
                    col1, col2, col3 = st.columns([2, 4, 1])
                    with col1:
                        st.markdown(f"**{key}**")
                    with col2:
                        st.code(display_value, language=None)
                    with col3:
                        st.markdown(f"{conf_color} {conf:.0%}")
            else:
                st.warning("⚠️ No entities extracted. Try enabling 'Use Sample Data' or check the document.")
    
    st.markdown("---")
    
    # ========================================
    # STEP 2: RULE MATCHING
    # ========================================
    st.markdown("## ⚖️ Step 2: Rule Matching")
    st.markdown("Configure and apply business rules to the extracted data")
    
    # Rules editor
    with st.expander("📝 **Configure Rules** - Click to edit", expanded=False):
        active_rules = render_rules_editor(doc_type)
        st.success(f"✅ {len(active_rules)} rules active")
    
    # Apply rules button
    col1, col2 = st.columns([3, 1])
    with col1:
        st.caption(f"🤖 AI Rules will be evaluated using: **{llm_model_name}**")
    with col2:
        apply_rules_btn = st.button(
            "⚖️ Apply Rules",
            type="primary",
            use_container_width=True,
            disabled=st.session_state.extracted_entities is None
        )
    
    if apply_rules_btn and st.session_state.extracted_entities:
        entities = st.session_state.extracted_entities
        confidence_scores = st.session_state.confidence_scores
        
        with st.spinner("⚖️ Evaluating rules..."):
            # Initialize rule engine
            rule_engine = RuleEngine()
            rule_engine.load_rules_from_dict(RULE_SETS[doc_type])
            
            # Get decision from engine
            decision = rule_engine.get_decision(entities, confidence_scores, min_confidence=0.7)
            
            # Evaluate custom rules from editor
            custom_rules = st.session_state.get(f"rules_{doc_type}", DEFAULT_RULES.get(doc_type, []))
            custom_matched = []
            
            for rule in custom_rules:
                if not rule.get("enabled", True):
                    continue
                
                field = rule.get("field", "")
                operator = rule.get("operator", "==")
                target_value = rule.get("value", "")
                field_value = entities.get(field)
                
                if field_value is None:
                    continue
                
                try:
                    field_num = float(str(field_value).replace("$", "").replace(",", ""))
                    target_num = float(target_value)
                    
                    matched = False
                    if operator == ">" and field_num > target_num:
                        matched = True
                    elif operator == "<" and field_num < target_num:
                        matched = True
                    elif operator == ">=" and field_num >= target_num:
                        matched = True
                    elif operator == "<=" and field_num <= target_num:
                        matched = True
                    elif operator == "==" and field_num == target_num:
                        matched = True
                    elif operator == "!=" and field_num != target_num:
                        matched = True
                    
                    if matched:
                        custom_matched.append({
                            "name": rule.get("name", "Custom Rule"),
                            "action": rule.get("action", "Process"),
                            "matched_conditions": [f"{field} {operator} {target_value}"]
                        })
                except (ValueError, TypeError):
                    if operator == "==" and str(field_value).lower() == str(target_value).lower():
                        custom_matched.append({
                            "name": rule.get("name", "Custom Rule"),
                            "action": rule.get("action", "Process"),
                            "matched_conditions": [f"{field} {operator} {target_value}"]
                        })
                    elif operator == "!=" and str(field_value).lower() != str(target_value).lower():
                        custom_matched.append({
                            "name": rule.get("name", "Custom Rule"),
                            "action": rule.get("action", "Process"),
                            "matched_conditions": [f"{field} {operator} {target_value}"]
                        })
            
            if custom_matched:
                if "rules" not in decision:
                    decision["rules"] = []
                decision["rules"].extend(custom_matched)
                decision["matched_rules"] = len(decision.get("rules", []))
            
            # Evaluate LLM-based custom rules
            custom_llm_rules = st.session_state.get(f"custom_llm_rules_{doc_type}", [])
            if custom_llm_rules and api_key:
                llm_matched = evaluate_llm_rules(entities, custom_llm_rules, api_key, llm_model)
                if llm_matched:
                    if "rules" not in decision:
                        decision["rules"] = []
                    decision["rules"].extend(llm_matched)
                    decision["matched_rules"] = len(decision.get("rules", []))
            
            st.session_state.rule_decision = decision
            st.session_state.action_executions = None  # Reset actions
            st.success(f"✅ {decision.get('matched_rules', 0)} rules matched!")
    
    # Show rule results if available
    if st.session_state.rule_decision:
        decision = st.session_state.rule_decision
        
        with st.container(border=True):
            st.markdown("#### 📊 Rule Matching Results")
            
            matched_rules = decision.get("rules", [])
            if matched_rules:
                for rule in matched_rules:
                    is_warning = rule.get("action") in ["flag_for_investigation", "reject"]
                    matched_conds = rule.get('matched_conditions', [])[:2]
                    matched_str = ', '.join(matched_conds) if matched_conds else 'All conditions met'
                    
                    with st.container(border=True):
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.markdown(f"**{rule.get('name', 'Rule')}**")
                            st.caption(f"Matched: {matched_str}")
                        with col2:
                            if is_warning:
                                st.error(rule.get('action', 'N/A'))
                            else:
                                st.success(rule.get('action', 'N/A'))
            else:
                st.info("No rules matched for this document.")
            
            if decision.get("needs_manual_review"):
                st.warning(f"⚠️ Manual review required: {', '.join(decision.get('low_confidence_fields', []))}")
    
    st.markdown("---")
    
    # ========================================
    # STEP 3: ACTION EXECUTION
    # ========================================
    st.markdown("## ⚡ Step 3: Action Execution")
    st.markdown("Execute automated actions based on matched rules")
    
    col1, col2 = st.columns([3, 1])
    with col2:
        execute_actions_btn = st.button(
            "⚡ Execute Actions",
            type="primary",
            use_container_width=True,
            disabled=st.session_state.rule_decision is None
        )
    
    if execute_actions_btn and st.session_state.rule_decision:
        decision = st.session_state.rule_decision
        extraction_result = st.session_state.extraction_result
        
        with st.spinner("⚡ Executing actions..."):
            action_engine = ActionEngine(demo_mode=True)
            action_executions = action_engine.execute_decision(
                decision,
                document_context={"document_id": extraction_result.document_id if extraction_result else "UNKNOWN"}
            )
            st.session_state.action_executions = action_executions
            st.success(f"✅ {len(action_executions)} actions executed!")
    
    # Show action results if available
    if st.session_state.action_executions:
        action_executions = st.session_state.action_executions
        
        with st.container(border=True):
            st.markdown("#### 🎯 Executed Actions")
            
            action_icons = {
                "route": "📁", "approve": "✅", "reject": "❌", "flag": "🚩",
                "notify": "📧", "create_ticket": "🎫", "send_email": "📨",
                "escalate": "⬆️", "request_info": "📋", "schedule_review": "📅",
            }
            
            for execution in action_executions:
                icon = action_icons.get(execution.action_type.value, "⚡")
                is_success = execution.status == ActionStatus.COMPLETED
                result_msg = execution.result.get("message", "") if execution.result else execution.error or ""
                
                with st.container(border=True):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.markdown(f"**{icon} {execution.action_name}**")
                        st.caption(result_msg)
                    with col2:
                        if is_success:
                            st.success(execution.status.value)
                        else:
                            st.error(execution.status.value)
        
        # Final Decision Summary
        st.markdown("---")
        st.markdown("### 🎯 Final Decision Summary")
        
        decision = st.session_state.rule_decision
        primary_action = decision.get("primary_action") or "route"
        routing = decision.get("routing") or "general_queue"
        flags = decision.get("flags", [])
        
        is_approved = primary_action in ["auto_approve", "auto_pay"]
        icon = "✅" if is_approved else "📁"
        action_display = primary_action.replace('_', ' ').title() if primary_action else "Route"
        
        with st.container(border=True):
            col1, col2 = st.columns([1, 4])
            with col1:
                st.markdown(f"# {icon}")
            with col2:
                st.markdown(f"### {action_display}")
                routing_text = f"**Routed to:** {routing}"
                if flags:
                    routing_text += f" | **Flags:** {', '.join(flags)}"
                st.markdown(routing_text)
        
        if is_approved:
            st.success("✅ Document processed successfully - Auto-approved!")
        else:
            st.info(f"📁 Document routed to {routing} for processing")
        
        # Export buttons
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        
        extraction_result = st.session_state.extraction_result
        
        with col1:
            export_data = {
                "document": extraction_result.to_dict() if extraction_result else {},
                "decision": decision,
                "actions": [{"action": e.action_name, "status": e.status.value, "result": e.result} 
                           for e in action_executions],
            }
            st.download_button(
                "📥 Export Full Report",
                json.dumps(export_data, indent=2, default=str),
                file_name=f"bps_result_{extraction_result.document_id if extraction_result else 'unknown'}.json",
                mime="application/json"
            )
        
        with col2:
            if extraction_result:
                st.download_button(
                    "📄 Export Entities Only",
                    json.dumps(extraction_result.entities, indent=2),
                    file_name=f"entities_{extraction_result.document_id}.json",
                    mime="application/json"
                )
    
    # Footer
    st.divider()
    col1, col2, col3 = st.columns(3)
    with col2:
        st.markdown("**Powered by NVIDIA**")


if __name__ == "__main__":
    main()

