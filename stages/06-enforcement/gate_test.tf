# Lab 6 gate test: intentionally non-compliant so the compliance gate has something to reject.
# Never merge this file.
resource "azurerm_storage_account" "gate_test" {
  name                            = "stgrcgatetest001"
  resource_group_name             = "rg-grc-sandbox-dev"
  location                        = "eastus"
  account_tier                    = "Standard"
  account_replication_type        = "LRS"
  allow_nested_items_to_be_public = true
  shared_access_key_enabled       = true
}
