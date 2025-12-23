"""
Rule Engine Module
------------------
Pillar 2 of BPS Transformation: Business Rule Matching

This module provides:
- Configurable business rules (YAML/JSON)
- Rule evaluation against extracted entities
- Condition matching with operators
- Decision routing and scoring
"""

import json
import re
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import yaml


class RuleOperator(Enum):
    """Operators for rule conditions."""
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    GREATER_EQUAL = "greater_equal"
    LESS_EQUAL = "less_equal"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    MATCHES_REGEX = "matches_regex"
    IN_LIST = "in_list"
    NOT_IN_LIST = "not_in_list"
    IS_EMPTY = "is_empty"
    IS_NOT_EMPTY = "is_not_empty"
    BETWEEN = "between"


class RulePriority(Enum):
    """Rule priority levels."""
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4


@dataclass
class Condition:
    """A single condition in a rule."""
    field: str
    operator: RuleOperator
    value: Any = None
    value2: Any = None  # For BETWEEN operator
    
    def evaluate(self, entities: Dict[str, Any]) -> bool:
        """Evaluate this condition against entities."""
        field_value = self._get_nested_value(entities, self.field)
        
        # Handle None/missing values
        if field_value is None:
            if self.operator == RuleOperator.IS_EMPTY:
                return True
            elif self.operator == RuleOperator.IS_NOT_EMPTY:
                return False
            return False
        
        # Convert to appropriate types for comparison
        field_value = self._normalize_value(field_value)
        compare_value = self._normalize_value(self.value)
        
        op = self.operator
        
        if op == RuleOperator.EQUALS:
            return field_value == compare_value
        elif op == RuleOperator.NOT_EQUALS:
            return field_value != compare_value
        elif op == RuleOperator.GREATER_THAN:
            return float(field_value) > float(compare_value)
        elif op == RuleOperator.LESS_THAN:
            return float(field_value) < float(compare_value)
        elif op == RuleOperator.GREATER_EQUAL:
            return float(field_value) >= float(compare_value)
        elif op == RuleOperator.LESS_EQUAL:
            return float(field_value) <= float(compare_value)
        elif op == RuleOperator.CONTAINS:
            return str(compare_value).lower() in str(field_value).lower()
        elif op == RuleOperator.NOT_CONTAINS:
            return str(compare_value).lower() not in str(field_value).lower()
        elif op == RuleOperator.STARTS_WITH:
            return str(field_value).lower().startswith(str(compare_value).lower())
        elif op == RuleOperator.ENDS_WITH:
            return str(field_value).lower().endswith(str(compare_value).lower())
        elif op == RuleOperator.MATCHES_REGEX:
            return bool(re.match(str(compare_value), str(field_value)))
        elif op == RuleOperator.IN_LIST:
            return field_value in (compare_value if isinstance(compare_value, list) else [compare_value])
        elif op == RuleOperator.NOT_IN_LIST:
            return field_value not in (compare_value if isinstance(compare_value, list) else [compare_value])
        elif op == RuleOperator.IS_EMPTY:
            return not field_value or str(field_value).strip() == ""
        elif op == RuleOperator.IS_NOT_EMPTY:
            return bool(field_value) and str(field_value).strip() != ""
        elif op == RuleOperator.BETWEEN:
            val = float(field_value)
            return float(compare_value) <= val <= float(self.value2)
        
        return False
    
    def _get_nested_value(self, data: Dict, path: str) -> Any:
        """Get value from nested dict using dot notation."""
        keys = path.split(".")
        value = data
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None
        return value
    
    def _normalize_value(self, value: Any) -> Any:
        """Normalize value for comparison."""
        if value is None:
            return None
        
        # Try to parse as number
        if isinstance(value, str):
            # Remove currency symbols and commas
            cleaned = re.sub(r'[$€£,]', '', value.strip())
            try:
                if '.' in cleaned:
                    return float(cleaned)
                return int(cleaned)
            except ValueError:
                pass
        
        return value


