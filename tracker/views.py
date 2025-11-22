import json
from datetime import date, timedelta
from django.shortcuts import render, redirect
from django.conf import settings
import os
import boto3
import uuid

from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
import logging

logger = logging.getLogger(__name__)

# local imports
from .forms import SignUpForm
from .models import UserProfile

# Lazy import helper will locate the plan function at call time.
from django.http import JsonResponse

# Lazy import helper: try to import the real calculate_plan, otherwise
# provide a safe fallback so the app won't crash at module import time.
def _get_calculate_plan():
    """Return a callable to calculate a plan.

    Tries several common function names in `smartharvest_plan.plan` and
    returns the first callable found. If the module can't be imported or
    no callable is found, returns a fallback that returns an empty list.
    """
    try:
        import importlib
        mod = importlib.import_module('smartharvest_plan.plan')
        # Try common function names; this makes the code robust to slight
        # naming differences in the installed package.
        for name in ('calculate_plan', 'generate_plan', 'create_plan', 'build_plan', 'plan'):
            if hasattr(mod, name):
                candidate = getattr(mod, name)
                if callable(candidate):
                    logger.info('Using %s from smartharvest_plan.plan', name)
                    return candidate
        logger.warning('Imported smartharvest_plan.plan but no callable plan function found')
    except Exception as e:
        logger.warning('Could not import smartharvest_plan.plan: %s', e)

    # Fallback that returns an empty plan so the app remains usable.
    def _fallback(*args, **kwargs):
        return []

    return _fallback

DATA_FILE_PATH = os.path.join(settings.BASE_DIR, 'tracker', 'data.json')

def load_plant_data():
    with open(DATA_FILE_PATH, 'r') as f:
        return json.load(f)

def index(request):
    """
    Display the user's saved plantings.
    Similar to the original simple code, but loads from DynamoDB and session.
    """
    from .dynamodb_helper import load_user_plantings, get_user_id_from_token
    
    # Initialize plantings list (like original code)
    user_plantings = []
    
    # Get user_id from token
    user_id = get_user_id_from_token(request)
    logger.info('Index: user_id = %s', user_id if user_id else 'None')
    
    # Try to load from DynamoDB first if user_id exists
    if user_id:
        try:
            dynamodb_plantings = load_user_plantings(user_id)
            if dynamodb_plantings:
                user_plantings = dynamodb_plantings
                logger.info('Loaded %d plantings from DynamoDB', len(user_plantings))
        except Exception as e:
            logger.exception('Error loading from DynamoDB: %s', e)
    
    # If no DynamoDB data, use session (like original code's approach)
    if not user_plantings:
        session_plantings = request.session.get('user_plantings', [])
        if session_plantings:
            user_plantings = session_plantings
            logger.info('Using %d plantings from session', len(user_plantings))
    
    logger.info('Displaying %d plantings total', len(user_plantings))
    
    today = date.today()
    
    ongoing, upcoming, past = [], [], []

    # Process each planting with error handling
    for i, planting_data in enumerate(user_plantings):
        try:
            planting = planting_data.copy() # Work with a copy
            planting['id'] = i

            # Ensure image_url is preserved (for display)
            if 'image_url' not in planting:
                planting['image_url'] = planting_data.get('image_url', '')

            # Convert the main planting_date
            if 'planting_date' in planting:
                planting['planting_date'] = date.fromisoformat(planting['planting_date'])
            else:
                logger.warning('Planting at index %d missing planting_date, skipping', i)
                continue

            # --- FIX: Convert due_dates within the plan ---
            for task in planting.get('plan', []):
                if 'due_date' in task and task['due_date']:
                    try:
                        if isinstance(task['due_date'], str):
                            task['due_date'] = date.fromisoformat(task['due_date'])
                    except (ValueError, TypeError) as e:
                        logger.warning('Error parsing due_date in planting %d: %s', i, e)
                        task['due_date'] = None

            harvest_task = next((task for task in reversed(planting.get('plan', [])) if 'due_date' in task and task.get('due_date')), None)

            if harvest_task and harvest_task.get('due_date'):
                harvest_date = harvest_task['due_date'] # It's already a date object
                planting['harvest_date'] = harvest_date

                if harvest_date < today:
                    past.append(planting)
                elif (harvest_date - today).days <= 7:
                    upcoming.append(planting)
                else:
                    ongoing.append(planting)
            else:
                ongoing.append(planting)
        except Exception as e:
            logger.exception('Error processing planting at index %d: %s', i, e)
            # Skip this planting but continue with others
            continue
            
    logger.info('Processed plantings: ongoing=%d, upcoming=%d, past=%d', len(ongoing), len(upcoming), len(past))
    
    # Get user info and notification preference
    notifications_enabled = True
    user_email = None
    username = None
    
    try:
        from .dynamodb_helper import get_user_data_from_token, get_user_notification_preference
        user_data = get_user_data_from_token(request)
        if user_data:
            user_email = user_data.get('email')
            username = user_data.get('username') or user_data.get('preferred_username') or user_data.get('sub')
            
            if username:
                notifications_enabled = get_user_notification_preference(username)
                logger.info('Notification preference for %s: %s', username, notifications_enabled)
    except Exception as e:
        logger.exception('Error getting user notification preference: %s', e)
    
    context = {
        'ongoing': ongoing,
        'upcoming': upcoming,
        'past': past,
        'notifications_enabled': notifications_enabled,
        'user_email': user_email,
        'username': username
    }
    return render(request, 'tracker/index.html', context)

