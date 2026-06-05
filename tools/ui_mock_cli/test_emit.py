import inspect
from sdbus.dbus_proxy_async_signal import DbusLocalSignalAsync

print(inspect.signature(DbusLocalSignalAsync.emit))
