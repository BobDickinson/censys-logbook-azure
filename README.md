The Censys connector allows you to easily send Censys Logbook and Risk events to Microsoft Sentinel.

## Connector attributes

| Connector attribute | Description |
| --- | --- |
| **Log Analytics table(s)** | CensysLogbook_CL<br/> CensysRisks_CL |
| **Data collection rules support** | Not currently supported |
| **Supported by** | [Censys](https://www.censys.com/) |

## Query samples

**Summary of Logbook events by operation**
   ```kusto
CensysLogbook_CL            
   | summarize Count=count() by Operation_s
   ```

## Prerequisites

To integrate with Censys make sure you have: 

- **Microsoft.Web/sites permissions**: Read and write permissions to Azure Functions to create a Function App is required. [See the documentation to learn more about Azure Functions](/azure/azure-functions/).

## Vendor installation instructions

> [!NOTE]
   >  This connector: Uses Azure Functions to connect to Censys ASM APIs to pull Logbook and Risk events into Microsoft Sentinel. This might result in additional data ingestion costs. Check the [Azure Functions pricing page](https://azure.microsoft.com/pricing/details/functions/) for details.  This connector also requires an Azure Key Vault to store the required parameters stored as secrets (will be created automatically by the ARM template when using the "Deploy to Azure" button option below).

STEP 1 - Get your Censys credentials

Log into Censys ASM and navigate to the [Integrations page](https://app.censys.io/integrations), where you will find your API key.  Record this for use below.

STEP 2 - Get your Azure Log Analytics workspace credentials

Log into Azure and navigate to Log Analytics Workspaces, select the desired workspace, select 'Agents', then click 'Log Analytics agent instructions'.  Record the Workspace ID and Primary Key for use below.

STEP 3 - Deploy the connector and the associated Azure Function

Option 1: Deploy using the Azure Resource Manager (ARM) Template

1. Click the **Deploy to Azure** button below. 

<!-- 
  Deploy to Azure button
  ======================
  The final piece of the path for the Deploy to Azure link is the URL to the azuredeploy.json file (URL encoded).
  The link below points to the raw tip of that file in this repo.  This will need to be changed when the repo moves,
  and you may want to point it to a more stable version of the file to support periodic releases of a stable template.

  The officialy support integrations hide this URL complexity behind a shortened (and branded) aka.ms link, like:
  https://aka.ms/censys-sentinel (Microsoft should be able to provide guidance on that once we're in their developer program).
-->
[![Deploy To Azure](https://aka.ms/deploytoazurebutton)](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2FBobDickinson%2Fcensys-logbook-azure%2Fmain%2Fazuredeploy.json) 

2. Select the preferred **Subscription**, **Resource Group** and **Location**. 
3. Enter the following parameters: 
 >- Choose **KeyVaultName** and **FunctionName** for the new resources (both values must be globally unique)
 >- Enter the Censys ASM API key from Step 1: **CensysAsmApiKey**
 >- Enter the Workspace credentials from Step 2:  **AzureLogsAnalyticsWorkspaceId** and **AzureLogAnalyticsWorkspaceSharedKey**
4. Mark the checkbox labeled **I agree to the terms and conditions stated above**. 
5. Click **Review+Create**, the once validated, click **Save** to deploy.

Option 2: Manual Deployment of the Azure Function

>- See our [Developer Documentation](DEV.md) to deploy the connector manually.
