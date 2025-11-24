# Fix: Planting Plans and Steps Generation

## Issue

Plantings were showing "No steps available" and some were incorrectly categorized (e.g., Lettuce with future harvest date showing in "Past Harvests").

## Solution

### 1. **Built-in Plan Calculator**

Created `tracker/plan_calculator.py` - a built-in library that generates 10-step care plans for each plant from `data.json`.

**Key Features:**
- Works without external dependencies
- Automatically calculates due dates based on planting date
- Supports 10 plants, each with 10 unique steps

### 2. **Always Regenerate Plans**

Updated `index()` view to **always regenerate plans** for all plantings when loading:
- Uses the built-in plan calculator/library
- Ensures all plantings have the latest 10-step plans
- Auto-saves regenerated plans back to DynamoDB

### 3. **Fixed Categorization**

Improved categorization logic:
- **PAST**: Harvest date is in the past (`days_until_harvest < 0`)
- **UPCOMING**: Harvest date within 7 days (`0 <= days <= 7`)
- **ONGOING**: Harvest date more than 7 days away (`days > 7`)

### 4. **Enhanced Logging**

Added detailed logging to track:
- Plan regeneration status
- Harvest date calculation
- Categorization decisions

## What Happens Now

1. **When viewing plantings:**
   - Plans are automatically regenerated using the library
   - All plantings get 10-step plans from `data.json`
   - Plans are auto-saved back to DynamoDB

2. **Categorization:**
   - Plantings with future harvest dates go to "Ongoing" or "Upcoming"
   - Only past harvest dates go to "Past Harvests"
   - Better date parsing and comparison

3. **Steps Display:**
   - All plantings now show all 10 steps
   - Steps include task descriptions and due dates
   - Modal displays steps when clicking on a planting

## 10 Plants with 10 Steps Each

1. **Cucumbers** - 10 steps (days 0, 7, 14, 21, 28, 35, 42, 49, 55, 65)
2. **Tomatoes** - 10 steps (days 0, 7, 14, 21, 28, 35, 42, 49, 60, 90)
3. **Lettuce** - 10 steps (days 0, 7, 14, 21, 28, 35, 42, 49, 55, 65)
4. **Carrots** - 10 steps (days 0, 7, 21, 28, 35, 42, 49, 60, 70, 80)
5. **Bell Peppers** - 10 steps (days 0, 7, 14, 21, 28, 35, 42, 49, 75, 90)
6. **Spinach** - 10 steps (days 0, 7, 14, 21, 28, 35, 42, 49, 55, 65)
7. **Basil** - 10 steps (days 0, 7, 14, 25, 28, 35, 40, 50, 60, 70)
8. **Radishes** - 10 steps (days 0, 3, 7, 14, 18, 21, 25, 30, 35, 40)
9. **Zucchini** - 10 steps (days 0, 7, 14, 21, 28, 35, 42, 49, 50, 65)
10. **Potatoes** - 10 steps (days 0, 7, 21, 35, 49, 56, 63, 70, 100, 105)

## Files Modified

- `tracker/plan_calculator.py` - New built-in plan calculator
- `tracker/data.json` - Updated with 10 plants, 10 steps each
- `tracker/views.py` - Always regenerates plans, fixes categorization
- `tracker/templates/tracker/index.html` - Better empty state messages

## How to Verify

1. **View any planting** - Should show all 10 steps
2. **Check categorization** - Future harvest dates should NOT be in "Past Harvests"
3. **Check logs** - Should see plan regeneration messages

## Example

For Lettuce planted Oct 28, 2025:
- Last step is day 65 → Harvest date = Dec 2, 2025
- If today is Nov 24, 2025 → Should be in "Ongoing" (8 days away)
- Will automatically regenerate 10-step plan on page load

