import json
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from .models import Post, Saved, Interested, User
from django.shortcuts import render, redirect
from django.shortcuts import redirect, render
from .forms import SignupForm, LoginForm, CreatePostsForm
from django.contrib import auth
from django.contrib.auth import authenticate
from django.contrib.auth.decorators import login_required
from django.db.models import Max, Q
from django.urls import reverse
from django.core.mail import EmailMessage
from .s3 import upload_file, delete_file
import mimetypes
from urllib.parse import urlparse

def index(request):
    # event_date___gte used to find the events available in future, To avoid the expried events and __gte means '>='
    posts = Post.objects.filter().values(
        'id', 'pet_name', 'pet_category', 'pet_age', 'pet_image_url', 'owner', 'updated').order_by('-updated')
    for post in posts:
        post['updated'] = post['updated'].date()
    return render(request, 'index.html', {'title': 'Take Care', 'page_url': "show_interest", 'posts': posts})


def search(request):
    search_value = request.GET.get('search_query')
    # Q is used to perform OR logical operation
    search_result = Post.objects.filter(Q(owner_name__icontains=search_value) | Q(pet_name__icontains=search_value) | Q(pet_category__icontains=search_value) | Q(pet_age__icontains=search_value)).values(
        'id', 'pet_name', 'pet_category', 'pet_age', 'pet_image_url', 'owner', 'updated').order_by('-updated')
    return render(request, 'index.html', {'title': 'Search - Take Care', 'page_url': "show_interest", 'posts': search_result})


@login_required(login_url="login")
def show_interest(request, id):
    # event_date___gte used to find the events available in future, To avoid the expried events and __gte means '>='
    post_details = Post.objects.filter(id=id).values()
    if not post_details:
        return HttpResponse("This post is not available")
    saved = Saved.objects.filter(
        owner=request.user, post=Post.objects.get(pk=id)).values()
    interested = Interested.objects.filter(
        owner=request.user, post=Post.objects.get(pk=id)
    ).values()
    return render(request, 'show_interest.html', {'title': 'Show Interest - Take Care', 'post_details': post_details[0], 'saved': saved, 'interested': interested})


def signup(request):
    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('login')
        return render(request, 'signup.html', {'signup_form': form})
    form = SignupForm()
    return render(request, 'signup.html', {'title': 'Signup - Take Care', 'signup_form': form})


def login(request):
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = authenticate(
                request, username=form.cleaned_data['username'], password=form.cleaned_data['password'])
            if user is not None:
                auth.login(request, user)
                next_url = request.GET.get('next', '')
                return redirect(next_url)
        return render(request, 'login.html', {'login_form': form})
    form = LoginForm()
    return render(request, 'login.html', {'title': 'Login - Take Care', 'login_form': form})


def logout(request):
    auth.logout(request)
    return redirect('')


@login_required(login_url="login")
def interest_showed(request):
    fetch_interest_showed = Post.objects.filter(
        interested_posts__owner=request.user).values(
        'id', 'pet_name', 'pet_category', 'pet_age', 'pet_image_url', 'owner', 'updated').annotate(
        order_by_interested=Max('interested_posts__updated')
    ).order_by('-order_by_interested')
    if not fetch_interest_showed:
        return HttpResponse('No interest yet')
    return render(request, 'index.html', {
        'title': 'Interest Showed - Take Care', 'page_url': 'show_interest', 'posts': fetch_interest_showed
    })


@login_required(login_url="login")
def create_posts(request):
    if request.method == 'POST':
        form = CreatePostsForm(request.POST, request.FILES)
        if form.is_valid():
            pet_image = request.FILES['pet_image']
            image_key = f"take_care/images/{pet_image}"
            content_type = mimetypes.guess_type(pet_image.name)[0]
            pet_image_response = upload_file(pet_image, 'x23176245-s3-bucket', image_key, content_type)
            create_post = form.save(commit=False)
            create_post.owner_name = request.user
            create_post.owner = request.user
            create_post.pet_image_url = pet_image_response['object_url']
            create_post.save()
            return redirect('posts_created_by_you')
    form = CreatePostsForm()
    return render(request, 'create_posts.html', {'title': 'Create Post - Take Care', 'create_posts_form': form, 'submit_button_value': "Create"})


