# Censys Logbook Integration with Azure Monitor - For Developers

This integration polls the Censys Logbook for new events and injects them into Azure Monitor via the Azure Monitor Data Collector HTTP endpoint. It is implemented as an Azure Function with a timer trigger. It is implemented in Python and uses the Censys Python SDK as well as Azure Python libraries.  For more details, see:

[Censys Python SDK](https://github.com/censys/censys-python)

[Azure Monitor Data Collector API](https://learn.microsoft.com/en-us/azure/azure-monitor/logs/data-collector-api?tabs=powershell)

[Azure Functions Python Developers Guide](https://learn.microsoft.com/en-us/azure/azure-functions/functions-reference-python?tabs=asgi%2Capplication-level&pivots=python-mode-decorators)

[Quickstart: Create a function in Azure with Python using Visual Studio Code](https://learn.microsoft.com/en-us/azure/azure-functions/create-first-function-vs-code-python?pivots=python-mode-decorators)

[Timer Triggers for Azure Functions](https://learn.microsoft.com/en-us/azure/azure-functions/functions-bindings-timer?tabs=python-v2%2Cisolated-process%2Cnodejs-v4&pivots=programming-language-python)

## Community-Supported Integrations
This is a community-supported integration. Please note that while these integrations are designed to enhance your experience with Censys products, they are not officially supported by Censys.

## Getting Started
To use this integration, follow these general steps:

### Local Development

1. Install Visual Studion Code, Python extensions, and Azure extensions.

2. Clone this project locally and open in VS Code.

3. Rename the `local.settings.json.sample` file to `local.settings.json` and provide the required values as indicated in the file and described in detail in the section below.

4. In your Azure Key Vault, set the Secret value CENSYS-LOGBOOK-NEXT-EVENT to 1. Update your local environment (via settings as above) so that the KEYVAULT_NAME setting contains the name of your key vault.

5. Install Azure command line tools and log in to Azure locally using `az login` (in order to be able to auth to Key Vault during local execution)

6. Install Python dependencies for the project using `pip install -r requirements.txt`

7. Install the [Azurite extension for VS Code](https://learn.microsoft.com/en-us/azure/storage/common/storage-use-azurite?tabs=visual-studio-code%2Cblob-storage) if you haven't already.

8. Start Azurite services from VS Code command palette: "Azurite: Start"

9. Run or debug the function in VS Code.  Note that this will obey the timer schedule configuration value.  For testing you may change the `run_on_startup` param to `True` in the app.schedule decorator (do NOT deploy to Azure with this set to True - it will run the function very frequently - on the order of once a minute - as the Azure internal state is shuffled around).

### Deploying to Azure

1. Follow standard instructions for [Deploying an Azure Function from VS Code](https://learn.microsoft.com/en-us/azure/azure-functions/functions-develop-vs-code?tabs=node-v3%2Cpython-v2%2Cisolated-process&pivots=programming-language-python)

2. The first time you deploy in this way it will copy your local settings to the Azure Function App "Configuration", where you will maintain them going forward.  If you want update that configuration from your local environment in the future, you can find your Function App "Application Settings" in the Azure extension view, right click, and select "Upload Local Settings...".

## Configuring the Integration

This integration is configured using environment variables. For local development these can be set in `local.settings.json`. For deployment to Azure these will be set in the Azure Function App "Configuration" values.
  
In production, some of these environment variables will be populated from a Key Vault using an environment/configuration value formatted like: `"@Microsoft.KeyVault(SecretUri=https://[YourKeyVaultName].vault.azure.net/secrets/[NameOfSecretInVault])"` (without the square brackets).

The Azure fuctions rely on an Azure Key Vault for access to Secrets called "CensysLogbookStartAfter" and "CensysRisksStartAfter". This is how we track the Censys cursor value between function runs (so we can pick up where we left off on subsequent runs).  While all other configuration variables may be accessed from the Key Vault indirectly (via redirected environment vars), these values will be accessed directly from the Key Vault (since they are both read and written to).  The Azure Key Vault name must be provided to the function via the KEYVAULT_NAME environment variable, and both your development environment (if desired) and Function App must have read and update privileges on Secrets in that Key Vault.

For initial configuration, these values can contain be either a number indicating the previous event ID processed (0 to start at the beginning of the respective log), or an RFC3339 formatted date to beging processing from that timestamp.  Once the function starts, it will store the last processed event ID in these values.

For the Azure Log Analytics Workspace ID and Shared Key, in the Azure console go to Log Analytics Workspaces, select a workspace, select 'Agents', then click 'Log Analytics agent instructions'.  For the shared key, you may use either the primary or secondary key.

| Name | Required | Description |
| ---- | -------- | ----------- |
| CENSYS_ASM_API_KEY | Yes | Censys ASM API key - find under the Integrations tab in Censys ASM |
| AZURE_LOG_ANALYTICS_WORKSPACE_ID | Yes | Azure Log Analytics Workspace ID |
| AZURE_LOG_ANALYTICS_SHARED_KEY | Yes | Azure Log Analytics agent shared key |
| KEYVAULT_NAME | Yes | Name of the Azure Keyvault used by this Azure Function |
| CENSYS_LOGBOOK_SYNC_INTERVAL | Yes | Chron expression for the CensysLogbookSync timer trigger, see [NCHRONTAB expressions](https://learn.microsoft.com/en-us/azure/azure-functions/functions-bindings-timer?tabs=python-v2%2Cisolated-process%2Cnodejs-v4&pivots=programming-language-python#ncrontab-expressions) |
| CENSYS_RISKS_SYNC_INTERVAL | Yes | Chron expression for the CensysLogbookSync timer trigger, see [NCHRONTAB expressions](https://learn.microsoft.com/en-us/azure/azure-functions/functions-bindings-timer?tabs=python-v2%2Cisolated-process%2Cnodejs-v4&pivots=programming-language-python#ncrontab-expressions) |
| AZURE_LOG_ANALYTICS_LOG_TYPE_CENSYS_LOGBOOK | No | Name of custom log file for logbook events, defaults to "Censys_Logbook_CL" |
| AZURE_LOG_ANALYTICS_LOG_TYPE_CENSYS_RISKS | No | Name of custom log file for risk events, defaults to "Censys_Risks_CL" |
| AZURE_EVENT_POST_LIMIT | No | The maximum number of Logbook events to push to Azure at one time, defaults to 500 |
| CENSYS_RISK_EVENTS_LIMIT | No | The page size of risk events for processing, defaults to 500 |
## Disclaimer
Please be aware that the availability and functionality of these community-supported integrations can change over time. They might not always be up-to-date with the latest versions of our products. Additionally, Censys reserves the right to remove or modify any integration that violates our guidelines or terms of use.
