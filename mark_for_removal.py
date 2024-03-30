import azure.functions as func
from azure.mgmt.resource import ManagementLockClient
from azure.mgmt.compute import ComputeManagementClient
from azure.identity import DefaultAzureCredential
from azure.data.tables import TableServiceClient
from datetime import datetime, timedelta
import logging

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

def add_rows_table(endpoint: str, table: str, rows: list):  
    cred = DefaultAzureCredential()
    table_client = TableServiceClient(endpoint=endpoint, credential=cred).get_table_client(table)
    for row in rows:
        table_client.update_entity(row, "merge")    

@app.route(route="mark_for_remove")
def mark_for_remove(req: func.HttpRequest) -> func.HttpResponse:
    try:
        json_body = req.get_json()
    except ValueError:
        return func.HttpResponse("Error: Invalid JSON.", status_code=400)
    
    subscription_id = json_body.get("subscriptionId")
    if subscription_id == None or not isinstance(subscription_id, str):
        return func.HttpResponse(
            "Error: susbcriptionId is required and the value must be a string.",
            status_code=400
        )
    vm_list = json_body.get("vmList")
    if vm_list == None or not isinstance(vm_list, list):
        return func.HttpResponse(
            "Error: vmList is required and the value must be a list.",
            status_code=400
        )
    change = json_body.get("change")
    if change == None or not isinstance(change, str):
        return func.HttpResponse(
            "Error: change is required and the value must be a string.",
            status_code=400
        )
    days = json_body.get("days")
    if days == None or not isinstance(days, int):
        return func.HttpResponse(
            "Error: 'days' key is required and the value must be a int.",
            status_code=400
        )
    
    try:
        for vm_info in vm_list:
            if vm_info["name"] == "" and vm_info["resourceGroup"] == "":
                return func.HttpResponse(f'Error: Each item in vmList must have a "name" and "resourceGroup."', status_code=400)                
    except KeyError:
        return func.HttpResponse(f'Error: Each item in vmList must have a "name" and "resourceGroup."', status_code=400)
        
    logging.info('Json is in a valid format')
    try:
        cred = DefaultAzureCredential()
        lock_client = ManagementLockClient(cred, subscription_id)
        compue_client = ComputeManagementClient(cred, subscription_id)
    except Exception as e:
        return func.HttpResponse(f"Error: {str(e)}", status_code=500)

    vms_to_lock = []
    for vm_json in vm_list:
        try:
            vm = compue_client.virtual_machines.get(resource_group_name=vm_json['resourceGroup'], vm_name=vm_json['name'])
        except Exception as e:
            return func.HttpResponse(f"Error getting vm information: {str(e)}", status_code=500)
        vms_to_lock.append(vm)

    rows = []
    for vm in vms_to_lock:
        try:
            group = vm.id.split('/')[4]
            compue_client.virtual_machines.begin_deallocate(group, vm.name)
            lock_parameters = {
                "level": "CanNotDelete",
                "notes": f"VM Marked to remove. change: {change}"
            }
            lock_client.management_locks.create_or_update_by_scope(scope=vm.id, lock_name="DeallocationLock", parameters=lock_parameters)
            now = datetime.now()
            remove_date = now + timedelta(days)
            row = {
                "PartitionKey": change,
                "RowKey": vm.name,
                "Name": vm.name,
                "ResourceGroup": group,
                "SubscriptionId": subscription_id,
                "Change": change,
                "Created": now.isoformat(),
                "RemoveDate": remove_date.isoformat()
            }
            rows.append(row)
        except Exception as e:
            return func.HttpResponse(f"Error deallocating or applying lock to vm {vm.name}: {str(e)}", status_code=500)
        
    add_rows_table("https://stasave001.table.core.windows.net", "vmremoval", rows)

    return func.HttpResponse(
         "OK!",
         status_code=200
    )