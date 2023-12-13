# Azure Functions deps
import logging
import azure.functions as func

app = func.FunctionApp()

@app.function_name(name="CensysLogbookSync")
@app.schedule(schedule="0 0 * * * *", arg_name="mytimer", run_on_startup=False) 
def censys_logbook_sync(mytimer: func.TimerRequest) -> None:

    logging.info('Not implemented yet')

@app.function_name(name="CensysRisksSync")
@app.schedule(schedule="0 0 * * * *", arg_name="mytimer", run_on_startup=False) 
def censys_risks_sync(mytimer: func.TimerRequest) -> None:

    logging.info("Not implemented yet")