def add_planting_view(request):
    plant_data = load_plant_data()
    context = {
        'plant_names': [p['name'] for p in plant_data['plants']],
        'is_editing': False
    }
    return render(request, 'tracker/edit.html', context)

def save_planting(request):
    if request.method == 'POST':
        crop_name = request.POST.get('crop_name')
        planting_date_str = request.POST.get('planting_date')
        batch_id = request.POST.get('batch_id', f'batch-{date.today().strftime("%Y%m%d")}')
        notes = request.POST.get('notes', '')

        # Get user_id first for image upload
        from .dynamodb_helper import get_user_id_from_token
        user_id = get_user_id_from_token(request)
        
        # Image upload logic - organized by user_id in S3
        image_url = ""
        if 'image' in request.FILES and request.FILES['image'].name:
            from .s3_helper import upload_planting_image
            if user_id:
                image_url = upload_planting_image(request.FILES['image'], user_id)
            else:
                logger.warning('Cannot upload image: user not authenticated')

        if not crop_name or not planting_date_str:
            return redirect('index')

        planting_date = date.fromisoformat(planting_date_str)

        plant_data = load_plant_data()
        calculate = _get_calculate_plan()
        calculated_plan = calculate(crop_name, planting_date, plant_data)

        # Convert due_date to ISO strings for storage
        for task in calculated_plan:
            if 'due_date' in task and isinstance(task['due_date'], date):
                task['due_date'] = task['due_date'].isoformat()

        # Save planting (similar to original simple code, but with DynamoDB/S3)
        from .dynamodb_helper import save_planting_to_dynamodb, get_user_id_from_token
        
        # Get user_id if not already retrieved
        if not user_id:
            user_id = get_user_id_from_token(request)
        
        # Create new planting (like original code) - always create it
        new_planting = {
            'crop_name': crop_name,
            'planting_date': planting_date.isoformat(),
            'batch_id': batch_id,
            'notes': notes,
            'plan': calculated_plan,
            'image_url': image_url
        }
        
        logger.info('Saving planting for user: %s', user_id if user_id else 'None')
        logger.info('Crop: %s, Planted on: %s', crop_name, planting_date)
        logger.info('Calculated Plan: %d tasks', len(calculated_plan))
        
        # Try to save to DynamoDB if user_id exists (for persistence)
        if user_id:
            planting_id = save_planting_to_dynamodb(user_id, new_planting)
            if planting_id:
                logger.info('✓ Saved planting %s to DynamoDB', planting_id)
                new_planting['planting_id'] = planting_id
            else:
                logger.warning('Failed to save to DynamoDB, using session only')
        
        # Always save to session for immediate visibility (like original code)
        user_plantings = request.session.get('user_plantings', [])
        user_plantings.append(new_planting)
        request.session['user_plantings'] = user_plantings
        request.session.modified = True
        
        logger.info('Saved to session: Crop=%s, Date=%s, Total plantings=%d', crop_name, planting_date, len(user_plantings))

    return redirect('index')

