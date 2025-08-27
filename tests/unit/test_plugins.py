import agent.plugins
from agent.core import discover_plugins


def test_plugins():
    plugins = discover_plugins(agent.plugins)

    assert len(plugins) == 1
