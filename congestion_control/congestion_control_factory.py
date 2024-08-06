# congestion_control/congestion_control_factory.py
from __future__ import annotations

from typing import TYPE_CHECKING

from utils.logging import setup_class_logger

from .built_in_congestion_control import BALIA, BBR, CUBIC, OLIA, WVegas

if TYPE_CHECKING:
    import logging
    from typing import ClassVar


@setup_class_logger
class CongestionControlFactory:
    __logger: ClassVar[logging.Logger]

    @staticmethod
    def create_congestion_control(cc_name, client, server):
        if cc_name == "cubic":
            return CUBIC(client=client, server=server)
        elif cc_name == "olia":
            return OLIA(client=client, server=server)
        elif cc_name == "bbr":
            return BBR(client=client, server=server)
        elif cc_name == "balia":
            return BALIA(client=client, server=server)
        elif cc_name == "wvegas":
            return WVegas(client=client, server=server)
        else:
            raise ValueError(f"Unsupported congestion control: {cc_name}")

    @staticmethod
    def create_congestion_controls(cc_names, client, server):
        return [
            CongestionControlFactory.create_congestion_control(cc_name, client, server)
            for cc_name in cc_names
        ]
