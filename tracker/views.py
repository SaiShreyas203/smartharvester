import json
import os
import uuid
import logging
from datetime import date, timedelta

from django.shortcuts import render, redirect
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User

logger = logging.getLogger(__name__)

# local imports
from .forms import SignUpForm
from .models import UserProfile

# Lazy import helper will locate the plan function at call time.
def _get_calculate_plan():
    """Return a callable to calculate a plan.

    Tries several common function names in `smartharvest_plan.plan` and
    returns the first callable found. If the module can't be imported or
    no callable is found, returns a fallback that returns an empty list.
    """
    try:
        import importlib
        mod = importlib.import_module('smartharvest_plan.plan')
        for name in ('calculate_plan', 'generate_plan', 'create_plan', 'build_plan', 'plan'):
            if hasattr(mod, name):
                candidate = getattr(mod, name)
                if callable(candidate):
                    logger.info('Using %s from smartharvest_plan.plan', name)
                    return candidate
        logger.warning('Imported smartharvest_plan.plan but no callable plan function found')
    except Exception as e:
        logger.warning('Could not import smartharvest_plan.plan: %s', e)

    def _fallback(*args, **kwargs):
        return []

    return _fallback

DATA_FILE_PATH = os.path.join(settings.BASE_DIR, 'tracker', 'data.json')


def load_plant_data():
    with open(DATA_FILE_PATH, 'r') as f:
        return json.load(f)


# Small dynamic importer to try multiple helper names from tracker.dynamodb_helper
def _get_helper(*names):
    """
    Try to import functions by name from tracker.dynamodb_helper.
    Returns the first callable found or None.
    """
    for name in names:
        try:
            mod = __import__('tracker.dynamodb_helper', fromlist=[name])
            fn = getattr(mod, name, None)
            if fn:
                return fn
        except Exception:
            continue
    return None


