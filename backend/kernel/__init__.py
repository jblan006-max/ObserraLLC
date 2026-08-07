"""Obserra shared cybersecurity kernel — service singletons + facade."""
from kernel.manifest import SUBSYSTEMS
from kernel.notification import NotificationEngine
from kernel.policy import PolicyEngine
from kernel.workflow import WorkflowEngine

notifications = NotificationEngine()
policies = PolicyEngine()
workflows = WorkflowEngine()

__all__ = ["SUBSYSTEMS", "notifications", "policies", "workflows"]