def edit_planting_view(request, planting_id):
    """Edit planting view - loads from DynamoDB or session (like original simple code)"""
    from .dynamodb_helper import load_user_plantings, get_user_id_from_token
    
    user_id = get_user_id_from_token(request)
    
    # Load plantings (try DynamoDB first, then session - like index view)
    user_plantings = []
    if user_id:
        try:
            user_plantings = load_user_plantings(user_id)
        except Exception as e:
            logger.exception('Error loading from DynamoDB: %s', e)
    
    # If no DynamoDB data, use session
    if not user_plantings:
        user_plantings = request.session.get('user_plantings', [])
    
    # Check if planting_id is valid
    if planting_id >= len(user_plantings):
        logger.error('Planting index %d out of range (total: %d)', planting_id, len(user_plantings))
        return redirect('index')
    
    try:
        planting_to_edit = user_plantings[planting_id].copy()
        planting_to_edit['id'] = planting_id
        
        # Convert planting_date to string for form (if it's a date object)
        if 'planting_date' in planting_to_edit:
            planting_date = planting_to_edit['planting_date']
            if isinstance(planting_date, date):
                planting_to_edit['planting_date_str'] = planting_date.isoformat()
            elif isinstance(planting_date, str):
                # If it's already a string, try to parse it first to validate
                try:
                    # Try to parse as ISO date to ensure it's valid
                    date.fromisoformat(planting_date)
                    planting_to_edit['planting_date_str'] = planting_date
                except (ValueError, TypeError):
                    planting_to_edit['planting_date_str'] = str(planting_date)
            else:
                planting_to_edit['planting_date_str'] = str(planting_date)
        else:
            planting_to_edit['planting_date_str'] = ''
        
        # Ensure all fields have default values for the form
        planting_to_edit.setdefault('crop_name', '')
        planting_to_edit.setdefault('batch_id', '')
        planting_to_edit.setdefault('notes', '')
        planting_to_edit.setdefault('image_url', '')
        
        logger.info('Loading planting for edit: id=%d, crop=%s, date=%s', 
                   planting_id, planting_to_edit.get('crop_name'), planting_to_edit.get('planting_date_str'))
    except (IndexError, KeyError) as e:
        logger.exception('Error getting planting to edit: %s', e)
        return redirect('index')

    plant_data = load_plant_data()
    context = {
        'plant_names': [p['name'] for p in plant_data['plants']],
        'planting': planting_to_edit,
        'is_editing': True
    }
    return render(request, 'tracker/edit.html', context)