def index(request):
    """
    Display the user's saved plantings.
    Loads per-user plantings from DynamoDB when possible, otherwise falls back to session storage.
    """
    # helpers (may or may not exist depending on which dynamodb_helper version is installed)
    load_user_plantings = _get_helper('load_user_plantings')
    get_user_id_from_token = _get_helper('get_user_id_from_token', 'get_user_id_from_request')
    get_user_data_from_token = _get_helper('get_user_data_from_token', 'get_user_id_from_token')
    get_user_notification_preference = _get_helper('get_user_notification_preference', 'get_notification_preference')

    user_plantings = []

    # Determine user id
    user_id = None
    try:
        if get_user_id_from_token:
            user_id = get_user_id_from_token(request)
        else:
            # Fallback: use django auth user id if logged in
            if hasattr(request, 'user') and getattr(request.user, 'is_authenticated', False):
                user_id = str(request.user.pk)
    except Exception as e:
        logger.exception('Error fetching user id: %s', e)

    logger.info('Index: user_id = %s', user_id if user_id else 'None')

    # Try to load from DynamoDB first if user_id exists
    if user_id and load_user_plantings:
        try:
            dynamodb_plantings = load_user_plantings(user_id)
            if dynamodb_plantings:
                user_plantings = dynamodb_plantings
                logger.info('Loaded %d plantings from DynamoDB', len(user_plantings))
        except Exception as e:
            logger.exception('Error loading from DynamoDB: %s', e)

    # If no DynamoDB data, use session
    if not user_plantings:
        session_plantings = request.session.get('user_plantings', [])
        if session_plantings:
            user_plantings = session_plantings
            logger.info('Using %d plantings from session', len(user_plantings))

    today = date.today()
    ongoing, upcoming, past = [], [], []

    # Process plantings - robust parsing for dates and image_url
    for i, planting_data in enumerate(user_plantings):
        try:
            planting = dict(planting_data)  # copy
            planting['id'] = i
            planting['image_url'] = planting.get('image_url') or planting_data.get('image_url', '') or ''

            # planting_date must be parsed (ISO string expected)
            if 'planting_date' in planting:
                if isinstance(planting['planting_date'], str):
                    planting['planting_date'] = date.fromisoformat(planting['planting_date'])
                elif isinstance(planting['planting_date'], date):
                    pass
                else:
                    logger.warning('Planting at index %d has unexpected planting_date type: %s', i, type(planting['planting_date']))
                    continue
            else:
                logger.warning('Planting at index %d missing planting_date, skipping', i)
                continue

            # Normalize plan due_date fields to date objects where possible
            for task in planting.get('plan', []):
                if 'due_date' in task and task['due_date']:
                    try:
                        if isinstance(task['due_date'], str):
                            task['due_date'] = date.fromisoformat(task['due_date'])
                    except (ValueError, TypeError) as e:
                        logger.warning('Error parsing due_date in planting %d: %s', i, e)
                        task['due_date'] = None

            # Determine harvest_date from last task that has due_date
            harvest_task = next((t for t in reversed(planting.get('plan', [])) if t.get('due_date')), None)
            if harvest_task and harvest_task.get('due_date'):
                harvest_date = harvest_task['due_date']
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
            continue

    logger.info('Processed plantings: ongoing=%d, upcoming=%d, past=%d', len(ongoing), len(upcoming), len(past))

    # Get user info and notification preference (best-effort)
    notifications_enabled = True
    user_email = None
    username = None
    try:
        user_data = None
        if get_user_data_from_token:
            try:
                user_data = get_user_data_from_token(request)
            except Exception:
                # If function expects a token string, try using session id_token
                try:
                    id_token = request.session.get('id_token')
                    user_data = get_user_data_from_token(id_token) if id_token else None
                except Exception:
                    user_data = None

        if not user_data and hasattr(request, 'user') and getattr(request.user, 'is_authenticated', False):
            # Best-effort: use Django user info
            user_email = request.user.email
            username = request.user.username

        if user_data:
            user_email = user_data.get('email') or user_email
            username = user_data.get('username') or user_data.get('preferred_username') or user_data.get('sub') or username
            if get_user_notification_preference and username:
                try:
                    notifications_enabled = get_user_notification_preference(username)
                except Exception:
                    logger.exception('Error getting notification preference for %s', username)
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
    """
    Save planting:
     - upload image to S3 (if provided) and set image_url
     - resolve username (table PK) and a stable user_id (Cognito sub or django_<pk>)
     - persist planting to DynamoDB (including username and user_id)
     - always save to session for immediate UI
    """
    if request.method != 'POST':
        return redirect('index')

    from datetime import date as _date
    import uuid
    import logging

    logger = logging.getLogger(__name__)

    crop_name = request.POST.get('crop_name')
    planting_date_str = request.POST.get('planting_date')
    # fixed quoting here: use double quotes for outer f-string so inner strftime uses single quotes
    batch_id = request.POST.get('batch_id', f"batch-{_date.today().strftime('%Y%m%d')}")
    notes = request.POST.get('notes', '')

    # Lazy helpers
    from .dynamodb_helper import get_user_id_from_token, get_user_data_from_token, save_planting_to_dynamodb
    from .s3_helper import upload_planting_image
    from .views_helpers import load_plant_data  # if you have a helper; otherwise use existing load_plant_data
    # If load_plant_data is in this module already, remove the import above.

    # Resolve stable user id (Cognito sub or django_<pk>) and username (users table PK)
    user_id = None
    username = None
    try:
        user_id = get_user_id_from_token(request)
        user_data = get_user_data_from_token(request)
        if user_data:
            username = user_data.get('username') or user_data.get('preferred_username') or user_data.get('email')
    except Exception:
        logger.exception("Error extracting user identity")

    # As a fallback, use Django authenticated user
    if not username and hasattr(request, 'user') and getattr(request.user, 'is_authenticated', False):
        username = getattr(request.user, 'username', None)
    if not user_id and hasattr(request, 'user') and getattr(request.user, 'is_authenticated', False):
        user_id = f"django_{getattr(request.user, 'pk', '')}"

    # Image upload
    image_url = ""
    if 'image' in request.FILES and request.FILES['image'].name:
        try:
            upload_owner = user_id or username or "anonymous"
            image_url = upload_planting_image(request.FILES['image'], upload_owner)
            logger.info("upload_planting_image -> %s", image_url)
        except Exception:
            logger.exception("Image upload failed")

    # Validate required fields
    if not crop_name or not planting_date_str:
        logger.error("Missing required fields in save_planting")
        return redirect('index')

    planting_date = _date.fromisoformat(planting_date_str)

    # Build plan
    plant_data = load_plant_data()
    calculate = _get_calculate_plan()
    calculated_plan = calculate(crop_name, planting_date, plant_data)

    # Convert internal due_date values to ISO strings for storage
    for task in calculated_plan:
        if 'due_date' in task and isinstance(task['due_date'], _date):
            task['due_date'] = task['due_date'].isoformat()

    # Compose planting dict with both username and stable user_id
    new_planting = {
        'crop_name': crop_name,
        'planting_date': planting_date.isoformat(),
        'batch_id': batch_id,
        'notes': notes,
        'plan': calculated_plan,
        'image_url': image_url,
        'user_id': user_id or (f"django_{getattr(request.user,'pk','')}" if getattr(request, 'user', None) and getattr(request.user, 'is_authenticated', False) else None),
        'username': username or (getattr(request.user, 'username', None) if getattr(request, 'user', None) else None)
    }

    # Ensure a local planting_id for session immediacy
    local_planting_id = str(uuid.uuid4())
    new_planting['planting_id'] = new_planting.get('planting_id') or local_planting_id

    # Persist to Dynamo if possible (best-effort)
    try:
        persisted_id = save_planting_to_dynamodb(new_planting)
        if persisted_id:
            new_planting['planting_id'] = persisted_id
            logger.info('Saved planting %s to DynamoDB', persisted_id)
        else:
            logger.warning('save_planting_to_dynamodb returned falsy; saved to session only')
    except Exception:
        logger.exception('Failed saving planting to DynamoDB, continuing with session-only')

    # Save to session for UI immediacy
    user_plantings = request.session.get('user_plantings', [])
    user_plantings.append(new_planting)
    request.session['user_plantings'] = user_plantings
    request.session.modified = True
    logger.info('Saved planting to session (total=%d)', len(user_plantings))

    return redirect('index')

