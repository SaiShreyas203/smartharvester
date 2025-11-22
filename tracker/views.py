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
    from .dynamodb_helper import load_user_plantings, get_user_id_from_token
    
    user_id = get_user_id_from_token(request)
    if user_id:
        user_plantings = load_user_plantings(user_id)
    else:
        # Fallback to session for backward compatibility or unauthenticated users
        user_plantings = request.session.get('user_plantings', [])
    
    today = date.today()
    
    ongoing, upcoming, past = [], [], []

    for i, planting_data in enumerate(user_plantings):
        planting = planting_data.copy() # Work with a copy
        planting['id'] = i

        # Convert the main planting_date
        planting['planting_date'] = date.fromisoformat(planting['planting_date'])

        # --- FIX: Convert due_dates within the plan ---
        for task in planting.get('plan', []):
            if 'due_date' in task:
                task['due_date'] = date.fromisoformat(task['due_date'])

        harvest_task = next((task for task in reversed(planting.get('plan', [])) if 'due_date' in task), None)

        if harvest_task:
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

        # Image upload logic:
        image_url = ""
        if 'image' in request.FILES and request.FILES['image'].name:
            image_file = request.FILES['image']
            s3 = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=getattr(settings, 'AWS_S3_REGION_NAME', 'us-east-1')
            )
            extension = image_file.name.split('.')[-1]
            key = f"media/planting_images/{uuid.uuid4()}.{extension}"
            # NOTE: No ExtraArgs, no ACL set!
            s3.upload_fileobj(image_file, settings.AWS_STORAGE_BUCKET_NAME, key)
            image_url = f"https://{settings.AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/{key}"

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

        # Save to DynamoDB
        from .dynamodb_helper import load_user_plantings, save_user_plantings, get_user_id_from_token
        
        user_id = get_user_id_from_token(request)
        if user_id:
            # Load existing plantings from DynamoDB
            user_plantings = load_user_plantings(user_id)
            # Add new planting
            user_plantings.append({
                'crop_name': crop_name,
                'planting_date': planting_date.isoformat(),
                'batch_id': batch_id,
                'notes': notes,
                'plan': calculated_plan,
                'image_url': image_url
            })
            # Save back to DynamoDB
            save_user_plantings(user_id, user_plantings)
        else:
            # Fallback to session for backward compatibility
            user_plantings = request.session.get('user_plantings', [])
            user_plantings.append({
                'crop_name': crop_name,
                'planting_date': planting_date.isoformat(),
                'batch_id': batch_id,
                'notes': notes,
                'plan': calculated_plan,
                'image_url': image_url
            })
            request.session['user_plantings'] = user_plantings

    return redirect('index')

def edit_planting_view(request, planting_id):
    from .dynamodb_helper import load_user_plantings, get_user_id_from_token
    
    user_id = get_user_id_from_token(request)
    if user_id:
        user_plantings = load_user_plantings(user_id)
    else:
        user_plantings = request.session.get('user_plantings', [])
    
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
        from .dynamodb_helper import load_user_plantings, save_user_plantings, get_user_id_from_token
        
        user_id = get_user_id_from_token(request)
        if user_id:
            user_plantings = load_user_plantings(user_id)
        else:
            user_plantings = request.session.get('user_plantings', [])
        
        if planting_id >= len(user_plantings):
            return redirect('index')

        crop_name = request.POST.get('crop_name')
        planting_date_str = request.POST.get('planting_date')
        batch_id = request.POST.get('batch_id', f'batch-{date.today().strftime("%Y%m%d")}')
        notes = request.POST.get('notes', '')

        image_url = user_plantings[planting_id].get('image_url', '')
        if 'image' in request.FILES and request.FILES['image'].name:
            # Upload new image to S3:
            image_file = request.FILES['image']
            s3 = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=getattr(settings, 'AWS_S3_REGION_NAME', 'us-east-1')
            )
            extension = image_file.name.split('.')[-1]
            key = f"media/planting_images/{uuid.uuid4()}.{extension}"
            s3.upload_fileobj(image_file, settings.AWS_STORAGE_BUCKET_NAME, key)
            image_url = f"https://{settings.AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/{key}"

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

        user_plantings[planting_id] = {
            'crop_name': crop_name,
            'planting_date': planting_date.isoformat(),
            'batch_id': batch_id,
            'notes': notes,
            'plan': calculated_plan,
            'image_url': image_url
        }
        
        # Save to DynamoDB or session
        if user_id:
            save_user_plantings(user_id, user_plantings)
        else:
            request.session['user_plantings'] = user_plantings

    return redirect('index')

def delete_planting(request, planting_id):
    if request.method == 'POST':
        from .dynamodb_helper import load_user_plantings, save_user_plantings, get_user_id_from_token
        
        user_id = get_user_id_from_token(request)
        if user_id:
            user_plantings = load_user_plantings(user_id)
        else:
            user_plantings = request.session.get('user_plantings', [])
        
        try:
            del user_plantings[planting_id]
            # Save to DynamoDB or session
            if user_id:
                save_user_plantings(user_id, user_plantings)
            else:
                request.session['user_plantings'] = user_plantings
        except IndexError:
            pass
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
        logger.info('Cognito callback: Tokens saved to session, redirecting to homepage')
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