def update_planting(request, planting_id):
    """Update planting - works with both DynamoDB and session (like original simple code)"""
    if request.method == 'POST':
        from .dynamodb_helper import load_user_plantings, save_planting_to_dynamodb, get_user_id_from_token
        from .s3_helper import upload_planting_image, delete_image_from_s3
        
        user_id = get_user_id_from_token(request)
        
        # Load plantings (try DynamoDB first, then session)
        user_plantings = []
        if user_id:
            try:
                user_plantings = load_user_plantings(user_id)
            except Exception as e:
                logger.exception('Error loading from DynamoDB: %s', e)
        
        # If no DynamoDB data, use session
        if not user_plantings:
            user_plantings = request.session.get('user_plantings', [])
        
        # Check if planting_id is valid
        if planting_id >= len(user_plantings):
            logger.error('Planting index %d out of range (total: %d)', planting_id, len(user_plantings))
            return redirect('index')
        
        # Get the existing planting
        existing_planting = user_plantings[planting_id]
        actual_planting_id = existing_planting.get('planting_id')

        # Get form values, but preserve old values if not provided or changed
        crop_name = request.POST.get('crop_name') or existing_planting.get('crop_name', '')
        planting_date_str = request.POST.get('planting_date') or existing_planting.get('planting_date', '')
        batch_id = request.POST.get('batch_id') or existing_planting.get('batch_id', f'batch-{date.today().strftime("%Y%m%d")}')
        notes = request.POST.get('notes', '') or existing_planting.get('notes', '')

        # Handle image upload - only update if new image is uploaded
        image_url = existing_planting.get('image_url', '')
        if 'image' in request.FILES and request.FILES['image'].name:
            # Delete old image if it exists
            old_image_url = image_url
            if old_image_url:
                delete_image_from_s3(old_image_url)
            
            # Upload new image (if user_id exists)
            if user_id:
                image_url = upload_planting_image(request.FILES['image'], user_id)
                logger.info('Uploaded new image for planting: %s', image_url)
            else:
                logger.warning('Cannot upload image: user not authenticated')
        else:
            # No new image uploaded - preserve existing image URL
            logger.info('No new image uploaded, preserving existing image: %s', image_url)

        if not crop_name or not planting_date_str:
            logger.error('Missing required fields: crop_name=%s, planting_date_str=%s', crop_name, planting_date_str)
            return redirect('index')

        # Parse planting date
        if isinstance(planting_date_str, str):
            planting_date = date.fromisoformat(planting_date_str)
        elif isinstance(planting_date_str, date):
            planting_date = planting_date_str
        else:
            logger.error('Invalid planting_date format: %s', planting_date_str)
            return redirect('index')

        # Recalculate plan based on updated crop and date
        plant_data = load_plant_data()
        calculate = _get_calculate_plan()
        calculated_plan = calculate(crop_name, planting_date, plant_data)

        # Convert due_date to ISO strings for storage
        for task in calculated_plan:
            if 'due_date' in task and isinstance(task['due_date'], date):
                task['due_date'] = task['due_date'].isoformat()

        # Update planting with all fields (preserving existing values where applicable)
        updated_planting = {
            'crop_name': crop_name,
            'planting_date': planting_date.isoformat() if isinstance(planting_date, date) else str(planting_date),
            'batch_id': batch_id,
            'notes': notes,
            'plan': calculated_plan,
            'image_url': image_url  # Will be existing URL if no new image uploaded
        }
        
        # Preserve planting_id if it exists
        if actual_planting_id:
            updated_planting['planting_id'] = actual_planting_id
        
        # Save to DynamoDB if user_id exists
        if user_id and actual_planting_id:
            if save_planting_to_dynamodb(user_id, updated_planting):
                logger.info('✓ Successfully updated planting %s in DynamoDB', actual_planting_id)
            else:
                logger.warning('Failed to update in DynamoDB, updating session only')
        
        # Always update session (like original simple code)
        user_plantings[planting_id] = updated_planting
        request.session['user_plantings'] = user_plantings
        request.session.modified = True
        logger.info('Updated planting at index %d in session', planting_id)

    return redirect('index')

