"""
Action Engine Module
--------------------
Pillar 3 of BPS Transformation: Automated Actions

This module provides:
- Action execution based on rule decisions
- Integration with external systems (email, ticketing, databases)
- Workflow automation and orchestration
- Audit trail and logging
"""

import json
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import uuid


class ActionType(Enum):
    """Types of actions that can be executed."""
    ROUTE = "route"                    # Route to a team/person
    APPROVE = "approve"                # Auto-approve
    REJECT = "reject"                  # Auto-reject
    FLAG = "flag"                      # Flag for attention
    NOTIFY = "notify"                  # Send notification
    CREATE_TICKET = "create_ticket"    # Create support ticket
    UPDATE_RECORD = "update_record"    # Update database record
    SEND_EMAIL = "send_email"          # Send email
    TRIGGER_WORKFLOW = "trigger_workflow"  # Trigger external workflow
    ESCALATE = "escalate"              # Escalate to supervisor
    REQUEST_INFO = "request_info"      # Request additional information
    SCHEDULE_REVIEW = "schedule_review"  # Schedule for manual review
    API_CALL = "api_call"              # Call external API


class ActionStatus(Enum):
    """Status of action execution."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ActionDefinition:
    """Definition of an action to be executed."""
    action_type: ActionType
    name: str
    description: str
    handler: Optional[Callable] = None
    params_schema: Dict[str, Any] = field(default_factory=dict)
    requires_confirmation: bool = False
    timeout_seconds: int = 30


@dataclass
class ActionExecution:
    """Record of an action execution."""
    execution_id: str
    action_type: ActionType
    action_name: str
    status: ActionStatus
    params: Dict[str, Any]
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: str = ""
    completed_at: str = ""
    duration_ms: int = 0


@dataclass
class WorkflowStep:
    """A step in a workflow."""
    step_id: str
    name: str
    action_type: ActionType
    params: Dict[str, Any]
    next_on_success: Optional[str] = None
    next_on_failure: Optional[str] = None
    condition: Optional[Dict] = None


class ActionEngine:
    """
    Action Execution Engine for BPS Transformation.
    
    Executes automated actions based on rule decisions, integrates with
    external systems, and maintains audit trails.
    """
    
    def __init__(self, demo_mode: bool = True):
        """
        Initialize the Action Engine.
        
        Args:
            demo_mode: If True, simulate actions instead of executing them
        """
        self.demo_mode = demo_mode
        self.action_registry: Dict[str, ActionDefinition] = {}
        self.execution_history: List[ActionExecution] = []
        self.workflows: Dict[str, List[WorkflowStep]] = {}
        self.integration_handlers: Dict[str, Callable] = {}
        
        # Register default actions
        self._register_default_actions()
    
    def _register_default_actions(self) -> None:
        """Register default action handlers."""
        
        self.register_action(ActionDefinition(
            action_type=ActionType.ROUTE,
            name="Route to Team",
            description="Route document to specified team for processing",
            params_schema={"route_to": "string", "priority": "string"}
        ))
        
        self.register_action(ActionDefinition(
            action_type=ActionType.APPROVE,
            name="Auto-Approve",
            description="Automatically approve the request",
            params_schema={"approval_level": "string", "notes": "string"}
        ))
        
        self.register_action(ActionDefinition(
            action_type=ActionType.REJECT,
            name="Auto-Reject",
            description="Automatically reject the request",
            params_schema={"reason": "string"}
        ))
        
        self.register_action(ActionDefinition(
            action_type=ActionType.FLAG,
            name="Flag for Attention",
            description="Flag document for special attention",
            params_schema={"flag_type": "string", "reason": "string"}
        ))
        
        self.register_action(ActionDefinition(
            action_type=ActionType.NOTIFY,
            name="Send Notification",
            description="Send notification to specified recipients",
            params_schema={"recipients": "list", "message": "string", "channel": "string"}
        ))
        
        self.register_action(ActionDefinition(
            action_type=ActionType.CREATE_TICKET,
            name="Create Ticket",
            description="Create a support/tracking ticket",
            params_schema={"title": "string", "description": "string", "assignee": "string", "priority": "string"}
        ))
        
        self.register_action(ActionDefinition(
            action_type=ActionType.SEND_EMAIL,
            name="Send Email",
            description="Send email to specified recipients",
            params_schema={"to": "list", "subject": "string", "body": "string", "template": "string"}
        ))
        
        self.register_action(ActionDefinition(
            action_type=ActionType.ESCALATE,
            name="Escalate",
            description="Escalate to supervisor or higher authority",
            params_schema={"escalate_to": "string", "reason": "string", "urgency": "string"}
        ))
        
        self.register_action(ActionDefinition(
            action_type=ActionType.REQUEST_INFO,
            name="Request Information",
            description="Request additional information from customer",
            params_schema={"requested_fields": "list", "message": "string", "deadline_days": "int"}
        ))
        
        self.register_action(ActionDefinition(
            action_type=ActionType.SCHEDULE_REVIEW,
            name="Schedule Review",
            description="Schedule document for manual review",
            params_schema={"reviewer": "string", "review_date": "string", "priority": "string"}
        ))
        
        self.register_action(ActionDefinition(
            action_type=ActionType.API_CALL,
            name="External API Call",
            description="Call external API endpoint",
            params_schema={"endpoint": "string", "method": "string", "payload": "dict"}
        ))
    
    def register_action(self, action_def: ActionDefinition) -> None:
        """Register an action definition."""
        self.action_registry[action_def.action_type.value] = action_def
    
    def register_integration(self, name: str, handler: Callable) -> None:
        """Register an integration handler."""
        self.integration_handlers[name] = handler
    
    def _map_custom_action(self, action_str: str) -> tuple:
        """
        Map custom action strings to standard BPS action types.
        Returns (ActionType, mapped_name, params)
        """
        action_lower = action_str.lower().strip()
        
        # Email/Notification mappings
        if any(kw in action_lower for kw in ["mail", "email", "send", "notify", "alert"]):
            return (ActionType.SEND_EMAIL, f"Send Email: {action_str}", 
                    {"subject": action_str, "template": "notification"})
        
        # Escalation mappings
        if any(kw in action_lower for kw in ["escalate", "supervisor", "manager", "senior"]):
            target = "manager" if "manager" in action_lower else "supervisor"
            return (ActionType.ESCALATE, f"Escalate to {target.title()}", 
                    {"escalate_to": target, "urgency": "high"})
        
        # Approval mappings
        if any(kw in action_lower for kw in ["approve", "accept", "process", "proceed"]):
            return (ActionType.APPROVE, f"Approve: {action_str}", 
                    {"approval_level": "rule_based"})
        
        # Rejection mappings
        if any(kw in action_lower for kw in ["reject", "deny", "decline", "refuse"]):
            return (ActionType.REJECT, f"Reject: {action_str}", 
                    {"reason": action_str})
        
        # Review/Flag mappings
        if any(kw in action_lower for kw in ["review", "check", "verify", "investigate", "flag", "fraud"]):
            return (ActionType.SCHEDULE_REVIEW, f"Schedule Review: {action_str}", 
                    {"priority": "high", "reason": action_str})
        
        # Routing mappings
        if any(kw in action_lower for kw in ["route", "assign", "transfer", "forward", "team"]):
            return (ActionType.ROUTE, f"Route: {action_str}", 
                    {"route_to": action_str})
        
        # Ticket creation
        if any(kw in action_lower for kw in ["ticket", "case", "incident", "issue"]):
            return (ActionType.CREATE_TICKET, f"Create Ticket: {action_str}", 
                    {"title": action_str, "priority": "medium"})
        
        # Request info
        if any(kw in action_lower for kw in ["request", "ask", "need", "missing", "require"]):
            return (ActionType.REQUEST_INFO, f"Request Info: {action_str}", 
                    {"message": action_str})
        
        # Default: Create a notification
        return (ActionType.NOTIFY, f"Action: {action_str}", 
                {"message": action_str, "channel": "system"})
    
    def execute_action(
        self,
        action_type: str,
        params: Dict[str, Any],
        context: Optional[Dict] = None
    ) -> ActionExecution:
        """
        Execute a single action.
        
        Args:
            action_type: Type of action to execute
            params: Parameters for the action
            context: Optional context (document_id, entities, etc.)
            
        Returns:
            ActionExecution record
        """
        execution_id = str(uuid.uuid4())[:8]
        started_at = datetime.now()
        
        action_def = self.action_registry.get(action_type)
        
        # If action not found, try to map custom action to standard type
        if not action_def:
            mapped_type, mapped_name, mapped_params = self._map_custom_action(action_type)
            action_def = self.action_registry.get(mapped_type.value)
            
            if action_def:
                # Use the mapped action with custom name
                params = {**mapped_params, **params}
                
                execution = ActionExecution(
                    execution_id=execution_id,
                    action_type=mapped_type,
                    action_name=mapped_name,
                    status=ActionStatus.IN_PROGRESS,
                    params=params,
                    started_at=started_at.isoformat(),
                )
                
                try:
                    if self.demo_mode:
                        result = self._simulate_action(mapped_type, params, context)
                    else:
                        result = self._execute_real_action(action_def, params, context)
                    
                    execution.status = ActionStatus.COMPLETED
                    execution.result = result
                    
                except Exception as e:
                    execution.status = ActionStatus.FAILED
                    execution.error = str(e)
                
                completed_at = datetime.now()
                execution.completed_at = completed_at.isoformat()
                execution.duration_ms = int((completed_at - started_at).total_seconds() * 1000)
                
                self.execution_history.append(execution)
                return execution
        
        execution = ActionExecution(
            execution_id=execution_id,
            action_type=action_def.action_type,
            action_name=action_def.name,
            status=ActionStatus.IN_PROGRESS,
            params=params,
            started_at=started_at.isoformat(),
        )
        
        try:
            if self.demo_mode:
                # Simulate action execution
                result = self._simulate_action(action_def.action_type, params, context)
            else:
                # Execute real action
                result = self._execute_real_action(action_def, params, context)
            
            execution.status = ActionStatus.COMPLETED
            execution.result = result
            
        except Exception as e:
            execution.status = ActionStatus.FAILED
            execution.error = str(e)
        
        completed_at = datetime.now()
        execution.completed_at = completed_at.isoformat()
        execution.duration_ms = int((completed_at - started_at).total_seconds() * 1000)
        
        # Add to history
        self.execution_history.append(execution)
        
        return execution
    
    def _simulate_action(
        self,
        action_type: ActionType,
        params: Dict[str, Any],
        context: Optional[Dict]
    ) -> Dict[str, Any]:
        """Simulate action execution for demo purposes."""
        
        simulated_results = {
            ActionType.ROUTE: {
                "status": "routed",
                "destination": params.get("route_to", "default_queue"),
                "queue_position": 3,
                "estimated_wait": "2 hours",
                "message": f"Document routed to {params.get('route_to', 'default queue')}"
            },
            ActionType.APPROVE: {
                "status": "approved",
                "approval_id": f"APR-{uuid.uuid4().hex[:6].upper()}",
                "approved_by": "System (Auto-Approval)",
                "approval_level": params.get("approval_level", "automatic"),
                "message": "Request has been automatically approved"
            },
            ActionType.REJECT: {
                "status": "rejected",
                "rejection_id": f"REJ-{uuid.uuid4().hex[:6].upper()}",
                "reason": params.get("reason", "Did not meet criteria"),
                "message": "Request has been rejected"
            },
            ActionType.FLAG: {
                "status": "flagged",
                "flag_id": f"FLG-{uuid.uuid4().hex[:6].upper()}",
                "flag_type": params.get("flag_type", "attention_required"),
                "message": f"Document flagged: {params.get('flag_type', 'attention required')}"
            },
            ActionType.NOTIFY: {
                "status": "sent",
                "notification_id": f"NOT-{uuid.uuid4().hex[:6].upper()}",
                "recipients": params.get("recipients", ["default"]),
                "channel": params.get("channel", "email"),
                "message": "Notification sent successfully"
            },
            ActionType.CREATE_TICKET: {
                "status": "created",
                "ticket_id": f"TKT-{uuid.uuid4().hex[:6].upper()}",
                "title": params.get("title", "New Ticket"),
                "assignee": params.get("assignee", "unassigned"),
                "priority": params.get("priority", "medium"),
                "message": "Support ticket created"
            },
            ActionType.SEND_EMAIL: {
                "status": "sent",
                "email_id": f"EML-{uuid.uuid4().hex[:6].upper()}",
                "to": params.get("to", []),
                "subject": params.get("subject", ""),
                "message": "Email sent successfully"
            },
            ActionType.ESCALATE: {
                "status": "escalated",
                "escalation_id": f"ESC-{uuid.uuid4().hex[:6].upper()}",
                "escalated_to": params.get("escalate_to", "supervisor"),
                "urgency": params.get("urgency", "normal"),
                "message": f"Escalated to {params.get('escalate_to', 'supervisor')}"
            },
            ActionType.REQUEST_INFO: {
                "status": "requested",
                "request_id": f"REQ-{uuid.uuid4().hex[:6].upper()}",
                "requested_fields": params.get("requested_fields", []),
                "deadline": params.get("deadline_days", 5),
                "message": "Additional information requested from customer"
            },
            ActionType.SCHEDULE_REVIEW: {
                "status": "scheduled",
                "review_id": f"REV-{uuid.uuid4().hex[:6].upper()}",
                "reviewer": params.get("reviewer", "available_reviewer"),
                "scheduled_date": params.get("review_date", "next_business_day"),
                "message": "Manual review scheduled"
            },
            ActionType.API_CALL: {
                "status": "completed",
                "call_id": f"API-{uuid.uuid4().hex[:6].upper()}",
                "endpoint": params.get("endpoint", ""),
                "response_code": 200,
                "message": "API call completed successfully"
            },
        }
        
        return simulated_results.get(action_type, {"status": "completed", "message": "Action executed"})
    
    def _execute_real_action(
        self,
        action_def: ActionDefinition,
        params: Dict[str, Any],
        context: Optional[Dict]
    ) -> Dict[str, Any]:
        """Execute real action (for production use)."""
        
        if action_def.handler:
            return action_def.handler(params, context)
        
        # Check for registered integration
        integration_name = params.get("integration")
        if integration_name and integration_name in self.integration_handlers:
            return self.integration_handlers[integration_name](params, context)
        
        # Default fallback - just return simulated result
        return self._simulate_action(action_def.action_type, params, context)
    
    def execute_decision(
        self,
        decision: Dict[str, Any],
        document_context: Optional[Dict] = None
    ) -> List[ActionExecution]:
        """
        Execute all actions from a rule engine decision.
        
        Args:
            decision: Decision from RuleEngine.get_decision()
            document_context: Document context (entities, metadata)
            
        Returns:
            List of ActionExecution records
        """
        executions = []
        
        # Build context
        context = {
            "decision_timestamp": decision.get("timestamp"),
            "matched_rules": decision.get("matched_rules", 0),
            "needs_review": decision.get("needs_manual_review", False),
        }
        if document_context:
            context.update(document_context)
        
        # Execute primary action if present
        primary_action = decision.get("primary_action")
        if primary_action:
            routing = decision.get("routing")
            flags = decision.get("flags", [])
            
            params = {
                "route_to": routing,
                "flags": flags,
            }
            
            execution = self.execute_action(primary_action, params, context)
            executions.append(execution)
        
        # Execute additional actions from rules
        for rule in decision.get("rules", []):
            action = rule.get("action")
            action_params = rule.get("params", {})
            
            # Skip if same as primary action
            if action == primary_action:
                continue
            
            execution = self.execute_action(action, action_params, context)
            executions.append(execution)
        
        # If manual review needed, schedule it
        if decision.get("needs_manual_review"):
            review_params = {
                "reason": f"Low confidence fields: {', '.join(decision.get('low_confidence_fields', []))}",
                "priority": "high" if len(decision.get("low_confidence_fields", [])) > 3 else "normal"
            }
            execution = self.execute_action("schedule_review", review_params, context)
            executions.append(execution)
        
        return executions
    
    def get_execution_summary(self) -> Dict[str, Any]:
        """Get summary of all executions."""
        total = len(self.execution_history)
        completed = sum(1 for e in self.execution_history if e.status == ActionStatus.COMPLETED)
        failed = sum(1 for e in self.execution_history if e.status == ActionStatus.FAILED)
        
        by_type = {}
        for execution in self.execution_history:
            action_type = execution.action_type.value
            if action_type not in by_type:
                by_type[action_type] = {"total": 0, "completed": 0, "failed": 0}
            by_type[action_type]["total"] += 1
            if execution.status == ActionStatus.COMPLETED:
                by_type[action_type]["completed"] += 1
            elif execution.status == ActionStatus.FAILED:
                by_type[action_type]["failed"] += 1
        
        avg_duration = 0
        if self.execution_history:
            avg_duration = sum(e.duration_ms for e in self.execution_history) / len(self.execution_history)
        
        return {
            "total_executions": total,
            "completed": completed,
            "failed": failed,
            "success_rate": f"{(completed/total*100):.1f}%" if total > 0 else "N/A",
            "by_action_type": by_type,
            "avg_duration_ms": round(avg_duration, 2),
        }
    
    def get_audit_trail(
        self,
        document_id: Optional[str] = None,
        action_type: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Dict]:
        """Get audit trail of executions."""
        trail = []
        
        for execution in self.execution_history:
            # Apply filters
            if action_type and execution.action_type.value != action_type:
                continue
            if status and execution.status.value != status:
                continue
            
            trail.append({
                "execution_id": execution.execution_id,
                "action_type": execution.action_type.value,
                "action_name": execution.action_name,
                "status": execution.status.value,
                "params": execution.params,
                "result": execution.result,
                "error": execution.error,
                "started_at": execution.started_at,
                "completed_at": execution.completed_at,
                "duration_ms": execution.duration_ms,
            })
        
        return trail


# Pre-built workflow templates
CLAIM_PROCESSING_WORKFLOW = [
    WorkflowStep(
        step_id="validate",
        name="Validate Claim Data",
        action_type=ActionType.FLAG,
        params={"flag_type": "validation_check"},
        next_on_success="route_claim",
        next_on_failure="request_info"
    ),
    WorkflowStep(
        step_id="route_claim",
        name="Route to Appropriate Team",
        action_type=ActionType.ROUTE,
        params={"route_to": "claims_team"},
        next_on_success="notify_customer",
    ),
    WorkflowStep(
        step_id="request_info",
        name="Request Missing Information",
        action_type=ActionType.REQUEST_INFO,
        params={"requested_fields": ["policy_number", "incident_details"]},
        next_on_success="validate",
    ),
    WorkflowStep(
        step_id="notify_customer",
        name="Send Confirmation to Customer",
        action_type=ActionType.SEND_EMAIL,
        params={"template": "claim_received"},
    ),
]

INVOICE_PAYMENT_WORKFLOW = [
    WorkflowStep(
        step_id="validate_invoice",
        name="Validate Invoice",
        action_type=ActionType.FLAG,
        params={"flag_type": "invoice_validation"},
        next_on_success="check_amount",
        next_on_failure="reject_invoice"
    ),
    WorkflowStep(
        step_id="check_amount",
        name="Check Amount Threshold",
        action_type=ActionType.FLAG,
        params={"flag_type": "amount_check"},
        next_on_success="auto_pay",
        condition={"field": "total_amount", "operator": "less_than", "value": 1000}
    ),
    WorkflowStep(
        step_id="auto_pay",
        name="Process Auto Payment",
        action_type=ActionType.APPROVE,
        params={"approval_level": "automatic"},
        next_on_success="notify_vendor",
    ),
    WorkflowStep(
        step_id="notify_vendor",
        name="Notify Vendor",
        action_type=ActionType.SEND_EMAIL,
        params={"template": "payment_confirmation"},
    ),
    WorkflowStep(
        step_id="reject_invoice",
        name="Reject Invalid Invoice",
        action_type=ActionType.REJECT,
        params={"reason": "Invalid invoice data"},
    ),
]

