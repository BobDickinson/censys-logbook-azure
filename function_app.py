# An Azure Function to send Censys Logbook data to Azure Monitor based on a timer trigger

# built-ins
from datetime import datetime, timedelta
import logging
import os
import json
import hashlib
import hmac
import base64
import uuid

# General deps
import requests

# Azure Functions deps
import azure.functions as func
from azure.core.exceptions import ResourceNotFoundError

# Azure KeyVault deps
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential

# Censys ASM deps
from censys.asm import Logbook
from censys.asm import Risks

app = func.FunctionApp()

@app.function_name(name="CensysLogbookSync")
@app.schedule(schedule="%CENSYS_LOGBOOK_SYNC_INTERVAL%", arg_name="mytimer", run_on_startup=False) 
def censys_logbook_sync(mytimer: func.TimerRequest) -> None:
    
    client = get_keyvault_client_quiet()

    start_after_raw_value = get_secret_quiet(client, 'CensysLogbookStartAfter', 0)
    start = None
    # get_cursor start arg can be either an event ID or a date.  We'll set it depending on what kind
    # of value is configured
    try:
        start = int(start_after_raw_value) + 1 # Start at the next event ID (after the last one we processed)
        logging.info('Processing Logbook events, starting with ID: {}'.format(start))
    except ValueError:
        # If not int, then it's a string we'll use as a date filter
        start = start_after_raw_value
        logging.info('Processing Logbook events, starting from: {}'.format(start))
               
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
        cursor = logbook.get_cursor(start, filters=["HOST"])
        events = logbook.get_events(cursor)
    except Exception as e:
        # The Censys Python SDK can thrown many specific Censys expceptions, and it's possible that other
        # exceptions could also be thrown.  We'll catch everything here and return state for retry.
        logging.error("Exception getting Censys Logbook events: {}".format(e))
        return

    # Build the object to send to Azure Log Analytics
    event_objects = [] 
    total_count = 0
    after_id = None
    for event in events:
        event_object = {
            "Event_ID": event['id'],
            "Event_type": event['type'],
            "Operation": event['operation'],
            "IP_Address": event['entity']['ipAddress'],
            "timestamp": event['timestamp']
        }
        event_objects.append(event_object)
        after_id = event['id']

        if len(event_objects) >= limit:
            logging.info(f"Sending {len(event_objects)} Logbook events to Azure Monitor, next batch will start after logbook ID: {event_objects[len(event_objects)-1]['Event_ID']}")
            if send_events_to_azure_monitor(event_objects, workspace_id, shared_key, log_type):
                total_count += len(event_objects)
                event_objects = []
                # Serialize next_event_id to KeyVault (sucessfully posted to Azure Monitor)
                set_secret_quiet(client, 'CensysLogbookStartAfter', after_id)
            else:
                return False
            
    if event_objects:
        logging.info(f"Sending {len(event_objects)} Logbook events to Azure Monitor, next batch will start after logbook ID: {event_objects[len(event_objects)-1]['Event_ID']}")
        if send_events_to_azure_monitor(event_objects, workspace_id, shared_key, log_type):
            total_count += len(event_objects)
            # Serialize next_event_id to KeyVault (sucessfully posted to Azure Monitor)
            set_secret_quiet(client, 'CensysLogbookStartAfter', after_id)
        else:
            return False
        
    if (total_count == 0):
        logging.info('No new Logbook events found')
    else:
        logging.info('Found {} new Logbook events, forwarded to Azure Monitor, last event processed was logbook ID: {}'.format(total_count, after_id))
    return
    

