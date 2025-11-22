# AWS DynamoDB PowerShell Commands (One-Liners)

## ✅ Your Table Structure:
- **users**: Partition key = `username` (String)
- **plantings**: Partition key = `planting_id` (String)
- **Region**: `us-east-1`

---

## 📋 Quick Commands

### List all users
```powershell
aws dynamodb scan --table-name users --region us-east-1
```

### List all plantings
```powershell
aws dynamodb scan --table-name plantings --region us-east-1
```

### Get specific user by username
```powershell
aws dynamodb get-item --table-name users --key "{\`"username\`":{\`"S\`":\`"YOUR_USERNAME\`"}}" --region us-east-1
```

### Get plantings for specific user_id (FIXED - PowerShell JSON)
```powershell
aws dynamodb scan --table-name plantings --filter-expression "user_id = :uid" --expression-attribute-values "{\`:uid\`:{\`"S\`":\`"YOUR_USER_ID\`"}}" --region us-east-1
```

### Count users
```powershell
aws dynamodb scan --table-name users --select COUNT --region us-east-1
```

### Count plantings
```powershell
aws dynamodb scan --table-name plantings --select COUNT --region us-east-1
```

### View users in readable format
```powershell
aws dynamodb scan --table-name users --region us-east-1 | ConvertFrom-Json | ForEach-Object { $_.Items | ForEach-Object { Write-Host "Username: $($_.username.S), Email: $($_.email.S), UserID: $($_.user_id.S)" } }
```

### View plantings in readable format
```powershell
aws dynamodb scan --table-name plantings --region us-east-1 | ConvertFrom-Json | ForEach-Object { $_.Items | ForEach-Object { Write-Host "PlantingID: $($_.planting_id.S), UserID: $($_.user_id.S), Crop: $($_.crop_name.S), Date: $($_.planting_date.S)" } }
```

### Get specific planting by planting_id
```powershell
aws dynamodb get-item --table-name plantings --key "{\`"planting_id\`":{\`"S\`":\`"PLANTING_ID\`"}}" --region us-east-1
```

### Check table structure
```powershell
aws dynamodb describe-table --table-name users --query "Table.KeySchema" --region us-east-1
aws dynamodb describe-table --table-name plantings --query "Table.KeySchema" --region us-east-1
```

---

## 🔧 Alternative: Use JSON Files (Easier for Complex Queries)

### Step 1: Create `filter.json` file:
```json
{
  ":uid": {
    "S": "YOUR_USER_ID"
  }
}
```

### Step 2: Run command:
```powershell
aws dynamodb scan --table-name plantings --filter-expression "user_id = :uid" --expression-attribute-values file://filter.json --region us-east-1
```

---

## 🗑️ Delete Commands (BE CAREFUL!)

### Delete user
```powershell
aws dynamodb delete-item --table-name users --key "{\`"username\`":{\`"S\`":\`"YOUR_USERNAME\`"}}" --region us-east-1
```

### Delete planting
```powershell
aws dynamodb delete-item --table-name plantings --key "{\`"planting_id\`":{\`"S\`":\`"PLANTING_ID\`"}}" --region us-east-1
```