def delete_planting(request, planting_id):
    """Delete planting - works with both DynamoDB and session (like original simple code)"""
    if request.method == 'POST':
        from .dynamodb_helper import load_user_plantings, delete_planting_from_dynamodb, get_user_id_from_token
        from .s3_helper import delete_image_from_s3
        
        user_id = get_user_id_from_token(request)
        
        # Load plantings (try DynamoDB first, then session)
        user_plantings = []
        if user_id:
            try:
                user_plantings = load_user_plantings(user_id)
            except Exception as e:
                logger.exception('Error loading from DynamoDB: %s', e)
        
        # If no DynamoDB data, use session
        if not user_plantings:
            user_plantings = request.session.get('user_plantings', [])
        
        # Check if planting_id is valid
        if planting_id >= len(user_plantings):
            logger.error('Planting index %d out of range (total: %d)', planting_id, len(user_plantings))
            return redirect('index')
        
        try:
            # Get the planting to delete
            planting_to_delete = user_plantings[planting_id]
            actual_planting_id = planting_to_delete.get('planting_id')
            image_url = planting_to_delete.get('image_url', '')
            
            # Delete image from S3 if it exists
            if image_url:
                delete_image_from_s3(image_url)
                logger.info('Deleted image from S3: %s', image_url)
            
            # Delete from DynamoDB if user_id and planting_id exist
            if user_id and actual_planting_id:
                if delete_planting_from_dynamodb(actual_planting_id):
                    logger.info('✓ Successfully deleted planting %s from DynamoDB', actual_planting_id)
                else:
                    logger.warning('Failed to delete from DynamoDB, deleting from session only')
            
            # Always delete from session (like original simple code)
            user_plantings.pop(planting_id)
            request.session['user_plantings'] = user_plantings
            request.session.modified = True
            logger.info('Deleted planting at index %d from session', planting_id)
            
        except (IndexError, KeyError) as e:
            logger.exception('Error deleting planting: %s', e)
    
    return redirect('index')


def cognito_login(request):
    """Redirect user to Cognito Hosted UI login."""
    from .cognito import build_authorize_url
    # Build the actual redirect URI from the request to ensure it matches exactly
    # Use the callback URL: https://3.235.196.246.nip.io/auth/callback/
    callback_url = request.build_absolute_uri('/auth/callback/')
    # Remove query parameters if any
    from urllib.parse import urlparse, urlunparse
    parsed = urlparse(callback_url)
    callback_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', '', ''))
    url = build_authorize_url(redirect_uri=callback_url)
    logger.info('Cognito login: Redirecting to Cognito with redirect_uri: %s', callback_url)
    return redirect(url)


def cognito_logout(request):
    """Logout user by clearing Cognito tokens and redirecting to login page."""
    # Clear all Cognito tokens from session
    request.session.pop('id_token', None)
    request.session.pop('access_token', None)
    request.session.pop('refresh_token', None)
    request.session.pop('cognito_tokens', None)
    
    logger.info('Cognito logout: Cleared tokens from session, redirecting to login')
    
    # Redirect to login page
    return redirect('login')  # Redirects to /login/


