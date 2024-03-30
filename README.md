# mark_for_removal.py

json request example:
```
{
    "subscriptionId": "<subId>",
    "change": "CHG000009",
    "days": 7,
    "vmList": [
        {
            "name": "vm00",
            "resourceGroup": "vm00_group"
        },
        {
            "name": "vm01",
            "resourceGroup": "vm00_group"
        }
    ]
}
```