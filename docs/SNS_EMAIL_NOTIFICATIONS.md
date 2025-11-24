# SNS Email Notifications Implementation

## Summary

Email notifications are now integrated with the profile section and notifications tab. When users save their email in the profile, they're automatically subscribed to SNS for harvest reminders, and the notifications tab shows email summaries of upcoming tasks.

## Changes Made

### 1. **Profile View - Auto Subscribe Email to SNS**

**File:** `tracker/views.py` - `profile()` function

**What it does:**
- When user saves profile with email, automatically subscribes email to SNS topic
- Enables notifications preference in DynamoDB
- Works for both Cognito and Django auth users

**Code flow:**
1. User submits profile form with email
2. Email is updated in DynamoDB (for Cognito users) or Django User model
3. Email is subscribed to SNS topic via `subscribe_email_to_topic()`
4. Notifications preference is enabled via `update_user_notification_preference()`

### 2. **Notification Summaries API Endpoint**

**File:** `tracker/views.py` - `get_notification_summaries()` function
**URL:** `/api/notification-summaries/`

**What it does:**
- Returns upcoming harvest tasks for the logged-in user (next 7 days)
- Returns email summary text (formatted message that would be sent)
- Returns JSON with summaries, email, and count

**Response format:**
```json
{
    "success": true,
    "email": "user@example.com",
    "summaries": [
        {
            "crop_name": "Tomatoes",
            "task": "Water plants",
            "due_date": "2025-01-25",
            "days_until": 3,
            "planting_date": "2025-01-01",
            "batch_id": "batch-20250101"
        }
    ],
    "email_summary": "Hello User,\n\nHere are your upcoming harvest reminders:\n\n...",
    "count": 2
}
```

### 3. **Notifications Modal - Email Summaries Display**

**File:** `tracker/templates/tracker/index.html`

**What it does:**
- Displays upcoming harvest tasks in a user-friendly format
- Shows email summary text that would be sent via SNS
- Color-coded by urgency (red=today, orange=1-2 days, green=3+ days)

**Features:**
- Click notification button (🔔) to open modal
- Right-click notification button to toggle notifications on/off
- Modal loads summaries dynamically via API
- Shows email summary formatted text

## User Flow

### 1. Save Email in Profile

1. User opens profile (via avatar icon)
2. Enters/updates email: `Sai.Shreyas23@outlook.com`
3. Clicks "Save"
4. **Automatically:**
   - Email saved to DynamoDB
   - Email subscribed to SNS topic
   - Notifications enabled
   - User receives SNS confirmation email (must confirm)

### 2. View Notifications

1. User clicks notification button (🔔) in header
2. Modal opens showing:
   - **Upcoming tasks** (next 7 days)
   - Each task shows:
     - Crop name
     - Task description
     - Due date
     - Days until due
   - **Email summary** section showing formatted message

### 3. Receive Notifications

1. Scheduled task runs: `python manage.py send_harvest_reminders --days 3`
2. Checks user's plantings for tasks due in 3 days
3. Sends email via SNS to subscribed email addresses
4. User receives email with harvest reminders

## Technical Details

### SNS Subscription

When email is saved in profile:
```python
from .sns_helper import subscribe_email_to_topic
subscribe_email_to_topic(email)
```

This:
- Subscribes email to SNS topic
- Returns SubscriptionArn (may be "PendingConfirmation")
- User must confirm subscription via email

### Notification Summaries

The endpoint:
1. Gets user_id from session/middleware
2. Loads user's plantings from DynamoDB
3. Scans plan tasks for due dates in next 7 days
4. Formats summaries with crop name, task, due date
5. Generates email summary text

### Email Summary Format

```
Hello {username},

Here are your upcoming harvest reminders:

• Tomatoes: Water plants due in 3 day(s) (2025-01-25)
• Lettuce: Harvest due today (2025-01-22)

Thanks,
SmartHarvester
```

## URL Routes

- `/api/notification-summaries/` - GET request to fetch summaries
- `/api/toggle-notifications/` - POST request to enable/disable notifications

## Configuration Required

### Environment Variables

```bash
# SNS Topic ARN
SNS_TOPIC_ARN=arn:aws:sns:us-east-1:518029233624:harvest-notifications

# AWS Credentials (or use IAM role)
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
```

### IAM Permissions

The application needs:
- `sns:Subscribe` - To subscribe emails
- `sns:Publish` - To send notifications
- `dynamodb:UpdateItem` - To enable notification preference
- `dynamodb:Query` - To load plantings

## Testing

### Test 1: Save Email in Profile

1. Login via Cognito
2. Click profile icon
3. Enter email: `test@example.com`
4. Click "Save"
5. Check logs for:
   ```
   Profile: Subscribed/updated email test@example.com to SNS topic
   Profile: Enabled notifications for user: ...
   ```
6. Check email inbox for SNS subscription confirmation
7. Click confirmation link

### Test 2: View Notification Summaries

1. Add a planting with tasks
2. Click notification button (🔔)
3. Modal should show:
   - Upcoming tasks (if any in next 7 days)
   - Email summary text
4. Check browser console for API response

### Test 3: Send Test Notification

```bash
python manage.py send_harvest_reminders --days 3 --dry-run
```

## UI Updates

### Notification Modal

- **Before**: Static "Upcoming harvest!" message
- **After**: 
  - Dynamic list of upcoming tasks
  - Color-coded by urgency
  - Email summary section showing formatted message

### Notification Button

- **Before**: Only toggled notifications on/off
- **After**: 
  - Click: Opens notification modal
  - Right-click: Toggles notifications on/off
  - Title shows: "Click to view notifications | Right-click to toggle on/off"

## Integration Points

### Profile Save → SNS Subscription

```python
# In profile() view
email_to_subscribe = email or user_data.get('email')
if email_to_subscribe:
    subscribe_email_to_topic(email_to_subscribe)
    update_user_notification_preference(username, True)
```

### Notifications Tab → Summaries API

```javascript
// In index.html
async function loadNotificationSummaries() {
    const response = await fetch('/api/notification-summaries/');
    const data = await response.json();
    // Display summaries in modal
}
```

## Next Steps

1. ✅ Profile saves email → Auto-subscribes to SNS
2. ✅ Notifications tab shows email summaries
3. ⏭️ User confirms SNS subscription via email
4. ⏭️ Scheduled task sends harvest reminders
5. ⏭️ User receives email notifications

## Summary

- **Profile**: Email automatically subscribed to SNS when saved
- **Notifications Tab**: Shows upcoming tasks and email summary
- **SNS Integration**: Fully connected for email notifications
- **User Experience**: One-click profile save → notifications enabled

