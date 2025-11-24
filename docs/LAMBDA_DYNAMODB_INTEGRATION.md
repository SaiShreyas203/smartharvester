# Lambda DynamoDB Integration Plan

## Overview

The Post Confirmation Lambda trigger (`lambda/post_confirmation_lambda.py`) automatically saves Cognito user data to the DynamoDB `users` table when a user confirms their account. The Django application **trusts this Lambda trigger** and reads from DynamoDB instead of duplicating the save operation.

## Precise Flow Architecture

### 1. User Sign-Up & Confirmation Flow

```
User Sign-Up via Cognito Hosted UI
    ↓
Cognito Creates User
    ↓
Pre Sign-up Lambda Trigger (lambda/cognito_auto_confirm.py)
    → Auto-confirms user
    → Auto-verifies email/phone
    ↓
Post Confirmation Lambda Trigger (lambda/post_confirmation_lambda.py)
    → Extracts event.get("userName") (Cognito username)
    → Saves to DynamoDB users table:
        * PK: username (from event.get("userName"))
        * Attributes: user_id (sub), email, name, preferred_username
    ↓
✅ User data now in DynamoDB users table (Lambda responsibility)
```

**Lambda Trigger Details:**
- **Trigger Point:** Post Confirmation (after user confirms account)
- **PK:** `username` (from `event.get("userName")` - Cognito username)
- **Saved Attributes:**
  - `user_id`: Cognito `sub` claim
  - `email`: User email
  - `name`: Full name or `given_name`
  - `preferred_username`: Preferred username
- **Operation:** `put_item` (idempotent - creates or updates)

### 2. User Login Flow (Django)

```
User Logs In via Cognito Hosted UI
    ↓
cognito_callback receives authorization code
    ↓
Exchange code for tokens (id_token, access_token, refresh_token)
    ↓
persist_cognito_user():
    ✅ Extract username from id_token (same as Lambda used)
    ✅ Load user from DynamoDB users table (Lambda already saved it)
    ✅ Verify user exists (if not, log warning but use token data as fallback)
    ✅ Get user_id from DynamoDB record (source of truth)
    ✅ Migrate session plantings using user_id from DynamoDB
    ↓
User data loaded from DynamoDB (NOT saved again - Lambda already did it!)
```

### 3. Plantings Flow

```
User Adds Planting
    ↓
save_planting():
    ✅ Get user_id from middleware/session (Cognito user)
    ✅ Load user from DynamoDB users table (trust Lambda saved it)
    ✅ Use user_id from DynamoDB (source of truth)
    ✅ Save planting to DynamoDB plantings table with:
        * user_id (from DynamoDB users table)
        * username (from DynamoDB users table)
    ✅ Also save to session for immediate UI
    ↓
Planting saved with correct user association
```

### 4. View Dashboard Flow

```
User Views Dashboard (index view)
    ↓
STEP 1: Load user from DynamoDB users table (Lambda saved it)
    ↓
STEP 2: Load plantings from DynamoDB plantings table (filtered by user_id from DynamoDB)
    ↓
STEP 3: Merge with session plantings (for newly saved items)
    ↓
Display to user
```

## Key Principles