def cognito_callback(request):
    """Handle callback from Cognito Hosted UI, exchange code for tokens."""
    import requests
    from django.http import HttpResponse
    from django.db import OperationalError

    logger.info('Cognito callback received for path: %s', request.path)
    logger.info('Cognito callback query params: %s', request.GET.dict())
    
    # Check for error responses from Cognito first
    error = request.GET.get('error')
    error_description = request.GET.get('error_description')
    if error:
        logger.error('Cognito callback error: %s - %s', error, error_description)
        # For invalid_scope errors, provide helpful message
        if error == 'invalid_scope':
            error_msg = f"Authentication error: Invalid scope. Please check Cognito app client settings. Details: {error_description or error}"
        else:
            error_msg = f"Authentication error: {error_description or error}"
        # Redirect to home with error message
        from urllib.parse import quote
        return redirect(f'/?auth_error={quote(error_msg)}')
    
    code = request.GET.get('code')
    if not code:
        logger.warning('Cognito callback: No code provided and no error - unexpected response')
        return HttpResponse("No code provided. Please try logging in again.", status=400)

    # Get the actual redirect URI that was used (from the request)
    # This must match exactly what was sent in the authorization request
    actual_redirect_uri = request.build_absolute_uri(request.path)
    # Remove query parameters from the redirect URI
    from urllib.parse import urlparse, urlunparse
    parsed = urlparse(actual_redirect_uri)
    actual_redirect_uri = urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', '', ''))
    
    # Use the actual redirect URI from the request, or fall back to settings
    redirect_uri = actual_redirect_uri or settings.COGNITO_REDIRECT_URI
    
    logger.info('Cognito callback: Using redirect_uri: %s (from settings: %s)', redirect_uri, settings.COGNITO_REDIRECT_URI)
    
    token_url = f"https://{settings.COGNITO_DOMAIN}/oauth2/token"

    data = {
        'grant_type': 'authorization_code',
        'client_id': settings.COGNITO_CLIENT_ID,
        'code': code,
        'redirect_uri': redirect_uri  # Use the actual redirect URI
    }

    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }

    try:
        response = requests.post(token_url, data=data, headers=headers, auth=(settings.COGNITO_CLIENT_ID, settings.COGNITO_CLIENT_SECRET) if settings.COGNITO_CLIENT_SECRET else None)
    except Exception as e:
        logger.exception('Error calling Cognito token endpoint: %s', e)
        return HttpResponse(f"Error fetching tokens: {str(e)}", status=500)
    
    if response.status_code != 200:
        error_text = response.text
        logger.error('Cognito token exchange failed: %s - %s', response.status_code, error_text)
        logger.error('Token exchange details - redirect_uri: %s, client_id: %s', redirect_uri, settings.COGNITO_CLIENT_ID)
        
        # Handle invalid_grant error specifically
        try:
            error_data = response.json()
            if error_data.get('error') == 'invalid_grant':
                error_msg = (
                    "The authorization code is invalid or has expired. This usually happens if:\n"
                    "1. The code was already used (codes are single-use)\n"
                    "2. The code expired (try logging in again)\n"
                    "3. The redirect_uri doesn't match exactly between authorization and token exchange\n"
                    f"Current redirect_uri: {redirect_uri}\n"
                    f"Expected redirect_uri in settings: {settings.COGNITO_REDIRECT_URI}\n"
                    "Please try logging in again."
                )
                return HttpResponse(error_msg, status=400, content_type='text/plain')
        except:
            pass
        
        return HttpResponse(f"Error fetching tokens: {error_text}", status=response.status_code)

    tokens = response.json()
    # tokens contain: access_token, id_token, refresh_token
    logger.info('Cognito callback: Tokens received successfully')
    
    try:
        # Save all tokens to session for future use
        request.session['id_token'] = tokens.get('id_token')
        request.session['access_token'] = tokens.get('access_token')
        # Also save refresh_token for token refresh
        if tokens.get('refresh_token'):
            request.session['refresh_token'] = tokens.get('refresh_token')
        # Save in old format for compatibility
        request.session['cognito_tokens'] = {
            'id_token': tokens.get('id_token'),
            'access_token': tokens.get('access_token'),
            'refresh_token': tokens.get('refresh_token'),
        }
        request.session.modified = True  # Ensure session is saved
        logger.info('Cognito callback: Tokens saved to session')
        
        # Save user data to DynamoDB users table (MUST HAPPEN AFTER TOKENS ARE SAVED)
        from .dynamodb_helper import save_user_to_dynamodb
        
        # Extract user data from the ID token directly
        try:
            from jose import jwt
            id_token = tokens.get('id_token')
            if not id_token:
                logger.error('✗ No ID token in Cognito response - cannot save user data')
            else:
                # Decode token to get user data
                user_data = jwt.decode(id_token, options={"verify_signature": False})
                logger.info('Extracted user data from token. Available keys: %s', list(user_data.keys()))
                
                # Log user information for debugging
                username = user_data.get('username') or user_data.get('preferred_username') or user_data.get('sub') or user_data.get('email')
                logger.info('User info: username=%s, email=%s, sub=%s', 
                          username,
                          user_data.get('email', 'N/A'),
                          user_data.get('sub', 'N/A'))
                
                # Save to DynamoDB
                from .dynamodb_helper import DYNAMODB_USERS_TABLE_NAME
                logger.info('Attempting to save user to DynamoDB users table...')
                if save_user_to_dynamodb(user_data):
                    logger.info('✓✓✓ SUCCESS: User data saved to DynamoDB users table')
                else:
                    logger.error('✗✗✗ FAILED: User data NOT saved to DynamoDB users table')
                    logger.error('Troubleshooting steps:')
                    logger.error('  1. Check if DynamoDB "users" table exists in AWS Console')
                    logger.error('  2. Verify AWS credentials in .env file (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)')
                    logger.error('  3. Check IAM permissions: dynamodb:PutItem, dynamodb:GetItem, dynamodb:DescribeTable')
                    logger.error('  4. Verify table name matches: %s', DYNAMODB_USERS_TABLE_NAME)
                    logger.error('  5. Run: python scripts/create_users_table.py to create the table')
        except Exception as user_save_error:
            logger.exception('✗ Exception while saving user data to DynamoDB: %s', user_save_error)
        
        logger.info('Cognito callback: Redirecting to homepage')
    except OperationalError as e:
        logger.exception('Database error saving session: %s', e)
        # Return tokens in response if we can't save to session
        return HttpResponse(f"Authentication successful but session save failed. Please check database connection. Tokens received: {bool(tokens.get('id_token'))}", status=503)
    except Exception as e:
        logger.exception('Error saving session: %s', e)
        return HttpResponse(f"Error saving session: {str(e)}", status=500)
    
    # Redirect to homepage - ensure this doesn't trigger login_required
    return redirect('/')  # redirect to homepage after login


