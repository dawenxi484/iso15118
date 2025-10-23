import asyncio
import logging
import sys

from iso15118.evcc import Config, EVCCHandler
from iso15118.evcc.controller.simulator import SimEVController
from iso15118.evcc.evcc_config import load_from_file
from iso15118.shared.exificient_exi_codec import ExificientEXICodec

logger = logging.getLogger(__name__)


async def main():
    """
    Entrypoint function that starts the ISO 15118 code running on
    the EVCC (EV Communication Controller)
    """
    config = Config()
    config.load_envs()
    if len(sys.argv) > 1:
        ev_config_file_path = sys.argv[1]
        if ev_config_file_path:
            config.ev_config_file_path = ev_config_file_path
    evcc_config = await load_from_file(config.ev_config_file_path)
    await EVCCHandler(
        evcc_config=evcc_config,
        interface_index=config.interface_index,
        exi_codec=ExificientEXICodec(),
        ev_controller=SimEVController(evcc_config),
    ).start()


def run():
    try:
        if sys.platform == 'win32':
            # 在 Windows 上使用 Selector 事件循环
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.debug("EVCC program terminated manually")


if __name__ == "__main__":
    # windows获取接口索引值
    # netsh interface ipv6 show interface
    run()