1. **Single Source of Truth:** Lambda trigger saves user once, Django reads from DynamoDB
2. **No Duplicate Saves:** Django does NOT save user - Lambda handles it
3. **Consistency:** All views use the same `user_id` from DynamoDB
4. **Fallback Safety:** If user not in DynamoDB yet (Lambda hasn't run), use token data as fallback
5. **Plantings Association:** Plantings always use `user_id` from DynamoDB users table

## Lambda Trigger Implementation

**File:** `lambda/post_confirmation_lambda.py`

**What it saves:**
- **PK:** `username` (from `event.get("userName")` - Cognito username)
- **Attributes:**
  - `user_id`: Cognito `sub` claim
  - `email`: User email
  - `name`: Full name or `given_name`
  - `preferred_username`: Preferred username

**Operation:** Uses `put_item` for idempotent upsert (creates if doesn't exist, updates if exists)

## Django Code Changes

### 1. `persist_cognito_user()` - Trust Lambda, Don't Duplicate Save

**Before:** Tried to save user to DynamoDB (duplicate of Lambda)
**After:** 
- ✅ Load user from DynamoDB (Lambda already saved it)
- ✅ Verify user exists
- ✅ Return `user_id` from DynamoDB
- ✅ Migrate session plantings using DynamoDB `user_id`

### 2. All Views - Load User from DynamoDB First

**Before:** Used tokens/middleware only
**After:**
- ✅ Load user from DynamoDB first (source of truth)
- ✅ Use `user_id` and `username` from DynamoDB
- ✅ Fall back to tokens if DynamoDB lookup fails

### 3. `save_planting()` - Use DynamoDB User Data

**Before:** Used `user_id` from tokens/session
**After:**
- ✅ Load user from DynamoDB
- ✅ Use `user_id` from DynamoDB record
- ✅ Save planting with `user_id` from DynamoDB (ensures consistency)

### 4. `index` View - Load from DynamoDB First

**Before:** Mixed tokens and session
**After:**
- ✅ STEP 1: Load user from DynamoDB users table
- ✅ STEP 2: Load plantings from DynamoDB plantings table
- ✅ STEP 3: Merge with session for immediate UI

## Username Extraction Consistency

The Lambda uses `event.get("userName")` which is the Cognito username (typically `cognito:username`). The Django code extracts the same username using this priority:

```python
username = (
    claims.get('cognito:username') or      # Primary (matches Lambda's event.get("userName"))
    claims.get('preferred_username') or    # Secondary
    claims.get('username') or              # Tertiary
    claims.get('email')                     # Fallback
)
```

This ensures consistency - the same username used by Lambda is used by Django for DynamoDB lookups.

## Data Flow Diagram

```
┌─────────────────┐
│  Cognito Login  │
└────────┬────────┘
         │
         ▼
┌──────────────────────────────┐
│ Post Confirmation Lambda     │
│ - event.get("userName")      │
│ - Saves to DynamoDB users    │
│   table (PK: username)       │
└────────┬─────────────────────┘
         │
         ▼
┌──────────────────────────────┐
│ DynamoDB users table         │
│ PK: username                 │
│ user_id, email, name, etc.   │
└────────┬─────────────────────┘
         │
         ▼
┌──────────────────────────────┐
│ Django cognito_callback      │
│ - Loads user from DynamoDB   │
│ - Gets user_id from DynamoDB │
│ - Migrates session plantings │
└────────┬─────────────────────┘
         │
         ▼
┌──────────────────────────────┐
│ User adds planting           │
│ - Loads user from DynamoDB   │
│ - Uses user_id from DynamoDB │
│ - Saves to plantings table   │
└────────┬─────────────────────┘
         │
         ▼
┌──────────────────────────────┐
│ DynamoDB plantings table     │
│ user_id, username, crop, etc.│
└──────────────────────────────┘
```

## Benefits

1. **Single Responsibility:** Lambda handles user creation, Django handles user data usage
2. **No Race Conditions:** No duplicate saves from Django and Lambda
3. **Consistency:** All views use same `user_id` from DynamoDB
4. **Reliability:** User data persists even if Django session is lost
5. **Scalability:** Lambda handles user creation independently of Django

## Error Handling

- If user not found in DynamoDB (Lambda hasn't run yet):
  - Log warning
  - Use token data as fallback
  - Don't fail the request
  - Lambda will save user on next confirmation

- If DynamoDB lookup fails (permissions, network, etc.):
  - Log error
  - Fall back to token data
  - Don't fail the request
  - User can still use the app

## Testing Checklist

- [ ] User signs up via Cognito Hosted UI
- [ ] Lambda trigger saves user to DynamoDB
- [ ] User logs in, Django loads user from DynamoDB
- [ ] User adds planting, uses `user_id` from DynamoDB
- [ ] Plantings are saved to DynamoDB with correct `user_id`
- [ ] User views dashboard, sees plantings from DynamoDB
- [ ] User logs out and logs back in, sees same plantings