@app.function_name(name="CensysRisksSync")
@app.schedule(schedule="%CENSYS_RISKS_SYNC_INTERVAL%", arg_name="mytimer", run_on_startup=False)
def censys_risks_sync(mytimer: func.TimerRequest) -> None:
    censys_asm_api_key = os.environ.get('CENSYS_ASM_API_KEY')

    client = get_keyvault_client_quiet()

    default_limit = 500
    try:
        limit = int(os.environ.get('CENSYS_RISK_EVENTS_LIMIT', default_limit))
    except ValueError:
        logging.error("Invalid value for CENSYS_RISK_EVENTS_LIMIT. Using default value of {}.".format(default_limit))
        limit = default_limit

    start_after_raw_value = get_secret_quiet(client, 'CensysRisksStartAfter', 0)
    start_date = None
    after_id = None
    try:
        after_id = int(start_after_raw_value)
    except ValueError:
        # If not int, then it's a string we'll use as a date filter
        start_date = start_after_raw_value
 
    # get_risk_events args can use either start_date or after_id the first time through, depending on what was
    # configured.  After the first call, we'll use after_id from the last event in the previous call results.
    #
    if (start_date):
        args = {"start": start_date, "limit": limit}
        logging.info('Processing risk events, starting from: {}'.format(start_date))
    else:
        args = {"after_id": after_id, "limit": limit}
        logging.info('Processing risk events, starting after ID: {}'.format(after_id))
               
    # Get environment variables
    censys_asm_api_key = os.environ.get('CENSYS_ASM_API_KEY')
    workspace_id = os.environ.get('AZURE_LOG_ANALYTICS_WORKSPACE_ID')
    shared_key = os.environ.get('AZURE_LOG_ANALYTICS_SHARED_KEY')
    log_type = os.environ.get('AZURE_LOG_ANALYTICS_LOG_TYPE_CENSYS_RISKS', 'Censys_Risks_CL')

    risks = Risks(censys_asm_api_key)
    count = 0

    def process_risk_events(risk_events):
        nonlocal count
        count += len(risk_events)

        # The risk events contain a combination of risk instance and risk type events.  We're only going
        # to process the risk instance events, and we only want to process the relevant attributes (these
        # will the base of the event object we'll send to Azure Monitor after we hydrate them).
        #
        instance_events = [
            {
                "Risk Event ID": event.get("id"),
                "Risk Event Operation": event.get("op"),
                "Risk Event Source": event.get("src"),
                "Risk Event Source ID": event.get("srcID"),
                "Risk Instance ID": event.get("riskID"),
                "timestamp": event.get("ts"),
            }            
            for event in risk_events
            if "riskID" in event
        ]

        # For any given batch of risk instance events, there will typically be many events referring to the
        # same risk instances.  We'll de-duplicate the risk instance IDs and then build a query from that set
        # to fetch the set of risk instances that we'll need to hydrate these events (we don't want to be getting
        # individual risk instances at this scale).
        #
        unique_risk_ids = list(set(event['Risk Instance ID'] for event in instance_events))
        filter = {
            "fields": ["id","context","typeID","displayName","severity","status","firstComputedAt","lastComputedAt"],
            "query": { "or": [ ] }
        }
        for risk_id in unique_risk_ids:
            filter["query"]["or"].append(["id", "=", risk_id])
        instances = risks.search_risk_instances(filter)

        # Build a dictionary of returned risk instances keyed by "id" (risk instance ID), then iterate through 
        # the risk instance events and hydrate them with the risk instance details.
        #
        instance_dict = {item['id']: item for item in instances["risks"]}
        for instance_event in instance_events:
            instance = instance_dict.get(instance_event["Risk Instance ID"])
            if instance: # Some events (especially older ones) may not have a risk instance - we just won't hydrate those
                # Hydrate the risk instance event with the risk instance details
                instance_event["Risk Type"] = instance.get("typeID")
                instance_event["Display Name"] = instance.get("displayName")
                instance_event["Severity"] = instance.get("severity")
                instance_event["Status"] = instance.get("status")
                instance_event["First Seen"] = instance.get("firstComputedAt")
                instance_event["Last Seen"] = instance.get("lastComputedAt")
                asset_label, impacted_asset, asset_path = get_imacted_asset(instance)
                instance_event["Impacted Asset"] = impacted_asset
                instance_event["Impacted Asset Label"] = asset_label
                instance_event["Link to Risk"] = asset_path

        # Return the set of hydrated events for Azure Monitor and the new "after_id" to use for the next call
        return instance_events, risk_events[len(risk_events)-1]["id"]

    sent_to_azure = 0
    while True:
        risk_event_results = risks.get_risk_events(**args)
        if (risk_event_results["total"] > 0):
            events, after_id = process_risk_events(risk_event_results["events"])
            args = {"after_id": after_id, "limit": limit}
            logging.info(f"Sending {len(events)} risk events to Azure Monitor, next batch will start after event ID: {after_id}")
            if send_events_to_azure_monitor(events, workspace_id, shared_key, log_type):
                sent_to_azure += len(events)
                # Serialize after_id to KeyVault (sucessfully posted to Azure Monitor)
                set_secret_quiet(client, 'CensysRisksStartAfter', after_id)
            else:
                return False
        if (risk_event_results["endOfEvents"]):
            break
    
    if (count == 0):
        logging.info('No new risk events found')
    else:
        logging.info('Found {} new risk events, forwarded {} qualifying risk instance events to Azure Monitor, last risk event processed was: {}'.format(count, sent_to_azure, after_id))
    return


def get_imacted_asset(risk_instance):
    asset_type_map = { 'host': 'hosts', 'cert': 'certificates', 'domain': 'domains', 'bucket': 'storage-bucket', 'webentity': 'web-entities', 'unknown': 'unknown' }
    base_uri = 'https://app.censys.io'
    asset_type = asset_type_map[risk_instance.get("context", {}).get("type", "unknown")]
    if asset_type == 'hosts':
        asset_label = risk_instance['context']['ip']
        impacted_asset = f"Host: {risk_instance['context']['ip']}"
        asset_path = f"{base_uri}/{asset_type}/{risk_instance['context']['ip']}/risks"
    elif asset_type == 'web-entities':
        asset_label = f"{risk_instance['context']['name']}:{risk_instance['context']['port']}"
        impacted_asset = f"Web Entity: {risk_instance['context']['name']}:#{risk_instance['context']['port']}"
        asset_path = f"{base_uri}/{asset_type}/{risk_instance['context']['name']}%3A#{risk_instance['context']['port']}/risks"
    elif asset_type == 'domains':
        asset_label = risk_instance['context']['domain']
        impacted_asset = f"Domain: {risk_instance['context']['domain']}"
        asset_path = f"{base_uri}/{asset_type}/{risk_instance['context']['domain']}/risks"
    elif asset_type == 'certificates':
        asset_label = risk_instance['context']['sha256']
        impacted_asset = f"Certificate: {risk_instance['context']['sha256']}"
        asset_path = f"{base_uri}/{asset_type}/{risk_instance['context']['sha256']}/risks"
    elif asset_type == 'storage-bucket':
        asset_label = risk_instance['context']['cri']
        impacted_asset = f"Bucket: {risk_instance['context']['cri']}"
        asset_path = f"{base_uri}/{asset_type}/{risk_instance['context']['cri']}/risks"
    else:
        asset_label = ''
        impacted_asset = ''
        asset_path = ''

    return asset_label, impacted_asset, asset_path


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
    rfc1123date = datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')
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
