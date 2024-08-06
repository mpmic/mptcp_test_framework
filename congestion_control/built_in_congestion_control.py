# congestion_control/built_in_congestion_control.py
from __future__ import annotations

from typing import TYPE_CHECKING

from utils.logging import setup_class_logger

from .icongestion_control import BaseCongestionControl

if TYPE_CHECKING:
    import logging
    from typing import ClassVar


@setup_class_logger
class CUBIC(BaseCongestionControl):
    __logger: ClassVar[logging.Logger]

    def __init__(self, client, server):
        super().__init__(name="cubic", client=client, server=server)

    def load(self):
        pass

    def unload(self):
        pass


@setup_class_logger
class OLIA(BaseCongestionControl):
    __logger: ClassVar[logging.Logger]

    def __init__(self, client, server):
        super().__init__(name="olia", client=client, server=server)

    def load(self):
        pass

    def unload(self):
        pass


@setup_class_logger
class BBR(BaseCongestionControl):
    __logger: ClassVar[logging.Logger]

    def __init__(self, client, server):
        super().__init__(name="bbr", client=client, server=server)

    def load(self):
        pass

    def unload(self):
        pass


@setup_class_logger
class BALIA(BaseCongestionControl):
    __logger: ClassVar[logging.Logger]

    def __init__(self, client, server):
        super().__init__(name="balia", client=client, server=server)


@setup_class_logger
class WVegas(BaseCongestionControl):
    __logger: ClassVar[logging.Logger]

    def __init__(self, client, server):
        super().__init__(name="wvegas", client=client, server=server)
