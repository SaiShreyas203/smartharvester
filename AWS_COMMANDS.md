# AWS DynamoDB One-Liner Commands (PowerShell Compatible)

## Check if tables exist
```powershell
aws dynamodb describe-table --table-name users --region us-east-1
aws dynamodb describe-table --table-name plantings --region us-east-1
```

## List all items in users table
```powershell
aws dynamodb scan --table-name users --region us-east-1
```

## List all items in plantings table
```powershell
aws dynamodb scan --table-name plantings --region us-east-1
```

## Get specific user by username (PowerShell)
```powershell
aws dynamodb get-item --table-name users --key "{\`"username\`":{\`"S\`":\`"YOUR_USERNAME\`"}}" --region us-east-1
```

## Get plantings for a specific user_id (PowerShell - Fixed JSON)
```powershell
aws dynamodb scan --table-name plantings --filter-expression "user_id = :uid" --expression-attribute-values "{\`:uid\`:{\`"S\`":\`"YOUR_USER_ID\`"}}" --region us-east-1
```

## Count items in users table
```powershell
aws dynamodb scan --table-name users --select COUNT --region us-east-1
```

## Count items in plantings table
```powershell
aws dynamodb scan --table-name plantings --select COUNT --region us-east-1
```

## List all tables in region
```powershell
aws dynamodb list-tables --region us-east-1
```

## Check table structure (KeySchema)
```powershell
aws dynamodb describe-table --table-name users --query "Table.KeySchema" --region us-east-1
aws dynamodb describe-table --table-name plantings --query "Table.KeySchema" --region us-east-1
```

## Get all users (formatted)
```powershell
aws dynamodb scan --table-name users --region us-east-1 | ConvertFrom-Json | Select-Object -ExpandProperty Items
```

## Get all plantings (formatted)
```powershell
aws dynamodb scan --table-name plantings --region us-east-1 | ConvertFrom-Json | Select-Object -ExpandProperty Items
```

## Get specific user by username (PowerShell - Alternative with file)
```powershell
# Create key.json file first: {"username":{"S":"YOUR_USERNAME"}}
aws dynamodb get-item --table-name users --key file://key.json --region us-east-1
```

## Get plantings by user_id (PowerShell - Using file method)
```powershell
# Create filter.json: {"user_id":{"S":"YOUR_USER_ID"}}
# Then use: aws dynamodb scan --table-name plantings --filter-expression "user_id = :uid" --expression-attribute-values file://filter.json --region us-east-1
```

## Delete a user (be careful!)
```powershell
aws dynamodb delete-item --table-name users --key "{\`"username\`":{\`"S\`":\`"YOUR_USERNAME\`"}}" --region us-east-1
```

## Delete a planting (be careful!)
```powershell
aws dynamodb delete-item --table-name plantings --key "{\`"planting_id\`":{\`"S\`":\`"PLANTING_ID\`"}}" --region us-east-1
```

## Check table status
```powershell
aws dynamodb describe-table --table-name users --query "Table.TableStatus" --region us-east-1
aws dynamodb describe-table --table-name plantings --query "Table.TableStatus" --region us-east-1
```

## View all users in readable format
```powershell
aws dynamodb scan --table-name users --region us-east-1 | ConvertFrom-Json | ForEach-Object { $_.Items | ForEach-Object { [PSCustomObject]@{ Username = $_.username.S; Email = $_.email.S; UserID = $_.user_id.S } } }
```

## View all plantings in readable format
```powershell
aws dynamodb scan --table-name plantings --region us-east-1 | ConvertFrom-Json | ForEach-Object { $_.Items | ForEach-Object { [PSCustomObject]@{ PlantingID = $_.planting_id.S; UserID = $_.user_id.S; CropName = $_.crop_name.S; PlantingDate = $_.planting_date.S } } }
```