def edit_planting_view(request, planting_id):
    """Edit planting view - loads from DynamoDB or session"""
    load_user_plantings = _get_helper('load_user_plantings')
    get_user_id_from_token = _get_helper('get_user_id_from_token', 'get_user_id_from_request')

    user_id = None
    try:
        if get_user_id_from_token:
            user_id = get_user_id_from_token(request)
        elif hasattr(request, 'user') and getattr(request.user, 'is_authenticated', False):
            user_id = str(request.user.pk)
    except Exception:
        logger.exception('Error getting user id in edit_planting_view')

    user_plantings = []
    if user_id and load_user_plantings:
        try:
            user_plantings = load_user_plantings(user_id)
        except Exception as e:
            logger.exception('Error loading from DynamoDB: %s', e)

    if not user_plantings:
        user_plantings = request.session.get('user_plantings', [])

    if planting_id >= len(user_plantings):
        logger.error('Planting index %d out of range (total: %d)', planting_id, len(user_plantings))
        return redirect('index')

    try:
        planting_to_edit = dict(user_plantings[planting_id])
        planting_to_edit['id'] = planting_id

        # planting_date normalization for the form
        pd = planting_to_edit.get('planting_date', '')
        if isinstance(pd, date):
            planting_to_edit['planting_date_str'] = pd.isoformat()
        elif isinstance(pd, str):
            try:
                date.fromisoformat(pd)
                planting_to_edit['planting_date_str'] = pd
            except Exception:
                planting_to_edit['planting_date_str'] = str(pd)
        else:
            planting_to_edit['planting_date_str'] = str(pd) if pd else ''

        planting_to_edit.setdefault('crop_name', '')
        planting_to_edit.setdefault('batch_id', '')
        planting_to_edit.setdefault('notes', '')
        planting_to_edit.setdefault('image_url', '')

        logger.info('Loading planting for edit: id=%d, crop=%s, date=%s',
                    planting_id, planting_to_edit.get('crop_name'), planting_to_edit.get('planting_date_str'))
    except Exception as e:
        logger.exception('Error preparing planting for edit: %s', e)
        return redirect('index')

    plant_data = load_plant_data()
    context = {
        'plant_names': [p['name'] for p in plant_data['plants']],
        'planting': planting_to_edit,
        'is_editing': True
    }
    return render(request, 'tracker/edit.html', context)


