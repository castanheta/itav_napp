import asyncio

from opencapif_sdk import capif_invoker_connector, service_discoverer

from app.utils.logger import get_app_logger

log = get_app_logger(__name__)


class CAPIFClient:

    def __init__(self, config_file: str) -> None:
        self._config_file = config_file
        self._token: str | None = None
        self._connector: capif_invoker_connector | None = None
        self._discoverer: service_discoverer | None = None

    def get_token(self) -> str | None:
        return self._token

    async def onboard(self) -> None:
    
        log.info("CAPIF: starting invoker onboarding")

        config_file = self._config_file

        def _do_onboard():
            connector = capif_invoker_connector(config_file=config_file)
            connector.onboard_invoker()
            discoverer = service_discoverer(config_file=config_file)
            discoverer.discover()
            return connector, discoverer

        self._connector, self._discoverer = await asyncio.to_thread(_do_onboard)
        log.info("CAPIF: invoker onboarding complete")

    async def offboard(self) -> None:
        
        log.info("CAPIF: starting invoker offboarding")
        if self._connector is None:
            log.warning("CAPIF: offboard called but connector is not initialised — skipping")
            return

        connector = self._connector

        def _do_offboard():
            connector.offboard_invoker()

        try:
            await asyncio.to_thread(_do_offboard)
            log.info("CAPIF: invoker offboarding complete")
        except Exception as exc:
            log.error("CAPIF: offboarding failed (best-effort, continuing shutdown): %s", exc)

    async def refresh_token(self) -> None:
        discoverer = self._discoverer

        def _do_refresh():
            discoverer.discover()
            discoverer.get_tokens()
            return discoverer.token

        token = await asyncio.to_thread(_do_refresh)
        self._token = token
        log.info("CAPIF: token refreshed successfully")

    async def run_token_refresh_loop(self, interval_seconds: int = 300) -> None:
        while True:
            try:
                await asyncio.sleep(interval_seconds)

                log.info("CAPIF: refreshing token")
                await self.refresh_token()

            except asyncio.CancelledError:
                log.info("CAPIF: token refresh loop cancelled — exiting")
                return

            except Exception as exc:
                log.error(
                    "CAPIF: token refresh failed, keeping stale token. "
                    "Will retry in %ds. Error: %s",
                    interval_seconds,
                    exc,
                )