def profile(request):
    if not hasattr(request, "user_data"):
        return JsonResponse({"error": "Unauthorized"}, status=401)

    return JsonResponse({
        "email": request.user_data["email"],
        "sub": request.user_data["sub"]
    })
    
# ========================
# USER SIGNUP VIEW
# ========================
def signup(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            email = form.cleaned_data['email']
            
            try:
                # Create Django user
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=form.cleaned_data['password1'],
                )
                logger.info('✓ Django user created: username=%s, id=%s', username, user.id)
                
                UserProfile.objects.create(
                    user=user,
                    country=form.cleaned_data['country']
                )
                logger.info('✓ UserProfile created for: %s', username)
                
                # Save user to DynamoDB users table (CRITICAL - must happen)
                from .dynamodb_helper import save_user_to_dynamodb
                user_data = {
                    'username': username,
                    'email': email,
                    'sub': f'django_{user.id}',  # Use Django user ID as sub
                    'name': username,
                }
                
                logger.info('=' * 60)
                logger.info('ATTEMPTING TO SAVE USER TO DYNAMODB')
                logger.info('Username: %s', username)
                logger.info('Email: %s', email)
                logger.info('User ID (sub): django_%s', user.id)
                logger.info('AWS Access Key ID configured: %s', bool(settings.AWS_ACCESS_KEY_ID))
                logger.info('AWS Secret Key configured: %s', bool(settings.AWS_SECRET_ACCESS_KEY))
                logger.info('DynamoDB Table Name: %s', getattr(settings, 'DYNAMODB_USERS_TABLE_NAME', 'users'))
                logger.info('=' * 60)
                
                try:
                    save_result = save_user_to_dynamodb(user_data)
                    if save_result:
                        logger.info('✓✓✓ SUCCESS: User %s saved to DynamoDB users table', username)
                    else:
                        logger.error('✗✗✗ FAILED: User %s NOT saved to DynamoDB users table', username)
                        logger.error('Check logs above for error details')
                        logger.error('Troubleshooting:')
                        logger.error('  1. Verify AWS credentials in .env: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY')
                        logger.error('  2. Check IAM permissions: dynamodb:PutItem, dynamodb:GetItem, dynamodb:DescribeTable')
                        logger.error('  3. Verify table exists: aws dynamodb describe-table --table-name users --region us-east-1')
                        logger.error('  4. Check table name matches: %s', getattr(settings, 'DYNAMODB_USERS_TABLE_NAME', 'users'))
                except Exception as dynamo_error:
                    logger.exception('EXCEPTION while saving to DynamoDB: %s', dynamo_error)
                    # Continue anyway - don't block signup if DynamoDB fails
                
                # Authenticate and login
                user = authenticate(username=username, password=form.cleaned_data['password1'])
                if user is not None:
                    login(request, user)
                    logger.info('✓ User %s authenticated and logged in', username)
                else:
                    logger.error('✗ Failed to authenticate user %s after signup', username)
                
                return redirect('/')
                
            except Exception as e:
                logger.exception('Error during signup: %s', e)
                # Re-raise or handle as needed
                form.add_error(None, f'An error occurred during signup: {str(e)}')
    else:
        form = SignUpForm()
    return render(request, 'registration/signup.html', {'form': form})