def update_planting(request, planting_id):
    """Update planting - update in Dynamo and session"""
    if request.method != 'POST':
        return redirect('index')

    load_user_plantings = _get_helper('load_user_plantings')
    save_planting_to_dynamodb = _get_helper('save_planting_to_dynamodb')
    get_user_id_from_token = _get_helper('get_user_id_from_token', 'get_user_id_from_request')
    upload_planting_image = _get_helper('upload_planting_image')
    delete_image_from_s3 = _get_helper('delete_image_from_s3')

    user_id = None
    try:
        if get_user_id_from_token:
            user_id = get_user_id_from_token(request)
        elif hasattr(request, 'user') and getattr(request.user, 'is_authenticated', False):
            user_id = str(request.user.pk)
    except Exception:
        logger.exception('Error getting user id in update_planting')

    user_plantings = []
    if user_id and load_user_plantings:
        try:
            user_plantings = load_user_plantings(user_id)
        except Exception as e:
            logger.exception('Error loading from DynamoDB: %s', e)

    if not user_plantings:
        user_plantings = request.session.get('user_plantings', [])

    if planting_id >= len(user_plantings):
        logger.error('Planting index %d out of range (total: %d)', planting_id, len(user_plantings))
        return redirect('index')

    existing_planting = dict(user_plantings[planting_id])
    actual_planting_id = existing_planting.get('planting_id')

    crop_name = request.POST.get('crop_name', '').strip() or existing_planting.get('crop_name', '')
    planting_date_str = request.POST.get('planting_date', '').strip() or existing_planting.get('planting_date', '')
    batch_id = request.POST.get('batch_id', '').strip() or existing_planting.get('batch_id', f'batch-{date.today().strftime("%Y%m%d")}')
    notes = request.POST.get('notes', '').strip() or existing_planting.get('notes', '')

    image_url = existing_planting.get('image_url', '')
    if 'image' in request.FILES and request.FILES['image'].name:
        old_image = image_url
        if old_image and delete_image_from_s3:
            try:
                delete_image_from_s3(old_image)
            except Exception:
                logger.exception('Failed deleting old image from S3: %s', old_image)
        if user_id and upload_planting_image:
            try:
                image_url = upload_planting_image(request.FILES['image'], user_id)
                logger.info('Uploaded new image for planting: %s', image_url)
            except Exception:
                logger.exception('Image upload failed for updated planting')

    if not crop_name or not planting_date_str:
        logger.error('Missing required fields on update')
        return redirect('index')

    if isinstance(planting_date_str, str):
        planting_date = date.fromisoformat(planting_date_str)
    elif isinstance(planting_date_str, date):
        planting_date = planting_date_str
    else:
        logger.error('Invalid planting_date format on update')
        return redirect('index')

    calculate = _get_calculate_plan()
    calculated_plan = calculate(crop_name, planting_date, load_plant_data())
    for task in calculated_plan:
        if 'due_date' in task and isinstance(task['due_date'], date):
            task['due_date'] = task['due_date'].isoformat()

    updated_planting = {
        'crop_name': crop_name,
        'planting_date': planting_date.isoformat(),
        'batch_id': batch_id,
        'notes': notes,
        'plan': calculated_plan,
        'image_url': image_url
    }
    if actual_planting_id:
        updated_planting['planting_id'] = actual_planting_id

    # Persist change to Dynamo (helper expects the planting dict)
    try:
        if user_id and save_planting_to_dynamodb:
            returned = save_planting_to_dynamodb(updated_planting)
            if returned:
                logger.info('Updated planting %s in DynamoDB', returned)
            else:
                logger.warning('Dynamo update did not return id; session updated only')
    except Exception:
        logger.exception('Failed to update planting in DynamoDB, proceeding with session update')

    # Update session
    user_plantings[planting_id] = updated_planting
    request.session['user_plantings'] = user_plantings
    request.session.modified = True
    logger.info('Updated planting at index %d in session', planting_id)

    return redirect('index')


