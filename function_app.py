# An Azure Function to send Censys Logbook data to Azure Monitor based on a timer trigger

# built-ins
from datetime import datetime, timedelta
import logging
import os
import json
import requests
import hashlib
import hmac
import base64
import uuid

# Azure Functions deps
import azure.functions as func
from azure.core.exceptions import ResourceNotFoundError

# Azure KeyVault deps
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential

# Censys ASM deps
from censys.asm import Logbook

app = func.FunctionApp()

@app.function_name(name="CensysLogbookSync")
@app.schedule(schedule="0 0 * * * *", arg_name="mytimer", run_on_startup=False) 
def censys_logbook_sync(mytimer: func.TimerRequest) -> None:
    '''
    client = get_keyvault_client_quiet()

    next_event_raw_value = get_secret_quiet(client, 'CENSYS-LOGBOOK-NEXT-EVENT', 1)
    next_event_id = None
    try:
        next_event_id = int(next_event_raw_value)
    except ValueError:
        # If not int, then it's a string we'll use as a date filter
        next_event_id = next_event_raw_value
    logging.info('Processing Logbook events, starting with {}'.format(next_event_id))
               
    # Get environment variables
    censys_asm_api_key = os.environ.get('CENSYS_ASM_API_KEY')
    workspace_id = os.environ.get('AZURE_LOG_ANALYTICS_WORKSPACE_ID')
    shared_key = os.environ.get('AZURE_LOG_ANALYTICS_SHARED_KEY')
    log_type = os.environ.get('AZURE_LOG_ANALYTICS_LOG_TYPE_CENSYS_LOGBOOK', 'Censys_Logbook_CL')

    default_limit = 500
    try:
        limit = int(os.environ.get('AZURE_EVENT_POST_LIMIT', default_limit))
    except ValueError:
        logging.error("Invalid value for AZURE_EVENT_POST_LIMIT. Using default value of {}.".format(default_limit))
        limit = default_limit

    # Get Logbook events from Censys ASM
    logbook = Logbook(censys_asm_api_key)

    events = None
    try:
        cursor = logbook.get_cursor(next_event_id, filters=["HOST"])
        events = logbook.get_events(cursor)
    except Exception as e:
        # The Censys Python SDK can thrown many specific Censys expceptions, and it's possible that other
        # exceptions could also be thrown.  We'll catch everything here and return state for retry.
        logging.error("Exception getting Censys Logbook events: {}".format(e))
        return

    # Build the object to send to Azure Log Analytics
    event_objects = [] 
    total_count = 0
    for event in events:
        event_object = {
            "Event_ID": event['id'],
            "Event_type": event['type'],
            "Operation": event['operation'],
            "IP_Address": event['entity']['ipAddress'],
            "timestamp": event['timestamp']
        }
        event_objects.append(event_object)
        next_event_id = event['id'] + 1

        if len(event_objects) >= limit:
            if send_events_to_azure_monitor(event_objects, workspace_id, shared_key, log_type):
                total_count += len(event_objects)
                event_objects = []
                # Serialize next_event_id to KeyVault (sucessfully posted to Azure Monitor)
                set_secret_quiet(client, 'CENSYS-LOGBOOK-NEXT-EVENT', next_event_id)
            else:
                return False
            
    if event_objects:
        if send_events_to_azure_monitor(event_objects, workspace_id, shared_key, log_type):
            total_count += len(event_objects)
            # Serialize next_event_id to KeyVault (sucessfully posted to Azure Monitor)
            set_secret_quiet(client, 'CENSYS-LOGBOOK-NEXT-EVENT', next_event_id)
        else:
            return False

    logging.info('Processed {} Logbook events, next event will be logbook ID: {}'.format(total_count, next_event_id))
    return
    '''
    logging.info("Not implemented yet")
    

@app.function_name(name="CensysRisksSync")
@app.schedule(schedule="0 0 * * * *", arg_name="mytimer", run_on_startup=False) 
def censys_risks_sync(mytimer: func.TimerRequest) -> None:

    logging.info("Not implemented yet")

'''
def get_keyvault_client_quiet():
    keyVaultName = os.environ.get("KEYVAULT_NAME")
    KVUri = f"https://{keyVaultName}.vault.azure.net"

    azure_logger = logging.getLogger('azure')
    azure_logger.setLevel(logging.WARNING)

    credential = DefaultAzureCredential()
    client = SecretClient(vault_url=KVUri, credential=credential)

    azure_logger.setLevel(logging.INFO)

    return client


def get_secret_quiet(client, key, default_value=None):
    azure_logger = logging.getLogger('azure')
    azure_logger.setLevel(logging.WARNING)

    retval = default_value
    try:
        retval_raw = client.get_secret(key)
        retval = retval_raw.value
    except ResourceNotFoundError:
        pass

    azure_logger.setLevel(logging.INFO)

    return retval


def set_secret_quiet(client, key, value):
    azure_logger = logging.getLogger('azure')
    azure_logger.setLevel(logging.WARNING)

    client.set_secret(key, value)

    azure_logger.setLevel(logging.INFO)


def send_events_to_azure_monitor(events, workspace_id, shared_key, log_type):
    body = json.dumps(events)
    request_params = build_request(workspace_id, shared_key, body, log_type)

    try:
        # Send the object to Azure Log Analytics
        logging.info(f"Sending {len(events)} events to Azure Monitor, next batch will start at logbook ID: {events[len(events)-1]['Event_ID']+1}")
        response = requests.post(request_params['url'], data=request_params['data'], headers=request_params['headers'])
        response.raise_for_status()  # Raises a HTTPError if the status is 4xx, 5xx
    except (requests.exceptions.RequestException, requests.exceptions.HTTPError) as e:
        logging.error(f"Post to Azure Monitor failed: {e}")
        return False
    
    return True


# Build the API signature for the Azure Log Analytics Data Collector
def build_signature(workspace_id, shared_key, date, content_length, method, content_type, resource):
    x_headers = 'x-ms-date:' + date
    string_to_hash = method + "\n" + str(content_length) + "\n" + content_type + "\n" + x_headers + "\n" + resource
    bytes_to_hash = bytes(string_to_hash, encoding="utf-8")  
    decoded_key = base64.b64decode(shared_key)
    encoded_hash = base64.b64encode(hmac.new(decoded_key, bytes_to_hash, digestmod=hashlib.sha256).digest()).decode()
    authorization = "SharedKey {}:{}".format(workspace_id,encoded_hash)
    return authorization


# Build the API call for the Azure Log Analytics Data Collector    
def build_request(workspace_id, shared_key, body, log_type):
    method = 'POST'
    content_type = 'application/json'
    resource = '/api/logs'
    rfc1123date = datetime.datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')
    content_length = len(body)
    signature = build_signature(workspace_id, shared_key, rfc1123date, content_length, method, content_type, resource)
    url = 'https://' + workspace_id + '.ods.opinsights.azure.com' + resource + '?api-version=2016-04-01'

    headers = {
        'content-type': content_type,
        'Authorization': signature,
        'Log-Type': log_type,
        'x-ms-date': rfc1123date,
        'time-generated-field': 'timestamp'
    }

    return {"url": url, "headers": headers, "data": body}
'''
