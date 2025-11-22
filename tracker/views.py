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
    # Load plantings from DynamoDB using user ID from Cognito token
    from .dynamodb_helper import load_user_plantings, get_user_id_from_token, migrate_session_to_dynamodb
    
    # Initialize user_plantings to empty list as default
    user_plantings = []
    
    try:
        user_id = get_user_id_from_token(request)
        logger.info('Index view: user_id extracted: %s', user_id if user_id else 'None')
        
        # Always check session first - it's the most reliable for immediate display
        session_plantings = request.session.get('user_plantings', [])
        logger.info('Session contains %d plantings', len(session_plantings))
        
        if user_id:
            logger.info('Loading plantings from DynamoDB for user_id: %s', user_id)
            # Load from DynamoDB
            dynamodb_plantings = load_user_plantings(user_id)
            logger.info('Loaded %d plantings from DynamoDB for user %s', len(dynamodb_plantings), user_id)
            
            # Use DynamoDB data if available, otherwise use session
            if dynamodb_plantings:
                user_plantings = dynamodb_plantings
                # Clear session if DynamoDB has data
                if session_plantings:
                    request.session.pop('user_plantings', None)
                    logger.info('Using DynamoDB data (%d plantings), cleared session', len(user_plantings))
            elif session_plantings:
                # DynamoDB is empty but session has data - use session and try to migrate
                user_plantings = session_plantings
                logger.info('Using session data (%d plantings) - DynamoDB is empty', len(user_plantings))
                # Try to migrate to DynamoDB in background (don't block display)
                try:
                    if migrate_session_to_dynamodb(user_id, session_plantings):
                        logger.info('Successfully migrated %d plantings to DynamoDB', len(session_plantings))
                        request.session.pop('user_plantings', None)
                except Exception as migrate_error:
                    logger.warning('Migration failed (non-critical): %s', migrate_error)
            else:
                # Both are empty
                user_plantings = []
                logger.info('No plantings found in DynamoDB or session')
        else:
            # No user ID - use session only
            logger.warning('No user_id found - using session data only')
            user_plantings = session_plantings
            if user_plantings:
                logger.info('Using %d plantings from session (user not authenticated)', len(user_plantings))
            else:
                logger.info('No plantings found in session')
    except Exception as e:
        logger.exception('Error in index view while loading plantings: %s', e)
        # Fallback to session if there's an error
        user_plantings = request.session.get('user_plantings', [])
        logger.warning('Using session fallback due to error: %d plantings', len(user_plantings))
    
    logger.info('Final plantings count for display: %d', len(user_plantings))
    
    today = date.today()
    
    ongoing, upcoming, past = [], [], []

    # Process each planting with error handling
    for i, planting_data in enumerate(user_plantings):
        try:
            planting = planting_data.copy() # Work with a copy
            planting['id'] = i

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
    context = {'ongoing': ongoing, 'upcoming': upcoming, 'past': past}
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

        # Save to DynamoDB - REQUIRED for logged-in users
        from .dynamodb_helper import load_user_plantings, save_planting_to_dynamodb
        
        # user_id already retrieved above for image upload
        if not user_id:
            logger.error('Cannot save planting: user not authenticated (no user_id from token)')
            return redirect('index')
        
        logger.info('Saving planting for user_id: %s', user_id)
        
        # Create new planting
        new_planting = {
            'crop_name': crop_name,
            'planting_date': planting_date.isoformat(),
            'batch_id': batch_id,
            'notes': notes,
            'plan': calculated_plan,
            'image_url': image_url
        }
        
        # Save individual planting to DynamoDB
        planting_id = save_planting_to_dynamodb(user_id, new_planting)
        if planting_id:
            logger.info('✓ Successfully saved planting %s to DynamoDB for user %s', planting_id, user_id)
            new_planting['planting_id'] = planting_id
        else:
            logger.error('✗ FAILED to save planting to DynamoDB for user %s', user_id)
            logger.warning('Data will be saved to session only. Please check DynamoDB plantings table.')
        
        # Always save to session for immediate visibility
        user_plantings = load_user_plantings(user_id)
        # If DynamoDB save failed, add to session list
        if not planting_id:
            user_plantings = request.session.get('user_plantings', [])
            user_plantings.append(new_planting)
        else:
            # Reload from DynamoDB to get the saved planting
            user_plantings = load_user_plantings(user_id)
        
        request.session['user_plantings'] = user_plantings
        request.session.modified = True
        logger.info('Saved %d plantings to session for immediate display', len(user_plantings))

    return redirect('index')

def edit_planting_view(request, planting_id):
    from .dynamodb_helper import load_user_plantings, get_user_id_from_token
    
    user_id = get_user_id_from_token(request)
    if not user_id:
        logger.error('Cannot edit planting: user not authenticated')
        return redirect('index')
    
    user_plantings = load_user_plantings(user_id)
    
    try:
        planting_to_edit = user_plantings[planting_id].copy()
        planting_to_edit['id'] = planting_id
        # This conversion is for the form value, which is correct
        planting_to_edit['planting_date_str'] = planting_to_edit['planting_date']
    except (IndexError, KeyError):
        return redirect('index')

    plant_data = load_plant_data()
    context = {
        'plant_names': [p['name'] for p in plant_data['plants']],
        'planting': planting_to_edit,
        'is_editing': True
    }
    return render(request, 'tracker/edit.html', context)