@login_required
def profile(request):
    """Handle profile view and profile updates."""
    if request.method == 'POST':
        # Handle profile update
        user = request.user
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        # Update username if provided and different
        if username and username != user.username:
            user.username = username
            user.save()
            logger.info('Profile updated: username changed to %s', username)
        
        # Update email if provided and different
        if email and email != user.email:
            user.email = email
            user.save()
            logger.info('Profile updated: email changed to %s', email)
        
        # Update password if provided
        if password:
            user.set_password(password)
            user.save()
            logger.info('Profile updated: password changed')
        
        # Redirect to home after saving
        return redirect('/')
    
    # GET request - show profile page
    return render(request, 'profile.html')

def login_view(request):
    """
    Login view - shows login page with Cognito login option.
    If user already has tokens, redirects to home page.
    Supports both Cognito login (recommended) and traditional Django login (fallback).
    """
    from .dynamodb_helper import get_user_id_from_token
    
    # Check if user is already authenticated (has Cognito tokens)
    user_id = get_user_id_from_token(request)
    if user_id:
        logger.info('User already authenticated (user_id: %s), redirecting to home', user_id)
        return redirect('index')
    
    # If POST request (traditional Django login), try to authenticate
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        if username and password:
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                logger.info('User %s logged in via Django auth', username)
                return redirect('index')
            else:
                # Failed authentication - show error
                from django.contrib.auth.forms import AuthenticationForm
                form = AuthenticationForm()
                form.errors['__all__'] = form.error_messages['invalid_login']
                return render(request, 'registration/login.html', {'form': form})
    
    # For GET requests, show login page with Cognito login option
    return render(request, 'registration/login.html')


def toggle_notifications(request):
    """
    API endpoint to toggle user's notification preferences.
    
    POST /api/toggle-notifications/
    Body: {"enabled": true/false}
    """
    from .dynamodb_helper import get_user_data_from_token, update_user_notification_preference
    from .sns_helper import subscribe_email_to_topic
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method allowed'}, status=405)
    
    try:
        user_data = get_user_data_from_token(request)
        if not user_data:
            return JsonResponse({'error': 'User not authenticated'}, status=401)
        
        username = user_data.get('username') or user_data.get('preferred_username') or user_data.get('sub')
        email = user_data.get('email')
        
        if not username:
            return JsonResponse({'error': 'Username not found'}, status=400)
        
        # Get enabled status from request
        import json
        try:
            body = json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            body = request.POST
        
        enabled = body.get('enabled', True)
        if isinstance(enabled, str):
            enabled = enabled.lower() == 'true'
        
        # Update notification preference in DynamoDB
        success = update_user_notification_preference(username, enabled)
        if not success:
            return JsonResponse({'error': 'Failed to update notification preference'}, status=500)
        
        # If enabling notifications and email exists, subscribe to SNS topic
        if enabled and email:
            subscribe_email_to_topic(email)
            logger.info('✓ Subscribed %s to SNS topic for notifications', email)
        
        return JsonResponse({
            'success': True,
            'notifications_enabled': enabled,
            'message': 'Notification preferences updated successfully'
        })
        
    except Exception as e:
        logger.exception('Error toggling notifications: %s', e)
        return JsonResponse({'error': str(e)}, status=500)