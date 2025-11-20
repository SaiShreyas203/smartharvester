import json
from datetime import date, timedelta
from django.shortcuts import render, redirect
from django.conf import settings
import os
import boto3
import uuid

from smartharvest_plan.plan import calculate_plan

from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User

from .forms import SignUpForm
from .models import UserProfile

from smartharvest_plan.plan import calculate_plan # My PyPi Library

DATA_FILE_PATH = os.path.join(settings.BASE_DIR, 'tracker', 'data.json')


def load_plant_data():
    with open(DATA_FILE_PATH, 'r') as f:
        return json.load(f)

def index(request):
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
        calculated_plan = calculate_plan(crop_name, planting_date, plant_data)

        # Convert due_date to ISO strings for storage in session
        for task in calculated_plan:
            if 'due_date' in task and isinstance(task['due_date'], date):
                task['due_date'] = task['due_date'].isoformat()

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
        calculated_plan = calculate_plan(crop_name, planting_date, plant_data)

        # Convert due_date to ISO strings for storage in session
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
        request.session['user_plantings'] = user_plantings

    return redirect('index')

def delete_planting(request, planting_id):
    if request.method == 'POST':
        user_plantings = request.session.get('user_plantings', [])
        try:
            del user_plantings[planting_id]
            request.session['user_plantings'] = user_plantings
        except IndexError:
            pass
    return redirect('index')

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