def delete_planting(request, planting_id):
    """Delete planting - Dynamo and session"""
    if request.method != 'POST':
        return redirect('index')

    load_user_plantings = _get_helper('load_user_plantings')
    delete_planting_from_dynamodb = _get_helper('delete_planting_from_dynamodb', 'delete_planting')
    get_user_id_from_token = _get_helper('get_user_id_from_token', 'get_user_id_from_request')
    delete_image_from_s3 = _get_helper('delete_image_from_s3')

    user_id = None
    try:
        if get_user_id_from_token:
            user_id = get_user_id_from_token(request)
        elif hasattr(request, 'user') and getattr(request.user, 'is_authenticated', False):
            user_id = str(request.user.pk)
    except Exception:
        logger.exception('Error getting user id in delete_planting')

    user_plantings = []
    if user_id and load_user_plantings:
        try:
            user_plantings = load_user_plantings(user_id)
        except Exception as e:
            logger.exception('Error loading from DynamoDB: %s', e)

    if not user_plantings:
        user_plantings = request.session.get('user_plantings', [])

    if planting_id >= len(user_plantings):
        logger.error('Planting index %d out of range (total: %d)', planting_id, len(user_plantings))
        return redirect('index')

    try:
        planting_to_delete = user_plantings[planting_id]
        actual_planting_id = planting_to_delete.get('planting_id')
        image_url = planting_to_delete.get('image_url', '')

        if image_url and delete_image_from_s3:
            try:
                delete_image_from_s3(image_url)
                logger.info('Deleted image from S3: %s', image_url)
            except Exception:
                logger.exception('Failed to delete image from S3: %s', image_url)

        if user_id and actual_planting_id and delete_planting_from_dynamodb:
            try:
                deleted = delete_planting_from_dynamodb(actual_planting_id)
                if deleted:
                    logger.info('Deleted planting %s from DynamoDB', actual_planting_id)
                else:
                    logger.warning('Dynamo delete returned falsy; removing from session only')
            except Exception:
                logger.exception('Failed deleting planting from DynamoDB; proceeding to remove from session')

        # Remove from session list
        user_plantings.pop(planting_id)
        request.session['user_plantings'] = user_plantings
        request.session.modified = True
        logger.info('Deleted planting at index %d from session', planting_id)
    except Exception:
        logger.exception('Exception while deleting planting')

    return redirect('index')


def cognito_login(request):
    """Redirect user to Cognito Hosted UI login."""
    from .cognito import build_authorize_url
    callback_url = request.build_absolute_uri('/auth/callback/')
    from urllib.parse import urlparse, urlunparse
    parsed = urlparse(callback_url)
    callback_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', '', ''))
    url = build_authorize_url(redirect_uri=callback_url)
    logger.info('Cognito login: Redirecting to Cognito with redirect_uri: %s', callback_url)
    return redirect(url)


def cognito_logout(request):
    """Logout user by clearing Cognito tokens and redirecting to login page."""
    request.session.pop('id_token', None)
    request.session.pop('access_token', None)
    request.session.pop('refresh_token', None)
    request.session.pop('cognito_tokens', None)
    logger.info('Cognito logout: Cleared tokens from session, redirecting to login')
    return redirect('login')


