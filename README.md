# Censys Logbook Integration with Azure Monitor

This integration polls the Censys Logbook for new events and injects them into Azure Monitor via the Azure Monitory Data Collector HTTP endpoint. It is implemented as a Durable Azure Function using the Eternal Orchestration pattern, meaning that the Azure function runs indefinitely (but in an efficient and cost-effective way).  It is implemented in Python and uses the Censys Python SDK as well as Azure Python libraries.  For more details, see:

[Censys Python SDK](https://github.com/censys/censys-python)

[Azure Monitor Data Collector API](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/data-collector-api?tabs=powershell)

[Azure Durable Functions](https://learn.microsoft.com/en-us/azure/azure-functions/durable/quickstart-python-vscode?tabs=macos%2Cvs-code-set-indexing-flag&pivots=python-mode-decorators)

[Timers in Durable Functions](https://learn.microsoft.com/en-us/azure/azure-functions/durable/durable-functions-timers?tabs=python)

[Eternal Orchestration in Durable Functions](https://learn.microsoft.com/en-us/azure/azure-functions/durable/durable-functions-eternal-orchestrations?tabs=python)

## Community-Supported Integrations
This is a community-supported integration. Please note that while these integrations are designed to enhance your experience with Censys products, they are not officially supported by Censys.

## Getting Started
To use this integration, follow these general steps:

### Local Development

1. Rename the `local.settings.json.sample` file to `local.settings.json` and provide the required values as indicated in the file and described in detail in the next section.

2. Run or debug the function in VS Code.

### Deploying to Azure

1. Step 1

2. Step 2

## Configuring the Integration

This integration is configured using environment variables. For local development these can be set in `local.settings.json`. For deployment to Azure these will be set in the Azure function configuration.

| Name | Required | Description |
| ---- | -------- | ----------- |
| CENSYS_ASM_API_KEY | Yes | Xxxxx |
| AZURE_LOG_ANALYTICS_WORKSPACE_ID | Yes | Xxxx |
| AZURE_LOG_ANALYTICS_SHARED_KEY | Yes | Xxxxx |
| AZURE_LOG_ANALYTICS_LOG_TYPE | No | Name of custom log file, defaults to "Censys_Logbook_CL" |
| CENSYS_LOGBOOK_LIMIT | No | The maximum number of Logbook events to push to Azure at one time, defaults to 500 |
| CENSYS_LOGBOOK_LAST_EVENT_ID | No | The ID of the last Logbook event synchronized to Azure (used when restarting this function to pick up where it left off, or to start ingestion at some point other than the beginning of the Censys workspace) |


## Disclaimer
Please be aware that the availability and functionality of these community-supported integrations can change over time. They might not always be up-to-date with the latest versions of our products. Additionally, Censys reserves the right to remove or modify any integration that violates our guidelines or terms of use.
