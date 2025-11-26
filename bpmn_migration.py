import xml.etree.ElementTree as ET
import sys
import json
import csv
import re
from datetime import datetime
from enum import Enum
from typing import List, Dict, Any, Set


class Severity(Enum):
    """Issue severity levels"""
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"


class MigrationIssue:
    """Represents a migration issue with severity and details"""

    def __init__(self, severity: Severity, category: str, element_id: str,
                 element_name: str, message: str, details: str = ""):
        self.severity = severity
        self.category = category
        self.element_id = element_id
        self.element_name = element_name
        self.message = message
        self.details = details

    def to_dict(self) -> Dict[str, Any]:
        return {
            'severity': self.severity.value,
            'category': self.category,
            'element_id': self.element_id,
            'element_name': self.element_name,
            'message': self.message,
            'details': self.details
        }


class BPMNAnalyzer:
    """Main analyzer class for BPMN migration assessment"""

    def __init__(self, bpmn_file: str):
        self.bpmn_file = bpmn_file
        self.namespace = {
            'bpmn': 'http://www.omg.org/spec/BPMN/20100524/MODEL',
            'bpmn2': 'http://www.omg.org/spec/BPMN/20100524/MODEL',
            'camunda': 'http://camunda.org/schema/1.0/bpmn',
            'xsi': 'http://www.w3.org/2001/XMLSchema-instance'
        }
        self.tree = None
        self.root = None
        self.issues: List[MigrationIssue] = []
        self.statistics = {}
        self.process_variables: Set[str] = set()

    def parse(self) -> bool:
        """Parse the BPMN XML file"""
        try:
            self.tree = ET.parse(self.bpmn_file)
            self.root = self.tree.getroot()
            return True
        except Exception as e:
            print(f"Error parsing BPMN file: {e}")
            return False

    def add_issue(self, severity: Severity, category: str, element_id: str,
                  element_name: str, message: str, details: str = ""):
        """Add a migration issue"""
        issue = MigrationIssue(severity, category, element_id, element_name, message, details)
        self.issues.append(issue)

    # ==================== Expression Validation ====================

    def extract_variables_from_expression(self, expression: str) -> Set[str]:
        """Extract variable names from JUEL/UEL expressions"""
        if not expression:
            return set()

        # Pattern for ${variable} or #{variable}
        pattern = r'[$#]\{([^}]+)\}'
        matches = re.findall(pattern, expression)

        variables = set()
        for match in matches:
            # Extract variable name (before dots, brackets, etc.)
            var_name = re.split(r'[\.\[\(\s]', match)[0]
            if var_name:
                variables.add(var_name)

        return variables

    def validate_expression_syntax(self, expression: str, element_id: str,
                                   element_name: str, context: str):
        """Validate expression syntax and detect JUEL expressions"""
        if not expression:
            return

        # Extract variables
        variables = self.extract_variables_from_expression(expression)
        self.process_variables.update(variables)

        # Check for JUEL/UEL syntax (needs conversion to FEEL)
        if '${' in expression or '#{' in expression:
            self.add_issue(
                Severity.CRITICAL,
                "Expression",
                element_id,
                element_name,
                f"JUEL/UEL expression detected in {context}",
                f"Expression '{expression}' uses Camunda 7 syntax. Must be converted to FEEL in Camunda 8. "
                f"Example: '${{myVar}}' -> '=myVar'"
            )

        # Check for incomplete expressions
        if ('${' in expression and '}' not in expression) or \
           ('#{' in expression and '}' not in expression):
            self.add_issue(
                Severity.CRITICAL,
                "Expression",
                element_id,
                element_name,
                f"Malformed expression in {context}",
                f"Expression '{expression}' appears to be incomplete"
            )

    # ==================== Service Task Validation ====================

    def validate_service_tasks(self):
        """Validate service tasks including connectors and delegates"""
        service_tasks = self.root.findall('.//bpmn:serviceTask', self.namespace)

        for task in service_tasks:
            task_id = task.get('id', 'unknown')
            task_name = task.get('name', 'Unnamed')

            # Check for external task
            task_type = task.get('{http://camunda.org/schema/1.0/bpmn}type')
            topic = task.get('{http://camunda.org/schema/1.0/bpmn}topic')

            # Check for delegate
            delegate_expression = task.get('{http://camunda.org/schema/1.0/bpmn}delegateExpression')
            class_name = task.get('{http://camunda.org/schema/1.0/bpmn}class')
            expression = task.get('{http://camunda.org/schema/1.0/bpmn}expression')

            # Check for HTTP connector
            connector_id = task.get('{http://camunda.org/schema/1.0/bpmn}connectorId')

            if task_type == 'external':
                self.add_issue(
                    Severity.INFO,
                    "Service Task",
                    task_id,
                    task_name,
                    "External task pattern already compatible",
                    f"Topic: {topic}. Ensure workers are updated to use Camunda 8 client."
                )

            if delegate_expression:
                self.validate_expression_syntax(delegate_expression, task_id, task_name, "delegateExpression")
                self.add_issue(
                    Severity.CRITICAL,
                    "Service Task",
                    task_id,
                    task_name,
                    "Delegate expression must be converted to Job Worker",
                    f"Delegate: {delegate_expression}. Implement as external task worker in Camunda 8."
                )

            if class_name:
                self.add_issue(
                    Severity.CRITICAL,
                    "Service Task",
                    task_id,
                    task_name,
                    "Java delegate class must be converted to Job Worker",
                    f"Class: {class_name}. Implement as external task worker in Camunda 8."
                )

            if expression:
                self.validate_expression_syntax(expression, task_id, task_name, "expression attribute")

            if connector_id:
                self.add_issue(
                    Severity.CRITICAL,
                    "Connector",
                    task_id,
                    task_name,
                    "Camunda Connector must be migrated",
                    f"Connector ID: {connector_id}. Convert to Camunda 8 Connector Template or Job Worker."
                )

            # Check for async configuration
            async_before = task.get('{http://camunda.org/schema/1.0/bpmn}asyncBefore')
            async_after = task.get('{http://camunda.org/schema/1.0/bpmn}asyncAfter')

            if async_before == 'true' or async_after == 'true':
                self.add_issue(
                    Severity.INFO,
                    "Configuration",
                    task_id,
                    task_name,
                    "Async configuration not needed in Camunda 8",
                    "All service tasks are asynchronous by default in Camunda 8."
                )

            # Check for retry configuration
            retry = task.get('{http://camunda.org/schema/1.0/bpmn}failedJobRetryTimeCycle')
            if retry:
                self.add_issue(
                    Severity.WARNING,
                    "Configuration",
                    task_id,
                    task_name,
                    "Retry configuration uses different syntax",
                    f"Current: {retry}. Use Zeebe retry headers in Camunda 8."
                )

    # ==================== Script Task Validation ====================

    def validate_script_tasks(self):
        """Validate script tasks and script formats"""
        script_tasks = self.root.findall('.//bpmn:scriptTask', self.namespace)

        for task in script_tasks:
            task_id = task.get('id', 'unknown')
            task_name = task.get('name', 'Unnamed')
            script_format = task.get('{http://camunda.org/schema/1.0/bpmn}scriptFormat')

            script_element = task.find('bpmn:script', self.namespace)
            script_content = script_element.text if script_element is not None else ""

            if script_format and script_format.lower() not in ['feel', 'javascript', 'groovy']:
                self.add_issue(
                    Severity.CRITICAL,
                    "Script Task",
                    task_id,
                    task_name,
                    f"Script format '{script_format}' not supported in Camunda 8",
                    "Consider converting to FEEL or implementing as Job Worker."
                )
            elif script_format and script_format.lower() in ['groovy', 'javascript']:
                self.add_issue(
                    Severity.WARNING,
                    "Script Task",
                    task_id,
                    task_name,
                    f"Script format '{script_format}' support is limited",
                    "Groovy and JavaScript support may differ. Test thoroughly or convert to FEEL."
                )

            # Check for variables in script
            if script_content:
                variables = self.extract_variables_from_expression(script_content)
                self.process_variables.update(variables)

    # ==================== Gateway Validation ====================

    def validate_gateways(self):
        """Validate all gateway types and their conditions"""
        gateway_types = [
            'exclusiveGateway', 'parallelGateway', 'inclusiveGateway',
            'eventBasedGateway', 'complexGateway'
        ]

        for gw_type in gateway_types:
            gateways = self.root.findall(f'.//bpmn:{gw_type}', self.namespace)

            for gateway in gateways:
                gw_id = gateway.get('id', 'unknown')
                gw_name = gateway.get('name', 'Unnamed')

                # Find outgoing sequence flows
                outgoing_flows = gateway.findall('bpmn:outgoing', self.namespace)

                for outgoing in outgoing_flows:
                    flow_id = outgoing.text
                    if flow_id:
                        # Find the sequence flow element
                        flow = self.root.find(f".//bpmn:sequenceFlow[@id='{flow_id}']", self.namespace)
                        if flow is not None:
                            condition = flow.find('bpmn:conditionExpression', self.namespace)
                            if condition is not None and condition.text:
                                self.validate_expression_syntax(
                                    condition.text.strip(),
                                    gw_id,
                                    gw_name,
                                    f"gateway condition on flow {flow_id}"
                                )

                # Specific validations per gateway type
                if gw_type == 'complexGateway':
                    self.add_issue(
                        Severity.CRITICAL,
                        "Gateway",
                        gw_id,
                        gw_name,
                        "Complex gateway not supported in Camunda 8",
                        "Consider redesigning using exclusive or parallel gateways."
                    )

                if gw_type == 'eventBasedGateway':
                    self.add_issue(
                        Severity.WARNING,
                        "Gateway",
                        gw_id,
                        gw_name,
                        "Event-based gateway behavior may differ",
                        "Review event correlation and timing in Camunda 8."
                    )

    # ==================== Event Validation ====================

    def validate_events(self):
        """Validate all event types including timers, messages, signals, and errors"""
        event_types = [
            'startEvent', 'endEvent', 'intermediateCatchEvent',
            'intermediateThrowEvent', 'boundaryEvent'
        ]

        for event_type in event_types:
            events = self.root.findall(f'.//bpmn:{event_type}', self.namespace)

            for event in events:
                event_id = event.get('id', 'unknown')
                event_name = event.get('name', 'Unnamed')

                # Find event definition
                timer_def = event.find('bpmn:timerEventDefinition', self.namespace)
                message_def = event.find('bpmn:messageEventDefinition', self.namespace)
                signal_def = event.find('bpmn:signalEventDefinition', self.namespace)
                error_def = event.find('bpmn:errorEventDefinition', self.namespace)
                escalation_def = event.find('bpmn:escalationEventDefinition', self.namespace)

                # Validate timer events
                if timer_def is not None:
                    self.validate_timer_event(timer_def, event_id, event_name)

                # Validate message events
                if message_def is not None:
                    self.validate_message_event(message_def, event_id, event_name)

                # Validate signal events
                if signal_def is not None:
                    self.validate_signal_event(signal_def, event_id, event_name)

                # Validate error events
                if error_def is not None:
                    self.validate_error_event(error_def, event_id, event_name)

                # Validate escalation events
                if escalation_def is not None:
                    self.add_issue(
                        Severity.WARNING,
                        "Event",
                        event_id,
                        event_name,
                        "Escalation event behavior may differ in Camunda 8",
                        "Review escalation handling and consider alternatives."
                    )

    def validate_timer_event(self, timer_def, event_id: str, event_name: str):
        """Validate timer event definitions"""
        time_date = timer_def.find('bpmn:timeDate', self.namespace)
        time_duration = timer_def.find('bpmn:timeDuration', self.namespace)
        time_cycle = timer_def.find('bpmn:timeCycle', self.namespace)

        for time_element, time_type in [
            (time_date, 'timeDate'),
            (time_duration, 'timeDuration'),
            (time_cycle, 'timeCycle')
        ]:
            if time_element is not None and time_element.text:
                expression = time_element.text.strip()
                self.validate_expression_syntax(expression, event_id, event_name, f"timer {time_type}")

                # Check for ISO 8601 format
                if not expression.startswith('P') and not expression.startswith('='):
                    self.add_issue(
                        Severity.WARNING,
                        "Timer",
                        event_id,
                        event_name,
                        f"Timer {time_type} should use ISO 8601 format",
                        f"Expression: {expression}. Ensure compatibility with Camunda 8."
                    )

    def validate_message_event(self, message_def, event_id: str, event_name: str):
        """Validate message event definitions"""
        message_ref = message_def.get('messageRef')

        if message_ref:
            # Find message definition
            message = self.root.find(f".//bpmn:message[@id='{message_ref}']", self.namespace)
            if message is not None:
                message_name = message.get('name')

                # Check for correlation keys in extension elements
                ext_elements = message.find('bpmn:extensionElements', self.namespace)
                if ext_elements is not None:
                    # Look for message event subscriptions or input/output mappings
                    self.add_issue(
                        Severity.WARNING,
                        "Message Event",
                        event_id,
                        event_name,
                        "Message correlation may need adjustment",
                        f"Message: {message_name}. Review correlation keys for Camunda 8."
                    )

    def validate_signal_event(self, signal_def, event_id: str, event_name: str):
        """Validate signal event definitions"""
        signal_ref = signal_def.get('signalRef')

        if signal_ref:
            self.add_issue(
                Severity.WARNING,
                "Signal Event",
                event_id,
                event_name,
                "Signal event behavior may differ in Camunda 8",
                f"Signal reference: {signal_ref}. Verify signal scope and propagation."
            )

    def validate_error_event(self, error_def, event_id: str, event_name: str):
        """Validate error event definitions"""
        error_ref = error_def.get('errorRef')
        error_code = error_def.get('{http://camunda.org/schema/1.0/bpmn}errorCodeVariable')
        error_message = error_def.get('{http://camunda.org/schema/1.0/bpmn}errorMessageVariable')

        if error_ref:
            # Find error definition
            error = self.root.find(f".//bpmn:error[@id='{error_ref}']", self.namespace)
            if error is not None:
                error_code_attr = error.get('errorCode')
                error_name_attr = error.get('name')

                self.add_issue(
                    Severity.INFO,
                    "Error Event",
                    event_id,
                    event_name,
                    "Error handling is compatible but verify error codes",
                    f"Error: {error_name_attr}, Code: {error_code_attr}"
                )

    # ==================== User Task and Forms Validation ====================

    def validate_user_tasks(self):
        """Validate user tasks and form configurations"""
        user_tasks = self.root.findall('.//bpmn:userTask', self.namespace)

        for task in user_tasks:
            task_id = task.get('id', 'unknown')
            task_name = task.get('name', 'Unnamed')

            # Check form configuration
            form_key = task.get('{http://camunda.org/schema/1.0/bpmn}formKey')
            form_ref = task.get('{http://camunda.org/schema/1.0/bpmn}formRef')

            if form_key:
                if form_key.startswith('embedded:') or form_key.startswith('camunda-forms:'):
                    self.add_issue(
                        Severity.CRITICAL,
                        "User Task",
                        task_id,
                        task_name,
                        "Embedded form must be converted to Camunda 8 Forms",
                        f"Form key: {form_key}. Migrate to Camunda Forms JSON schema."
                    )
                else:
                    self.add_issue(
                        Severity.WARNING,
                        "User Task",
                        task_id,
                        task_name,
                        "External form reference needs review",
                        f"Form key: {form_key}. Ensure form is accessible in Camunda 8."
                    )

            if form_ref:
                self.add_issue(
                    Severity.WARNING,
                    "User Task",
                    task_id,
                    task_name,
                    "Form reference needs verification",
                    f"Form ref: {form_ref}"
                )

            # Check for form fields in extension elements
            ext_elements = task.find('bpmn:extensionElements', self.namespace)
            if ext_elements is not None:
                form_data = ext_elements.find('camunda:formData', self.namespace)
                if form_data is not None:
                    form_fields = form_data.findall('camunda:formField', self.namespace)
                    if form_fields:
                        self.add_issue(
                            Severity.CRITICAL,
                            "User Task",
                            task_id,
                            task_name,
                            f"Embedded form with {len(form_fields)} fields must be migrated",
                            "Convert form fields to Camunda 8 Forms JSON schema."
                        )

            # Check assignment
            assignee = task.get('{http://camunda.org/schema/1.0/bpmn}assignee')
            candidate_users = task.get('{http://camunda.org/schema/1.0/bpmn}candidateUsers')
            candidate_groups = task.get('{http://camunda.org/schema/1.0/bpmn}candidateGroups')

            if assignee:
                self.validate_expression_syntax(assignee, task_id, task_name, "assignee")
            if candidate_users:
                self.validate_expression_syntax(candidate_users, task_id, task_name, "candidateUsers")
            if candidate_groups:
                self.validate_expression_syntax(candidate_groups, task_id, task_name, "candidateGroups")

    # ==================== Listener Validation ====================

    def validate_listeners(self):
        """Validate both task listeners and execution listeners"""
        # Find all extension elements
        all_elements = self.root.findall('.//*', self.namespace)

        for element in all_elements:
            element_id = element.get('id', 'unknown')
            element_name = element.get('name', 'Unnamed')
            element_type = element.tag.split('}')[1] if '}' in element.tag else element.tag

            ext_elements = element.find('bpmn:extensionElements', self.namespace)
            if ext_elements is not None:
                # Task listeners
                task_listeners = ext_elements.findall('camunda:taskListener', self.namespace)
                for listener in task_listeners:
                    self.validate_listener(listener, element_id, element_name, "Task Listener")

                # Execution listeners
                execution_listeners = ext_elements.findall('camunda:executionListener', self.namespace)
                for listener in execution_listeners:
                    self.validate_listener(listener, element_id, element_name, "Execution Listener")

    def validate_listener(self, listener, element_id: str, element_name: str, listener_type: str):
        """Validate a single listener"""
        event = listener.get('event')
        delegate_expression = listener.get('delegateExpression')
        class_name = listener.get('class')
        expression = listener.get('expression')

        if delegate_expression or class_name or expression:
            self.add_issue(
                Severity.CRITICAL,
                listener_type,
                element_id,
                element_name,
                f"{listener_type} not supported in Camunda 8",
                f"Event: {event}. Convert listener logic to Job Worker or process redesign."
            )

            if delegate_expression:
                self.validate_expression_syntax(delegate_expression, element_id, element_name, listener_type)
            if expression:
                self.validate_expression_syntax(expression, element_id, element_name, listener_type)

    # ==================== Call Activity and Business Rule Validation ====================

    def validate_call_activities(self):
        """Validate call activities and their configurations"""
        call_activities = self.root.findall('.//bpmn:callActivity', self.namespace)

        for activity in call_activities:
            activity_id = activity.get('id', 'unknown')
            activity_name = activity.get('name', 'Unnamed')
            called_element = activity.get('calledElement')

            if called_element:
                self.validate_expression_syntax(called_element, activity_id, activity_name, "calledElement")

                self.add_issue(
                    Severity.WARNING,
                    "Call Activity",
                    activity_id,
                    activity_name,
                    "Call activity requires verification",
                    f"Called element: {called_element}. Ensure called process exists in Camunda 8."
                )

            # Check variable mapping
            ext_elements = activity.find('bpmn:extensionElements', self.namespace)
            if ext_elements is not None:
                in_mappings = ext_elements.findall('camunda:in', self.namespace)
                out_mappings = ext_elements.findall('camunda:out', self.namespace)

                if in_mappings or out_mappings:
                    self.add_issue(
                        Severity.WARNING,
                        "Call Activity",
                        activity_id,
                        activity_name,
                        "Variable mapping syntax differs in Camunda 8",
                        f"Found {len(in_mappings)} input and {len(out_mappings)} output mappings."
                    )

    def validate_business_rule_tasks(self):
        """Validate business rule tasks and DMN references"""
        business_rule_tasks = self.root.findall('.//bpmn:businessRuleTask', self.namespace)

        for task in business_rule_tasks:
            task_id = task.get('id', 'unknown')
            task_name = task.get('name', 'Unnamed')
            decision_ref = task.get('{http://camunda.org/schema/1.0/bpmn}decisionRef')

            if decision_ref:
                self.validate_expression_syntax(decision_ref, task_id, task_name, "decisionRef")

                self.add_issue(
                    Severity.WARNING,
                    "Business Rule Task",
                    task_id,
                    task_name,
                    "DMN decision reference needs verification",
                    f"Decision: {decision_ref}. Ensure DMN is deployed and compatible with Camunda 8."
                )

    # ==================== Multi-Instance and Subprocess Validation ====================

    def validate_multi_instance(self):
        """Validate multi-instance configurations"""
        multi_instances = self.root.findall('.//bpmn:multiInstanceLoopCharacteristics', self.namespace)

        for mi in multi_instances:
            parent = self.find_parent(mi)
            if parent is not None:
                parent_id = parent.get('id', 'unknown')
                parent_name = parent.get('name', 'Unnamed')

                collection = mi.get('{http://camunda.org/schema/1.0/bpmn}collection')
                element_variable = mi.get('{http://camunda.org/schema/1.0/bpmn}elementVariable')

                if collection:
                    self.validate_expression_syntax(collection, parent_id, parent_name, "multi-instance collection")

                # Check completion condition
                completion_condition = mi.find('bpmn:completionCondition', self.namespace)
                if completion_condition is not None and completion_condition.text:
                    self.validate_expression_syntax(
                        completion_condition.text.strip(),
                        parent_id,
                        parent_name,
                        "multi-instance completion condition"
                    )

    def find_parent(self, element):
        """Find parent element in tree"""
        for parent in self.root.iter():
            if element in list(parent):
                return parent
        return None

    def validate_subprocesses(self):
        """Validate subprocess configurations"""
        subprocesses = self.root.findall('.//bpmn:subProcess', self.namespace)

        for subprocess in subprocesses:
            subprocess_id = subprocess.get('id', 'unknown')
            subprocess_name = subprocess.get('name', 'Unnamed')
            triggered_by_event = subprocess.get('triggeredByEvent')

            if triggered_by_event == 'true':
                self.add_issue(
                    Severity.WARNING,
                    "Subprocess",
                    subprocess_id,
                    subprocess_name,
                    "Event subprocess behavior may differ in Camunda 8",
                    "Review event subprocess triggering and variable scope."
                )

    # ==================== Input/Output Mapping Validation ====================

    def validate_input_output_mappings(self):
        """Validate input/output parameter mappings"""
        all_elements = self.root.findall('.//*', self.namespace)

        for element in all_elements:
            element_id = element.get('id', 'unknown')
            element_name = element.get('name', 'Unnamed')

            ext_elements = element.find('bpmn:extensionElements', self.namespace)
            if ext_elements is not None:
                input_output = ext_elements.find('camunda:inputOutput', self.namespace)
                if input_output is not None:
                    input_params = input_output.findall('camunda:inputParameter', self.namespace)
                    output_params = input_output.findall('camunda:outputParameter', self.namespace)

                    for param in input_params + output_params:
                        param_name = param.get('name')
                        param_text = param.text

                        if param_text:
                            self.validate_expression_syntax(param_text.strip(), element_id, element_name, f"I/O parameter {param_name}")

                        # Check for script in parameter
                        script = param.find('camunda:script', self.namespace)
                        if script is not None:
                            self.add_issue(
                                Severity.CRITICAL,
                                "I/O Mapping",
                                element_id,
                                element_name,
                                "Script in I/O parameter not supported",
                                f"Parameter: {param_name}. Convert to FEEL expression or Job Worker."
                            )

    # ==================== Configuration Validation ====================

    def validate_configurations(self):
        """Validate various Camunda 7 configurations"""
        all_elements = self.root.findall('.//*', self.namespace)

        for element in all_elements:
            element_id = element.get('id', 'unknown')
            element_name = element.get('name', 'Unnamed')

            # Check for history time to live
            history_ttl = element.get('{http://camunda.org/schema/1.0/bpmn}historyTimeToLive')
            if history_ttl:
                self.add_issue(
                    Severity.INFO,
                    "Configuration",
                    element_id,
                    element_name,
                    "History TTL configuration not applicable in Camunda 8",
                    f"TTL: {history_ttl}. Camunda 8 has different data retention mechanisms."
                )

            # Check for job priority
            job_priority = element.get('{http://camunda.org/schema/1.0/bpmn}jobPriority')
            if job_priority:
                self.add_issue(
                    Severity.INFO,
                    "Configuration",
                    element_id,
                    element_name,
                    "Job priority not supported in Camunda 8",
                    f"Priority: {job_priority}"
                )

    def validate_namespaces(self):
        """Validate BPMN namespaces and versions"""
        # Check root element
        if self.root is not None:
            # Check for BPMN 2.0 namespace
            bpmn_ns = self.root.get('{http://www.w3.org/2001/XMLSchema-instance}schemaLocation')

            if not bpmn_ns or 'BPMN/20100524' not in bpmn_ns:
                self.add_issue(
                    Severity.WARNING,
                    "BPMN",
                    "root",
                    "BPMN Document",
                    "BPMN 2.0 namespace may be incorrect or missing",
                    "Ensure BPMN uses correct BPMN 2.0 namespace."
                )

    # ==================== Analysis Orchestration ====================

    def analyze(self) -> Dict[str, Any]:
        """Run complete analysis"""
        if not self.parse():
            return {}

        # Run all validations
        self.validate_namespaces()
        self.validate_service_tasks()
        self.validate_script_tasks()
        self.validate_user_tasks()
        self.validate_gateways()
        self.validate_events()
        self.validate_listeners()
        self.validate_call_activities()
        self.validate_business_rule_tasks()
        self.validate_multi_instance()
        self.validate_subprocesses()
        self.validate_input_output_mappings()
        self.validate_configurations()

        # Calculate statistics
        self.calculate_statistics()

        return {
            'file': self.bpmn_file,
            'timestamp': datetime.now().isoformat(),
            'statistics': self.statistics,
            'issues': [issue.to_dict() for issue in self.issues],
            'process_variables': sorted(list(self.process_variables))
        }

    def calculate_statistics(self):
        """Calculate analysis statistics"""
        # Count elements
        element_counts = {}
        element_types = [
            'serviceTask', 'userTask', 'scriptTask', 'businessRuleTask', 'callActivity',
            'startEvent', 'endEvent', 'intermediateCatchEvent', 'intermediateThrowEvent',
            'boundaryEvent', 'exclusiveGateway', 'parallelGateway', 'inclusiveGateway',
            'eventBasedGateway', 'subProcess'
        ]

        total_elements = 0
        for elem_type in element_types:
            count = len(self.root.findall(f'.//bpmn:{elem_type}', self.namespace))
            element_counts[elem_type] = count
            total_elements += count

        # Count issues by severity
        issue_counts = {
            'CRITICAL': len([i for i in self.issues if i.severity == Severity.CRITICAL]),
            'WARNING': len([i for i in self.issues if i.severity == Severity.WARNING]),
            'INFO': len([i for i in self.issues if i.severity == Severity.INFO])
        }

        # Count issues by category
        category_counts = {}
        for issue in self.issues:
            category_counts[issue.category] = category_counts.get(issue.category, 0) + 1

        self.statistics = {
            'total_elements': total_elements,
            'element_counts': element_counts,
            'total_issues': len(self.issues),
            'issue_counts_by_severity': issue_counts,
            'issue_counts_by_category': category_counts,
            'total_variables_detected': len(self.process_variables)
        }

    # ==================== Report Generation ====================

    def print_report(self):
        """Print analysis report to console"""
        print("\n" + "="*80)
        print("BPMN MIGRATION ANALYSIS FOR CAMUNDA 8")
        print("              NTConsult")
        print("="*80)
        print(f"\nFile: {self.bpmn_file}")
        print(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # Statistics
        print("\n" + "-"*80)
        print("STATISTICS")
        print("-"*80)
        print(f"Total BPMN Elements: {self.statistics['total_elements']}")
        print(f"Total Issues Found: {self.statistics['total_issues']}")
        print(f"  - Critical: {self.statistics['issue_counts_by_severity']['CRITICAL']}")
        print(f"  - Warning:  {self.statistics['issue_counts_by_severity']['WARNING']}")
        print(f"  - Info:     {self.statistics['issue_counts_by_severity']['INFO']}")
        print(f"Total Process Variables: {self.statistics['total_variables_detected']}")

        # Element breakdown
        print("\nElement Breakdown:")
        for elem_type, count in sorted(self.statistics['element_counts'].items()):
            if count > 0:
                print(f"  - {elem_type}: {count}")

        # Issues by category
        print("\nIssues by Category:")
        for category, count in sorted(self.statistics['issue_counts_by_category'].items()):
            print(f"  - {category}: {count}")

        # Detailed issues
        print("\n" + "-"*80)
        print("DETAILED ISSUES")
        print("-"*80)

        # Group by severity
        for severity in [Severity.CRITICAL, Severity.WARNING, Severity.INFO]:
            severity_issues = [i for i in self.issues if i.severity == severity]
            if severity_issues:
                print(f"\n{severity.value} ({len(severity_issues)}):")
                print("-" * 40)
                for issue in severity_issues:
                    print(f"\n[{issue.category}] {issue.message}")
                    print(f"  Element: {issue.element_name} (ID: {issue.element_id})")
                    if issue.details:
                        print(f"  Details: {issue.details}")

        # Process variables
        if self.process_variables:
            print("\n" + "-"*80)
            print("PROCESS VARIABLES DETECTED")
            print("-"*80)
            for var in sorted(self.process_variables):
                print(f"  - {var}")

        # Migration complexity assessment
        print("\n" + "-"*80)
        print("MIGRATION COMPLEXITY ASSESSMENT")
        print("-"*80)

        critical_count = self.statistics['issue_counts_by_severity']['CRITICAL']
        warning_count = self.statistics['issue_counts_by_severity']['WARNING']

        if critical_count == 0 and warning_count == 0:
            complexity = "LOW"
            description = "Process appears largely compatible with minimal changes needed."
        elif critical_count <= 5 and warning_count <= 10:
            complexity = "MEDIUM"
            description = "Moderate migration effort required. Focus on critical issues first."
        else:
            complexity = "HIGH"
            description = "Significant migration effort required. Consider phased approach."

        print(f"Complexity Level: {complexity}")
        print(f"Assessment: {description}")

        print("\n" + "="*80)

    def export_json(self, output_file: str):
        """Export analysis results to JSON"""
        result = self.analyze() if not self.statistics else {
            'file': self.bpmn_file,
            'timestamp': datetime.now().isoformat(),
            'statistics': self.statistics,
            'issues': [issue.to_dict() for issue in self.issues],
            'process_variables': sorted(list(self.process_variables))
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        print(f"\nJSON report exported to: {output_file}")

    def export_csv(self, output_file: str):
        """Export issues to CSV"""
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Severity', 'Category', 'Element ID', 'Element Name', 'Message', 'Details'
            ])

            for issue in self.issues:
                writer.writerow([
                    issue.severity.value,
                    issue.category,
                    issue.element_id,
                    issue.element_name,
                    issue.message,
                    issue.details
                ])

        print(f"CSV report exported to: {output_file}")

    def export_html(self, output_file: str):
        """Export analysis results to HTML"""
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>BPMN Migration Analysis</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .header {{
            background-color: #2c3e50;
            color: white;
            padding: 20px;
            border-radius: 5px;
        }}
        .section {{
            background-color: white;
            margin: 20px 0;
            padding: 20px;
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .critical {{ color: #e74c3c; font-weight: bold; }}
        .warning {{ color: #f39c12; font-weight: bold; }}
        .info {{ color: #3498db; font-weight: bold; }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 10px 0;
        }}
        th, td {{
            padding: 10px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #34495e;
            color: white;
        }}
        .issue {{
            margin: 15px 0;
            padding: 15px;
            border-left: 4px solid #ddd;
            background-color: #f9f9f9;
        }}
        .issue.critical {{ border-left-color: #e74c3c; }}
        .issue.warning {{ border-left-color: #f39c12; }}
        .issue.info {{ border-left-color: #3498db; }}
        .stats {{
            display: flex;
            justify-content: space-around;
            flex-wrap: wrap;
        }}
        .stat-box {{
            flex: 1;
            min-width: 200px;
            margin: 10px;
            padding: 15px;
            background-color: #ecf0f1;
            border-radius: 5px;
            text-align: center;
        }}
        .stat-number {{
            font-size: 2em;
            font-weight: bold;
            color: #2c3e50;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>BPMN Migration Analysis for Camunda 8</h1>
        <p>NTConsult</p>
        <p>File: {self.bpmn_file}</p>
        <p>Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>

    <div class="section">
        <h2>Statistics</h2>
        <div class="stats">
            <div class="stat-box">
                <div class="stat-number">{self.statistics['total_elements']}</div>
                <div>Total Elements</div>
            </div>
            <div class="stat-box">
                <div class="stat-number">{self.statistics['total_issues']}</div>
                <div>Total Issues</div>
            </div>
            <div class="stat-box">
                <div class="stat-number critical">{self.statistics['issue_counts_by_severity']['CRITICAL']}</div>
                <div>Critical</div>
            </div>
            <div class="stat-box">
                <div class="stat-number warning">{self.statistics['issue_counts_by_severity']['WARNING']}</div>
                <div>Warnings</div>
            </div>
            <div class="stat-box">
                <div class="stat-number info">{self.statistics['issue_counts_by_severity']['INFO']}</div>
                <div>Info</div>
            </div>
            <div class="stat-box">
                <div class="stat-number">{self.statistics['total_variables_detected']}</div>
                <div>Process Variables</div>
            </div>
        </div>
    </div>

    <div class="section">
        <h2>Element Breakdown</h2>
        <table>
            <tr><th>Element Type</th><th>Count</th></tr>
"""

        for elem_type, count in sorted(self.statistics['element_counts'].items()):
            if count > 0:
                html += f"            <tr><td>{elem_type}</td><td>{count}</td></tr>\n"

        html += """        </table>
    </div>

    <div class="section">
        <h2>Issues by Category</h2>
        <table>
            <tr><th>Category</th><th>Count</th></tr>
"""

        for category, count in sorted(self.statistics['issue_counts_by_category'].items()):
            html += f"            <tr><td>{category}</td><td>{count}</td></tr>\n"

        html += """        </table>
    </div>
"""

        # Issues by severity
        for severity in [Severity.CRITICAL, Severity.WARNING, Severity.INFO]:
            severity_issues = [i for i in self.issues if i.severity == severity]
            if severity_issues:
                severity_class = severity.value.lower()
                html += f"""    <div class="section">
        <h2 class="{severity_class}">{severity.value} Issues ({len(severity_issues)})</h2>
"""
                for issue in severity_issues:
                    html += f"""        <div class="issue {severity_class}">
            <strong>[{issue.category}] {issue.message}</strong><br>
            <em>Element: {issue.element_name} (ID: {issue.element_id})</em><br>
"""
                    if issue.details:
                        html += f"            <p>{issue.details}</p>\n"
                    html += "        </div>\n"

                html += "    </div>\n"

        # Process variables
        if self.process_variables:
            html += """    <div class="section">
        <h2>Process Variables Detected</h2>
        <ul>
"""
            for var in sorted(self.process_variables):
                html += f"            <li>{var}</li>\n"
            html += """        </ul>
    </div>
"""

        html += """</body>
</html>"""

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html)

        print(f"HTML report exported to: {output_file}")


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("Usage: python bpmn_migration.py <bpmn_file> [options]")
        print("\nOptions:")
        print("  --json <file>    Export results to JSON")
        print("  --csv <file>     Export issues to CSV")
        print("  --html <file>    Export report to HTML")
        print("\nExample:")
        print("  python bpmn_migration.py process.bpmn --json report.json --html report.html")
        sys.exit(1)

    bpmn_file = sys.argv[1]

    # Parse options
    export_json = None
    export_csv = None
    export_html = None

    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == '--json' and i + 1 < len(sys.argv):
            export_json = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == '--csv' and i + 1 < len(sys.argv):
            export_csv = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == '--html' and i + 1 < len(sys.argv):
            export_html = sys.argv[i + 1]
            i += 2
        else:
            i += 1

    # Run analysis
    analyzer = BPMNAnalyzer(bpmn_file)
    analyzer.analyze()
    analyzer.print_report()

    # Export reports
    if export_json:
        analyzer.export_json(export_json)

    if export_csv:
        analyzer.export_csv(export_csv)

    if export_html:
        analyzer.export_html(export_html)


if __name__ == "__main__":
    main()