def cognito_callback(request):
    """Handle callback from Cognito Hosted UI, exchange code for tokens and save user to DynamoDB (best-effort)."""
    import requests
    from django.db import OperationalError

    logger.info('Cognito callback received for path: %s', request.path)
    logger.info('Cognito callback query params: %s', request.GET.dict())

    error = request.GET.get('error')
    error_description = request.GET.get('error_description')
    if error:
        logger.error('Cognito callback error: %s - %s', error, error_description)
        from urllib.parse import quote
        return redirect(f'/?auth_error={quote(error_description or error)}')

    code = request.GET.get('code')
    if not code:
        logger.warning('Cognito callback: No code provided and no error - unexpected response')
        return HttpResponse("No code provided. Please try logging in again.", status=400)

    # Build redirect_uri used in authorize request
    actual_redirect_uri = request.build_absolute_uri(request.path)
    from urllib.parse import urlparse, urlunparse
    parsed = urlparse(actual_redirect_uri)
    actual_redirect_uri = urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', '', ''))
    redirect_uri = actual_redirect_uri or settings.COGNITO_REDIRECT_URI

    token_url = f"https://{settings.COGNITO_DOMAIN}/oauth2/token"
    data = {
        'grant_type': 'authorization_code',
        'client_id': settings.COGNITO_CLIENT_ID,
        'code': code,
        'redirect_uri': redirect_uri
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}

    try:
        response = requests.post(token_url, data=data, headers=headers, auth=(settings.COGNITO_CLIENT_ID, settings.COGNITO_CLIENT_SECRET) if settings.COGNITO_CLIENT_SECRET else None)
    except Exception as e:
        logger.exception('Error calling Cognito token endpoint: %s', e)
        return HttpResponse(f"Error fetching tokens: {str(e)}", status=500)

    if response.status_code != 200:
        error_text = response.text
        logger.error('Cognito token exchange failed: %s - %s', response.status_code, error_text)
        try:
            error_data = response.json()
            if error_data.get('error') == 'invalid_grant':
                return HttpResponse("Authorization code invalid or expired. Please try logging in again.", status=400)
        except Exception:
            pass
        return HttpResponse(f"Error fetching tokens: {error_text}", status=response.status_code)

    tokens = response.json()
    logger.info('Cognito callback: Tokens received successfully')

    try:
        request.session['id_token'] = tokens.get('id_token')
        request.session['access_token'] = tokens.get('access_token')
        if tokens.get('refresh_token'):
            request.session['refresh_token'] = tokens.get('refresh_token')
        request.session['cognito_tokens'] = {
            'id_token': tokens.get('id_token'),
            'access_token': tokens.get('access_token'),
            'refresh_token': tokens.get('refresh_token'),
        }
        request.session.modified = True
        logger.info('Cognito callback: Tokens saved to session')

        # Best-effort: decode id_token and save user to DynamoDB
        id_token = tokens.get('id_token')
        if id_token:
            try:
                # Try jose first (if available), then PyJWT fallback
                try:
                    from jose import jwt as jose_jwt
                    payload = jose_jwt.decode(id_token, options={"verify_signature": False})
                except Exception:
                    try:
                        import jwt as pyjwt
                        payload = pyjwt.decode(id_token, options={"verify_signature": False})
                    except Exception as e:
                        logger.exception('Failed to decode id_token: %s', e)
                        payload = {}

                logger.info('Extracted user data from id_token keys: %s', list(payload.keys()))

                # Build simple user_data
                user_data = {
                    'username': payload.get('username') or payload.get('preferred_username') or payload.get('sub'),
                    'email': payload.get('email'),
                    'sub': payload.get('sub'),
                    'name': payload.get('name') or payload.get('username') or payload.get('email')
                }

                # Try multiple helper names to save user to DynamoDB (best-effort)
                save_user_to_dynamodb = _get_helper('save_user_to_dynamodb', 'create_or_update_user', 'save_user')
                if save_user_to_dynamodb:
                    try:
                        saved = save_user_to_dynamodb(user_data)
                        if saved:
                            logger.info('User saved to DynamoDB (best-effort)')
                        else:
                            logger.warning('Dynamo helper returned falsy when saving user')
                    except Exception:
                        logger.exception('Exception while saving user to DynamoDB')
                else:
                    logger.warning('No dynamo helper found to persist user data')
            except Exception:
                logger.exception('Exception processing id_token for user save')
        else:
            logger.warning('No id_token available in Cognito response; skipping user save')
    except OperationalError as e:
        logger.exception('Database error saving session: %s', e)
        return HttpResponse("Authentication succeeded but session save failed.", status=503)
    except Exception as e:
        logger.exception('Error saving session: %s', e)
        return HttpResponse(f"Error saving session: {str(e)}", status=500)

    return redirect('/')


# API endpoint for returning user profile JSON (kept distinct from the login_required profile page)
def user_profile_api(request):
    if not hasattr(request, "user") or not getattr(request.user, "is_authenticated", False):
        return JsonResponse({"error": "Unauthorized"}, status=401)

    return JsonResponse({
        "email": request.user.email,
        "sub": str(request.user.pk)
    })


@login_required
def profile(request):
    """Handle profile view and profile updates. (web UI)"""
    if request.method == 'POST':
        user = request.user
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')

        if username and username != user.username:
            user.username = username
            user.save()
            logger.info('Profile updated: username changed to %s', username)

        if email and email != user.email:
            user.email = email
            user.save()
            logger.info('Profile updated: email changed to %s', email)

        if password:
            user.set_password(password)
            user.save()
            logger.info('Profile updated: password changed')

        return redirect('/')

    return render(request, 'profile.html')