@login_required(login_url="login")
def save_this_post(request):
    if request.method == 'POST':
        # json.loads(request.POST) used to get the data from the POST request, request.POST can be used only in the form submissions
        id = json.loads(request.body)['id']
        # event = Event.objects.get(pk=id) to create Event model instance
        if not Saved.objects.filter(owner=request.user, post=Post.objects.get(pk=id)):
            Saved.objects.create(
                owner=request.user, post=Post.objects.get(pk=id))
            return JsonResponse({'saved': True})
        else:
            Saved.objects.filter(
                owner=request.user, post=Post.objects.get(pk=id)).delete()
            return JsonResponse({'saved': False})
    return JsonResponse({'status': 'Invalid request'})


@login_required(login_url="login")
def saved_posts(request):
    fetch_saved_posts = Post.objects.filter(
        saved_posts__owner=request.user).values(
        'id', 'pet_name', 'pet_category', 'pet_age', 'pet_image_url', 'owner', 'updated').order_by('-updated')
    if not fetch_saved_posts:
        return HttpResponse('No saved events')
    for post in fetch_saved_posts:
        post['updated'] = post['updated'].date()
    return render(request, 'index.html', {'title': 'Saved Posts - Take Care', 'page_url': "show_interest", 'posts': fetch_saved_posts})


@login_required(login_url="login")
def posts_created_by_you(request):
    fetch_posts_created_by_you = Post.objects.filter(owner=request.user).values(
        'id', 'pet_name', 'pet_category', 'pet_age', 'pet_image_url', 'owner', 'updated').order_by('-updated')
    if not fetch_posts_created_by_you:
        return HttpResponse('No posts created')
    return render(request, 'index.html', {'titles': 'Created Posts - Take Care', 'page_url': 'show_interest', 'posts': fetch_posts_created_by_you})


@login_required(login_url="login")
def confirm_interest(request):
    if request.method == 'POST':
        # json.loads(request.POST) used to get the data from the POST request, request.POST can be used only in the form submissions
        id = json.loads(request.body)['id']
        owner = json.loads(request.body)['owner']
        # event = Event.objects.get(pk=id) to create Event model instance
        if not Interested.objects.filter(owner=request.user, post=Post.objects.get(pk=id)):
            Interested.objects.create(
                owner=request.user, post=Post.objects.get(pk=id))
            receiver = User.objects.get(pk=owner).email
            email = EmailMessage('Interested in adopting your pet', '{} has shown interest in adopting your pet'.format(
                request.user), settings.EMAIL_HOST_USER, [receiver], reply_to=[request.user.email])
            email.send()
            return JsonResponse({'saved': True})
        else:
            Interested.objects.filter(
                owner=request.user, post=Post.objects.get(pk=id)).delete()
            receiver = User.objects.get(pk=owner).email
            email = EmailMessage("Update on Pet Adoption: {}'s Decision".format(request.user), '{} has withdrawn interest in adopting your pet'.format(
                request.user), settings.EMAIL_HOST_USER, [receiver], reply_to=[request.user.email])
            email.send()
            return JsonResponse({'saved': False})
    return JsonResponse({'status': 'Invalid request'})


@login_required(login_url="login")
def edit_created_post(request, id):
    post_edit = Post.objects.filter(owner=request.user, id=id)[0]
    if request.method == 'POST':
        form = CreatePostsForm(request.POST, request.FILES, instance=post_edit)
        if form.is_valid():
            if 'pet_image' in form.changed_data and form.cleaned_data['pet_image']:
                image_key = urlparse(post_edit.pet_image_url).path.lstrip('/')
                delete_file('x23176245-s3-bucket', image_key)
                pet_image = request.FILES['pet_image']
                image_key = f"take_care/images/{pet_image}"
                content_type = mimetypes.guess_type(pet_image.name)[0]
                pet_image_response = upload_file(pet_image, 'x23176245-s3-bucket', image_key, content_type)
                post_edit.pet_image_url = pet_image_response['object_url']
            form.save()
            request.session['previous_page'] = request.META.get(
                'HTTP_REFERER', '/')
            return redirect(reverse('show_interest', kwargs={'id': id}))
    form = CreatePostsForm(instance=post_edit)
    return render(request, 'create_posts.html', {'title': 'Post Edit - Take Care', 'create_posts_form': form, 'submit_button_value': "Update"})


@login_required(login_url="login")
def delete_created_post(request, id):
    post_deleted = Post.objects.filter(owner=request.user, id=id)[0]
    image_key = urlparse(post_deleted.pet_image_url).path.lstrip('/')
    delete_file('x23176245-s3-bucket', image_key)
    post_deleted.delete()
    return redirect('posts_created_by_you')
