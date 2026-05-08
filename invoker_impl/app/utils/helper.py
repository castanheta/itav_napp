'''helper class to build and send http request'''
import requests
from requests.exceptions import Timeout, HTTPError, RequestException
from fastapi import HTTPException

from app.schemas.location_fetch import DurationSec
from app.utils.exceptions import TokenFileError
from app.schemas.location_fetch import MonitoringEventSubscriptionRequest, MonitoringType, LocationType
from app.utils.logger import get_app_logger
from app.dependencies import get_task_registry
from app.config import get_settings

task_registry = get_task_registry()

settings = get_settings()

log = get_app_logger(__name__)

def build_monitoring_event_subscription(xapp_payload_request: dict, current_loc_enabled: bool) -> MonitoringEventSubscriptionRequest:
    """Builds a MonitoringEventSubscriptionRequest from the given xApp payload."""

    log.info("Building monitoring event subscription request with current_loc_enabled=%s", current_loc_enabled)
    

    if current_loc_enabled:
        log.info("Current location reporting is enabled.")
        max_num_reports = settings.current_loc_max_num_reports
        rep_period = settings.current_loc_rep_period
        log.info("maxNumReports: %s", max_num_reports)
        log.info("repPeriod: %s", rep_period)
        try:
            obj = MonitoringEventSubscriptionRequest(
                    #msisdn=xapp_payload_request["msisdn"].lstrip("+"),
                    msisdn=xapp_payload_request["msisdn"],
                    notificationDestination=settings.notification_destination,
                    monitoringType=MonitoringType.LOCATION_REPORTING,
                    locationType=LocationType.CURRENT_LOCATION,
                    maximumNumberOfReports=max_num_reports,
                    repPeriod=DurationSec(duration=rep_period)
                    )
            #log.info("Constructed request: %s", obj)
            return obj
        except Exception as exc:
            log.error("Error constructing MonitoringEventSubscriptionRequest: %s", exc)
            raise
    return MonitoringEventSubscriptionRequest(
        msisdn=xapp_payload_request["msisdn"].lstrip("+"),
        notificationDestination=xapp_payload_request["notificationDestination"],
        monitoringType=MonitoringType.LOCATION_REPORTING,
        locationType=LocationType.LAST_KNOWN
    )

def extract_callback_url(xapp_payload_request: dict) -> str:
    """Extracts the callback URL from the given xApp payload."""

    log.info("Extracting callback URL from payload")

    return xapp_payload_request["notificationDestination"]

def _read_access_token_from_file(file_path: str) -> str:
    """
    Reads an access token from a specified file.

    Args:
        file_path (str): The path to the file containing the access token.

    Returns:
        str: The access token read from the file.

    Raises:
        TokenFileError: If the file is not found or an I/O error occurs while reading the file.
    """
    try:
        with open(file_path, "r", encoding='utf-8') as file:
            token = file.read().strip()
            return token
    except FileNotFoundError as exc:
        raise TokenFileError(f"Token file not found: {file_path}") from exc
    except IOError as exc:
        raise TokenFileError(f"Error reading token file: {exc}") from exc
        
async def build_send_http_request(url : str, jwt_token: str | None, payload: dict, task_id :str) -> requests.Response:
    """
    Asynchronously builds and sends an HTTP POST request to the specified URL with an 
    authorization header.

    Args:
        url (str): The endpoint URL to send the POST request to.
        access_token_path (str): The path to the file containing the access token.

    Returns:
        None

    Side Effects:
        Prints the status code and JSON response of the HTTP request to the console.

    Raises:
        Any exceptions raised by httpx or file reading operations.
    """
    if jwt_token is not None:
        #token = _read_access_token_from_file(access_token_path)
        token = jwt_token

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }
    else:
        headers = {}

    try:
            log.info("Sending POST request to %s with payload: %s and headers: %s",url,payload,headers)

            response = requests.post(url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            
            log.info("Status Code: %s",response.status_code)
            log.info("Success: %s", response.json())

            return response
    except Timeout:
        log.error("Request timed out.")
        task_registry[task_id].cancel()
    except HTTPError as exc:
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=exc.response.text
        ) from exc
    except RequestException as exc:
        log.error("An error occurred while requesting %s:%s",exc.request.url,exc)
        task_registry[task_id].cancel()