def update_planting(request, planting_id):
    if request.method == 'POST':
        from .dynamodb_helper import load_user_plantings, save_planting_to_dynamodb, get_user_id_from_token
        
        user_id = get_user_id_from_token(request)
        if not user_id:
            logger.error('Cannot update planting: user not authenticated')
            return redirect('index')
        
        user_plantings = load_user_plantings(user_id)
        
        # planting_id is the index in the list
        if planting_id >= len(user_plantings):
            return redirect('index')
        
        # Get the actual planting_id from the database
        actual_planting_id = user_plantings[planting_id].get('planting_id')
        if not actual_planting_id:
            logger.error('Planting at index %d has no planting_id', planting_id)
            return redirect('index')

        crop_name = request.POST.get('crop_name')
        planting_date_str = request.POST.get('planting_date')
        batch_id = request.POST.get('batch_id', f'batch-{date.today().strftime("%Y%m%d")}')
        notes = request.POST.get('notes', '')

        image_url = user_plantings[planting_id].get('image_url', '')
        if 'image' in request.FILES and request.FILES['image'].name:
            # Upload new image to S3 organized by user_id
            from .s3_helper import upload_planting_image, delete_image_from_s3
            
            # Delete old image if it exists
            old_image_url = image_url
            if old_image_url:
                delete_image_from_s3(old_image_url)
            
            # Upload new image
            image_url = upload_planting_image(request.FILES['image'], user_id)

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

        # Update planting with actual planting_id
        updated_planting = {
            'planting_id': actual_planting_id,
            'crop_name': crop_name,
            'planting_date': planting_date.isoformat(),
            'batch_id': batch_id,
            'notes': notes,
            'plan': calculated_plan,
            'image_url': image_url
        }
        
        # Save updated planting to DynamoDB
        if save_planting_to_dynamodb(user_id, updated_planting):
            logger.info('✓ Successfully updated planting %s in DynamoDB for user %s', actual_planting_id, user_id)
            # Update session
            user_plantings[planting_id] = updated_planting
            request.session['user_plantings'] = user_plantings
            request.session.modified = True
        else:
            logger.error('Failed to update planting in DynamoDB for user %s', user_id)

    return redirect('index')

def delete_planting(request, planting_id):
    if request.method == 'POST':
        from .dynamodb_helper import load_user_plantings, delete_planting_from_dynamodb, get_user_id_from_token
        from .s3_helper import delete_image_from_s3
        
        user_id = get_user_id_from_token(request)
        if not user_id:
            logger.error('Cannot delete planting: user not authenticated')
            return redirect('index')
        
        user_plantings = load_user_plantings(user_id)
        
        try:
            # planting_id is the index in the list
            if planting_id >= len(user_plantings):
                return redirect('index')
            
            # Get the actual planting_id from the database
            planting_to_delete = user_plantings[planting_id]
            actual_planting_id = planting_to_delete.get('planting_id')
            image_url = planting_to_delete.get('image_url', '')
            
            # Delete image from S3 if it exists
            if image_url:
                delete_image_from_s3(image_url)
                logger.info('Deleted image from S3: %s', image_url)
            
            # Delete planting from DynamoDB using actual planting_id
            if actual_planting_id:
                if delete_planting_from_dynamodb(actual_planting_id):
                    logger.info('✓ Successfully deleted planting %s from DynamoDB for user %s', actual_planting_id, user_id)
                    # Update session
                    user_plantings.pop(planting_id)
                    request.session['user_plantings'] = user_plantings
                    request.session.modified = True
                else:
                    logger.error('✗ Failed to delete planting from DynamoDB for user %s', user_id)
            else:
                logger.error('Planting at index %d has no planting_id', planting_id)
        except (IndexError, KeyError) as e:
            logger.warning('Error deleting planting: %s', e)
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
        logger.info('Cognito callback: Tokens saved to session')
        
        # Save user data to DynamoDB users table
        from .dynamodb_helper import get_user_data_from_token, save_user_to_dynamodb
        user_data = get_user_data_from_token(request)
        if user_data:
            logger.info('Saving user data to DynamoDB users table')
            if save_user_to_dynamodb(user_data):
                logger.info('✓ User data saved to DynamoDB users table')
            else:
                logger.warning('Failed to save user data to DynamoDB (non-critical)')
        else:
            logger.warning('Could not extract user data from token for DynamoDB save')
        
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
            user = User.objects.create_user(
                username=form.cleaned_data['username'],
                email=form.cleaned_data['email'],
                password=form.cleaned_data['password1'],
            )
            UserProfile.objects.create(
                user=user,
                country=form.cleaned_data['country']
            )
            user = authenticate(username=form.cleaned_data['username'], password=form.cleaned_data['password1'])
            if user is not None:
                login(request, user)
            return redirect('/')
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
    # Basic example; improve as needed!
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('index')  # or your homepage
    return render(request, 'registration/login.html')