"""Home automation and scheduled triggers (optional config under JARVIS_HOME/config)."""

from jarvis.integrations.automation import Automation
from jarvis.integrations.smarthome import SmartHome

__all__ = ("Automation", "SmartHome")