def signup(request):
    """User signup: create Django User, UserProfile and best-effort save to DynamoDB"""
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            email = form.cleaned_data['email']
            try:
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=form.cleaned_data['password1'],
                )
                logger.info('Django user created: username=%s, id=%s', username, user.id)

                UserProfile.objects.create(
                    user=user,
                    country=form.cleaned_data.get('country')
                )
                logger.info('UserProfile created for: %s', username)

                # Prepare user_data to persist to Dynamo (best-effort)
                user_data = {
                    'username': username,
                    'email': email,
                    'sub': f'django_{user.id}',
                    'name': username
                }

                save_user_to_dynamodb = _get_helper('save_user_to_dynamodb', 'create_or_update_user', 'save_user')
                if save_user_to_dynamodb:
                    try:
                        saved = save_user_to_dynamodb(user_data)
                        if saved:
                            logger.info('Saved user %s to DynamoDB', username)
                        else:
                            logger.warning('Dynamo helper returned falsy when saving user %s', username)
                    except Exception:
                        logger.exception('Exception while saving user to DynamoDB')
                else:
                    logger.warning('No dynamo helper available to save user data')

                # Authenticate and log the user in
                user = authenticate(username=username, password=form.cleaned_data['password1'])
                if user is not None:
                    login(request, user)
                    logger.info('User %s authenticated and logged in', username)
                else:
                    logger.error('Failed to authenticate user %s after signup', username)

                return redirect('/')
            except Exception as e:
                logger.exception('Error during signup: %s', e)
                form.add_error(None, f'An error occurred during signup: {str(e)}')
    else:
        form = SignUpForm()
    return render(request, 'registration/signup.html', {'form': form})


def login_view(request):
    """
    Login view - supports Cognito redirect (preferred) and local Django auth fallback.
    """
    get_user_id_from_token = _get_helper('get_user_id_from_token', 'get_user_id_from_request')

    try:
        user_id = get_user_id_from_token(request) if get_user_id_from_token else None
    except Exception:
        user_id = None

    if user_id:
        logger.info('User already authenticated (user_id: %s), redirecting to home', user_id)
        return redirect('index')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        if username and password:
            user = authenticate(request, username=username, password=password)
            if user:
                login(request, user)
                logger.info('User %s logged in via Django auth', username)
                return redirect('index')
            else:
                from django.contrib.auth.forms import AuthenticationForm
                form = AuthenticationForm()
                form.errors['__all__'] = form.error_messages['invalid_login']
                return render(request, 'registration/login.html', {'form': form})

    return render(request, 'registration/login.html')


def toggle_notifications(request):
    """
    API endpoint to toggle user's notification preferences.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method allowed'}, status=405)

    get_user_data_from_token = _get_helper('get_user_data_from_token', 'get_user_id_from_token')
    update_user_notification_preference = _get_helper('update_user_notification_preference', 'set_user_notification_preference', 'update_user_notifications')
    subscribe_email_to_topic = _get_helper('subscribe_email_to_topic', 'sns_subscribe_email')

    try:
        user_data = None
        if get_user_data_from_token:
            try:
                user_data = get_user_data_from_token(request)
            except Exception:
                try:
                    id_token = request.session.get('id_token')
                    user_data = get_user_data_from_token(id_token) if id_token else None
                except Exception:
                    user_data = None

        if not user_data and hasattr(request, 'user') and getattr(request.user, 'is_authenticated', False):
            user_data = {'username': request.user.username, 'email': request.user.email, 'sub': str(request.user.pk)}

        if not user_data:
            return JsonResponse({'error': 'User not authenticated'}, status=401)

        username = user_data.get('username') or user_data.get('preferred_username') or user_data.get('sub')
        email = user_data.get('email')

        # parse body
        try:
            body = json.loads(request.body) if request.body else request.POST
        except Exception:
            body = request.POST

        enabled = body.get('enabled', True)
        if isinstance(enabled, str):
            enabled = enabled.lower() == 'true'

        if update_user_notification_preference:
            ok = update_user_notification_preference(username, enabled)
            if not ok:
                return JsonResponse({'error': 'Failed to update notification preference'}, status=500)

        if enabled and email and subscribe_email_to_topic:
            try:
                subscribe_email_to_topic(email)
                logger.info('Subscribed %s to SNS topic', email)
            except Exception:
                logger.exception('Failed subscribing email to SNS topic')

        return JsonResponse({'success': True, 'notifications_enabled': enabled})
    except Exception as e:
        logger.exception('Error toggling notifications: %s', e)
        return JsonResponse({'error': str(e)}, status=500)