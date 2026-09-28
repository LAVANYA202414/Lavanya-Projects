from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from .forms import UserSignupForm


def home_view(request):
    return render(request, 'home.html')


def signup_view(request):
    if request.method == "POST":
        form = UserSignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request,user)
            return redirect('home')

    else:
        form = UserSignupForm()

    return render(request,"signup.html", {'form':form})


def login_view(request):
    # Check if the user is already logged in; if so, send them straight to home
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        # AuthenticationForm handles email validation automatically
        # because USERNAME_FIELD = 'email' is set in your User model
        form = AuthenticationForm(request, data=request.POST)
        
        if form.is_valid():
            # Extract the authenticated user object from the form
            user = form.get_user()
            
            # Create the active browser session for the user
            login(request, user)
            
            # Send them to your dashboard or landing page
            return redirect('home')
    else:
        # Provide a clean, empty login form on a standard GET request
        form = AuthenticationForm()
        
    return render(request, 'login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect("login")