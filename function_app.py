# Send Censys Logbook data to Azure Monitor using the Data Collector API using a Diurable Azure Function

# Azure Functions deps
import logging
import os
import azure.functions as func
import azure.durable_functions as df
import uuid
from datetime import datetime, timedelta

# Azure Monitor Data Collector deps (built-in)
import json
import requests
import datetime
import hashlib
import hmac
import base64

# Censys ASM deps
from censys.asm import Logbook

myApp = df.DFApp(http_auth_level=func.AuthLevel.ANONYMOUS)

# The orchestrator startup fn gets called once at startup in the lifetime of this long-running
# Durable Azure Function, which implements the Eternal Orchestration pattern. 
#
# It determines the initial state to be passed in to the first execution of the orchestrator
# function, then calls the orchestrator function with that state.
#
# I can't figure out how to make a "run once at startup" trigger any other way, so this is a timer
# trigger that will not execute until Jan 1, 2030 (so it should execute at startup only).  There
# should be a better way to do this, but I can't find it.
#
@myApp.schedule(schedule="0 0 0 1 Jan Tue", arg_name="mytimer", run_on_startup=True) # Jan 1, 2030
@myApp.durable_client_input(client_name="client")
async def startup_fn(mytimer: func.TimerRequest, client) -> None:
    # start the orchestrator
    logging.info("Starting orchestrator")
    initial_state = {
        "last_event_id": os.environ.get('CENSYS_LOGBOOK_LAST_EVENT_ID', 0), # Optional override
        "more_events": True,
        "failed": False,
        "retry_minutes": 0
        }
    await client.start_new('orchestrator_fn', uuid.uuid4(), initial_state)


# Orchestrator
@myApp.orchestration_trigger(context_name="context")
def orchestrator_fn(context):
    # do the orchestration
    state = context.get_input()
    logging.info("state: " + json.dumps(context.get_input()))

    max_interval_minutes = 60
    if state['failed']:
        # The previous call to activity_fn failed, so we'll compute a back-off interval, wait, and retry
        if state['retry_minutes'] == 0:
            state['retry_minutes'] = 1 # First retry is 1 minute
            logging.info(f"Failure, first retry, waiting {state['retry_minutes']} minute")
        else:
            state['retry_minutes'] = state['retry_minutes'] * 2 # Double the retry interval each time
            if state['retry_minutes'] > max_interval_minutes:
                state['retry_minutes'] = max_interval_minutes
                logging.info(f"Failure, waiting max interval of {state['retry_minutes']} minutes")
            else:
                logging.info(f"Failure, doubling retry and waiting {state['retry_minutes']} minutes")
        backoff_interval = context.current_utc_datetime + timedelta(minutes=state['retry_minutes'])
        yield context.create_timer(backoff_interval)    
    elif not state['more_events']:
        # Last call to activity_fn succeeded, but no more events to process, wait max interval
        logging.info(f"No more events to process, waiting {max_interval_minutes} minutes")
        next_interval = context.current_utc_datetime + timedelta(minutes=max_interval_minutes)
        yield context.create_timer(next_interval)

    # Process more events
    logging.info("calling activity_fn")
    state['failed'] = False
    state = yield context.call_activity("activity_fn", state)
    if not state['failed']:
        state['retry_minutes'] = 0 # Reset retry interval
    logging.info("returned state {}".format(state))        

    # Post the state back to this orchestrator (we'll enter this function again, but with
    # no state other than the state we're setting here, allowing us to do this forever).
    context.continue_as_new(state)


# Activity
@myApp.activity_trigger(input_name="state")
def activity_fn(state):
    logging.info('Processing Logbook events, state {}'.format(state))

    default_limit = 500
    last_event_id = state['last_event_id']

    # Get environment variables
    censys_asm_api_key = os.environ.get('CENSYS_ASM_API_KEY')
    workspace_id = os.environ.get('AZURE_LOG_ANALYTICS_WORKSPACE_ID')
    shared_key = os.environ.get('AZURE_LOG_ANALYTICS_SHARED_KEY')
    log_type = os.environ.get('AZURE_LOG_ANALYTICS_LOG_TYPE', 'Censys_Logbook_CL')
    try:
        limit = int(os.environ.get('CENSYS_LOGBOOK_LIMIT', default_limit))
    except ValueError:
        logging.error("Invalid value for CENSYS_LOGBOOK_LIMIT. Using default value of {}.".format(default_limit))
        limit = default_limit

    # Get Logbook events from Censys ASM
    logbook = Logbook(censys_asm_api_key)
    events = None
    try:
        cursor = logbook.get_cursor(last_event_id, filters=["HOST"])
        events = logbook.get_events(cursor)
    except Exception as e:
        # The Censys Python SDK can thrown many specific Censys expceptions, and it's possible that other
        # exceptions could also be thrown.  We'll catch everything here and return state for retry.
        logging.error("Exception getting Censys Logbook events: {}".format(e))
        state['failed'] = True
        return state

    # Build the object to send to Azure Log Analytics
    more_events = False
    event_objects = [] 
    for event in events:
        if len(event_objects) >= limit:
            more_events = True
            break
        event_object = {
            "Event_ID": event['id'],
            "Event_type": event['type'],
            "Operation": event['operation'],
            "IP_Address": event['entity']['ipAddress'],
            "timestamp": event['timestamp']
        }
        event_objects.append(event_object)
        last_event_id = event['id']

    body = json.dumps(event_objects)
    request_params = build_request(workspace_id, shared_key, body, log_type)

    try:
        # Send the object to Azure Log Analytics
        logging.info(f"Sending {len(event_objects)} events to Azure Monitor")
        response = requests.post(request_params['url'], data=request_params['data'], headers=request_params['headers'])
        response.raise_for_status()  # Raises a HTTPError if the status is 4xx, 5xx
    except (requests.exceptions.RequestException, requests.exceptions.HTTPError) as e:
        logging.error(f"Post to Azure Monitor failed: {e}")
        state['failed'] = True
    else:
        logging.info("Post to Azure Monitor succeded with code: {}, last event id posted: {}".format(response.status_code, last_event_id))
        state['failed'] = False
        state['last_event_id'] = last_event_id
        state['more_events'] = more_events

    return state


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
