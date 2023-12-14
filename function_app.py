# Azure Functions deps
from datetime import datetime, timedelta
import logging
import os
import uuid
import json
import hashlib
import hmac
import base64
import azure.functions as func

import requests

# Censys ASM deps
from censys.asm import Logbook

app = func.FunctionApp()

@app.function_name(name="CensysLogbookSync")
@app.schedule(schedule="0 0 * * * *", arg_name="mytimer", run_on_startup=False) 
def censys_logbook_sync(mytimer: func.TimerRequest) -> None:

    logging.info('Not implemented yet')

@app.function_name(name="CensysRisksSync")
@app.schedule(schedule="0 0 * * * *", arg_name="mytimer", run_on_startup=False) 
def censys_risks_sync(mytimer: func.TimerRequest) -> None:

    logging.info("Not implemented yet")
