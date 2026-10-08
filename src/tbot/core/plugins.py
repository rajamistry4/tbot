"""Explicit allowlist: configuration cannot import arbitrary Python code."""
from .interfaces import Broker, DataProvider, ReportGenerator, RiskManager, Strategy, Trainer

CONTRACTS = {
    "data": DataProvider, "strategy": Strategy, "broker": Broker,
    "risk": RiskManager, "report": ReportGenerator, "trainer": Trainer,
}


class PluginRegistry:
    def __init__(self):
        self._plugins = {}

    def register(self, category: str, name: str, plugin_class: type) -> None:
        if category not in CONTRACTS:
            raise ValueError(f"Unknown plugin category: {category}")
        if not issubclass(plugin_class, CONTRACTS[category]):
            raise TypeError(f"{name} must implement {CONTRACTS[category].__name__}")
        key = (category, name)
        if key in self._plugins:
            raise ValueError(f"Plugin already registered: {category}/{name}")
        self._plugins[key] = plugin_class

    def create(self, category: str, settings: dict):
        settings = dict(settings)
        name = settings.pop("name")
        try:
            plugin_class = self._plugins[(category, name)]
        except KeyError as error:
            raise ValueError(f"Unknown plugin: {category}/{name}") from error
        return plugin_class(**settings)