@dataclass
class Rule:
    """A business rule with conditions and actions."""
    id: str
    name: str
    description: str
    conditions: List[Condition]
    logic: str = "AND"  # AND or OR
    priority: RulePriority = RulePriority.MEDIUM
    action: str = ""
    action_params: Dict[str, Any] = field(default_factory=dict)
    category: str = "general"
    enabled: bool = True
    
    def evaluate(self, entities: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Evaluate this rule against entities.
        
        Returns:
            Tuple of (matches: bool, matched_conditions: List[str])
        """
        if not self.enabled:
            return False, []
        
        results = []
        matched = []
        
        for condition in self.conditions:
            result = condition.evaluate(entities)
            results.append(result)
            if result:
                matched.append(f"{condition.field} {condition.operator.value} {condition.value}")
        
        if self.logic == "AND":
            return all(results), matched
        else:  # OR
            return any(results), matched


@dataclass
class RuleResult:
    """Result of rule evaluation."""
    rule_id: str
    rule_name: str
    matched: bool
    matched_conditions: List[str]
    action: str
    action_params: Dict[str, Any]
    priority: int
    category: str


class RuleEngine:
    """
    Business Rule Engine for BPS Transformation.
    
    Evaluates extracted document data against configurable business rules
    and determines the appropriate actions to take.
    """
    
    def __init__(self):
        self.rules: List[Rule] = []
        self.rule_sets: Dict[str, List[Rule]] = {}
    
    def load_rules_from_yaml(self, yaml_path: str) -> None:
        """Load rules from a YAML file."""
        with open(yaml_path, 'r') as f:
            config = yaml.safe_load(f)
        
        self._parse_rules_config(config)
    
    def load_rules_from_dict(self, config: Dict) -> None:
        """Load rules from a dictionary."""
        self._parse_rules_config(config)
    
    def _parse_rules_config(self, config: Dict) -> None:
        """Parse rules configuration."""
        for rule_config in config.get("rules", []):
            conditions = []
            for cond in rule_config.get("conditions", []):
                conditions.append(Condition(
                    field=cond["field"],
                    operator=RuleOperator(cond["operator"]),
                    value=cond.get("value"),
                    value2=cond.get("value2"),
                ))
            
            priority_str = rule_config.get("priority", "medium").upper()
            priority = RulePriority[priority_str] if priority_str in RulePriority.__members__ else RulePriority.MEDIUM
            
            rule = Rule(
                id=rule_config["id"],
                name=rule_config["name"],
                description=rule_config.get("description", ""),
                conditions=conditions,
                logic=rule_config.get("logic", "AND"),
                priority=priority,
                action=rule_config.get("action", ""),
                action_params=rule_config.get("action_params", {}),
                category=rule_config.get("category", "general"),
                enabled=rule_config.get("enabled", True),
            )
            
            self.rules.append(rule)
            
            # Add to rule set
            category = rule.category
            if category not in self.rule_sets:
                self.rule_sets[category] = []
            self.rule_sets[category].append(rule)
    
    def add_rule(self, rule: Rule) -> None:
        """Add a rule to the engine."""
        self.rules.append(rule)
        if rule.category not in self.rule_sets:
            self.rule_sets[rule.category] = []
        self.rule_sets[rule.category].append(rule)
    
    def evaluate(
        self, 
        entities: Dict[str, Any],
        categories: Optional[List[str]] = None,
        stop_on_first_match: bool = False
    ) -> List[RuleResult]:
        """
        Evaluate all rules against the extracted entities.
        
        Args:
            entities: Dictionary of extracted entities
            categories: Optional list of rule categories to evaluate
            stop_on_first_match: If True, stop after first matching rule
            
        Returns:
            List of RuleResult objects for matched rules
        """
        results = []
        
        # Filter rules by category if specified
        rules_to_check = self.rules
        if categories:
            rules_to_check = [r for r in self.rules if r.category in categories]
        
        # Sort by priority
        rules_to_check = sorted(rules_to_check, key=lambda r: r.priority.value)
        
        for rule in rules_to_check:
            matched, matched_conditions = rule.evaluate(entities)
            
            if matched:
                result = RuleResult(
                    rule_id=rule.id,
                    rule_name=rule.name,
                    matched=True,
                    matched_conditions=matched_conditions,
                    action=rule.action,
                    action_params=rule.action_params,
                    priority=rule.priority.value,
                    category=rule.category,
                )
                results.append(result)
                
                if stop_on_first_match:
                    break
        
        return results
    
    def get_decision(
        self,
        entities: Dict[str, Any],
        confidence_scores: Optional[Dict[str, float]] = None,
        min_confidence: float = 0.7
    ) -> Dict[str, Any]:
        """
        Get a decision based on rules and confidence scores.
        
        Args:
            entities: Extracted entities
            confidence_scores: Confidence scores for entities
            min_confidence: Minimum confidence threshold
            
        Returns:
            Decision dictionary with action, routing, and flags
        """
        # Check confidence first
        low_confidence_fields = []
        if confidence_scores:
            for field, score in confidence_scores.items():
                if score < min_confidence:
                    low_confidence_fields.append(field)
        
        # If too many low confidence fields, flag for manual review
        needs_review = len(low_confidence_fields) > 2
        
        # Evaluate rules
        rule_results = self.evaluate(entities)
        
        # Build decision
        decision = {
            "timestamp": datetime.now().isoformat(),
            "needs_manual_review": needs_review,
            "low_confidence_fields": low_confidence_fields,
            "matched_rules": len(rule_results),
            "rules": [],
            "primary_action": None,
            "routing": None,
            "flags": [],
        }
        
        # Process matched rules
        for result in rule_results:
            decision["rules"].append({
                "id": result.rule_id,
                "name": result.rule_name,
                "action": result.action,
                "params": result.action_params,
                "matched_conditions": result.matched_conditions,
            })
            
            # Set primary action from highest priority rule
            if decision["primary_action"] is None:
                decision["primary_action"] = result.action
                decision["routing"] = result.action_params.get("route_to")
            
            # Collect flags
            if "flag" in result.action_params:
                decision["flags"].append(result.action_params["flag"])
        
        return decision


# Pre-built rule sets for common scenarios
INSURANCE_CLAIM_RULES = {
    "rules": [
        {
            "id": "HIGH_VALUE_CLAIM",
            "name": "High Value Claim",
            "description": "Claims over $50,000 require senior adjuster review",
            "category": "routing",
            "priority": "high",
            "conditions": [
                {"field": "requested_amount", "operator": "greater_than", "value": 50000}
            ],
            "action": "route_to_senior",
            "action_params": {"route_to": "senior_adjuster", "flag": "high_value"}
        },
        {
            "id": "AUTO_APPROVE_SMALL",
            "name": "Auto-Approve Small Claims",
            "description": "Claims under $500 with complete info can be auto-approved",
            "category": "approval",
            "priority": "medium",
            "conditions": [
                {"field": "requested_amount", "operator": "less_equal", "value": 500},
                {"field": "signature_present", "operator": "equals", "value": "yes"},
                {"field": "policy_number", "operator": "is_not_empty"}
            ],
            "action": "auto_approve",
            "action_params": {"approval_level": "automatic"}
        },
        {
            "id": "FRAUD_INDICATOR_TIMING",
            "name": "Fraud Indicator - Late Reporting",
            "description": "Claims reported more than 30 days after incident",
            "category": "fraud",
            "priority": "high",
            "conditions": [
                {"field": "days_since_incident", "operator": "greater_than", "value": 30}
            ],
            "action": "flag_for_investigation",
            "action_params": {"flag": "late_reporting", "route_to": "fraud_team"}
        },
        {
            "id": "MEDICAL_CLAIM",
            "name": "Medical Claim Routing",
            "description": "Route medical claims to specialized team",
            "category": "routing",
            "priority": "medium",
            "conditions": [
                {"field": "claim_type", "operator": "equals", "value": "medical"}
            ],
            "action": "route_to_medical",
            "action_params": {"route_to": "medical_claims_team"}
        },
        {
            "id": "MISSING_DOCS",
            "name": "Missing Documentation",
            "description": "Flag claims missing required documents",
            "category": "validation",
            "priority": "high",
            "conditions": [
                {"field": "supporting_documents", "operator": "is_empty"}
            ],
            "logic": "OR",
            "action": "request_documents",
            "action_params": {"flag": "incomplete", "route_to": "customer_service"}
        },
    ]
}

INVOICE_PROCESSING_RULES = {
    "rules": [
        {
            "id": "AUTO_PAY_SMALL",
            "name": "Auto-Pay Small Invoices",
            "description": "Invoices under $1000 from approved vendors",
            "category": "payment",
            "priority": "low",
            "conditions": [
                {"field": "total_amount", "operator": "less_equal", "value": 1000}
            ],
            "action": "auto_pay",
            "action_params": {"payment_priority": "normal"}
        },
        {
            "id": "MANAGER_APPROVAL",
            "name": "Manager Approval Required",
            "description": "Invoices between $1000-$10000",
            "category": "approval",
            "priority": "medium",
            "conditions": [
                {"field": "total_amount", "operator": "between", "value": 1000, "value2": 10000}
            ],
            "action": "route_for_approval",
            "action_params": {"route_to": "department_manager"}
        },
        {
            "id": "EXECUTIVE_APPROVAL",
            "name": "Executive Approval Required",
            "description": "Invoices over $10000",
            "category": "approval",
            "priority": "high",
            "conditions": [
                {"field": "total_amount", "operator": "greater_than", "value": 10000}
            ],
            "action": "route_for_approval",
            "action_params": {"route_to": "executive", "flag": "high_value"}
        },
        {
            "id": "PAST_DUE",
            "name": "Past Due Invoice",
            "description": "Invoice past due date",
            "category": "urgency",
            "priority": "critical",
            "conditions": [
                {"field": "days_past_due", "operator": "greater_than", "value": 0}
            ],
            "action": "prioritize_payment",
            "action_params": {"flag": "past_due", "payment_priority": "urgent"}
        },
    ]
}

LOAN_APPLICATION_RULES = {
    "rules": [
        {
            "id": "HIGH_INCOME",
            "name": "High Income Fast Track",
            "description": "Applicants with income over $150K get fast-tracked",
            "category": "routing",
            "priority": "medium",
            "conditions": [
                {"field": "annual_income", "operator": "greater_than", "value": 150000}
            ],
            "action": "fast_track",
            "action_params": {"route_to": "premium_team", "flag": "high_value_customer"}
        },
        {
            "id": "LOW_AMOUNT_AUTO",
            "name": "Auto-Process Small Loans",
            "description": "Loans under $5000 for employed applicants",
            "category": "approval",
            "priority": "low",
            "conditions": [
                {"field": "requested_amount", "operator": "less_equal", "value": 5000},
                {"field": "employment_status", "operator": "equals", "value": "employed"}
            ],
            "action": "auto_approve",
            "action_params": {"approval_level": "automatic"}
        },
        {
            "id": "HIGH_RISK",
            "name": "High Risk Assessment",
            "description": "Large loan requests relative to income",
            "category": "risk",
            "priority": "high",
            "conditions": [
                {"field": "debt_to_income_ratio", "operator": "greater_than", "value": 0.4}
            ],
            "action": "additional_review",
            "action_params": {"flag": "high_risk", "route_to": "risk_team"}
        },
    ]
}

