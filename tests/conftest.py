import sys
from unittest.mock import MagicMock

# Global D-Bus mocking for tests when sdbus is not installed
try:
    import sdbus
except ImportError:
    mock_sdbus = MagicMock()
    
    async def dummy_async(*args, **kwargs):
        pass

    class DummyDbusInterface:
        def __init__(self, *args, **kwargs):
            pass
        def export_to_dbus(self, *args, **kwargs):
            pass
        @classmethod
        def __init_subclass__(cls, *args, **kwargs):
            pass
            
    mock_sdbus.DbusInterfaceCommonAsync = DummyDbusInterface
    mock_sdbus.DbusInterfaceCommon = DummyDbusInterface
    mock_sdbus.dbus_method_async = lambda *args, **kwargs: lambda func: func
    mock_sdbus.dbus_signal_async = lambda *args, **kwargs: lambda func: func
    mock_sdbus.dbus_method = lambda *args, **kwargs: lambda func: func
    mock_sdbus.request_default_bus_name_async = dummy_async
    sys.modules['sdbus'] = mock_sdbus
