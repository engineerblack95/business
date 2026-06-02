from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse
from django.core.paginator import Paginator
from .forms import (
    RegistrationForm, LoginForm, OTPVerificationForm,
    ProfileUpdateForm, SupplierApplicationForm
)
from .models import User, UserLoginHistory
from .utils.otp_handler import OTPHandler
from .utils.geolocation import GeoLocationService
from .utils.device_detector import DeviceDetector
import uuid
import os


def register_view(request):
    """User registration view - FIXED for Render"""
    if request.user.is_authenticated:
        return redirect('dashboard:home')
    
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.role = 'customer'
            user.is_verified = False
            user.save()
            
            # Generate OTP
            otp = user.generate_otp()
            
            # Send OTP with error handling for Render
            email_sent = False
            try:
                # Try to send email
                email_sent = OTPHandler.send_otp_email(user, otp, purpose='registration')
            except Exception as e:
                print(f"Email error: {e}")
                email_sent = False
            
            # Store OTP in session for debug mode on Render
            on_render = os.environ.get('RENDER_EXTERNAL_HOSTNAME', False)
            if on_render and not email_sent:
                # Store OTP in session so user can see it
                request.session['debug_otp'] = otp
                request.session['debug_email'] = user.email
                messages.warning(request, f'[DEMO MODE] Your OTP is: {otp} (Check console logs or use this code)')
            else:
                messages.success(request, 'Registration successful! Please verify your email with the OTP sent.')
            
            # Store user ID in session for OTP verification
            request.session['pending_user_id'] = str(user.id)
            return redirect('accounts:verify_otp')
    else:
        form = RegistrationForm()
    
    return render(request, 'accounts/register.html', {'form': form})


def login_view(request):
    """User login view - FIXED for Render"""
    if request.user.is_authenticated:
        return redirect('dashboard:home')
    
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            try:
                user = User.objects.get(email=email)
                
                # Check if user is active
                if not user.is_active:
                    messages.error(request, 'Your account is disabled.')
                    return redirect('accounts:login')
                
                # Generate OTP
                otp = user.generate_otp()
                
                # Send OTP with error handling for Render
                email_sent = False
                try:
                    email_sent = OTPHandler.send_otp_email(user, otp, purpose='login')
                except Exception as e:
                    print(f"Email error: {e}")
                    email_sent = False
                
                # Store user email in session
                request.session['login_email'] = email
                
                # Handle Render email issues
                on_render = os.environ.get('RENDER_EXTERNAL_HOSTNAME', False)
                if on_render and not email_sent:
                    request.session['debug_otp'] = otp
                    messages.warning(request, f'[DEMO MODE] Your OTP is: {otp} (Use this code to login)')
                else:
                    messages.success(request, f'OTP sent to {email}. Please check your email.')
                    
                return redirect('accounts:verify_otp')
                
            except User.DoesNotExist:
                messages.error(request, 'No account found with this email.')
    else:
        form = LoginForm()
    
    return render(request, 'accounts/login.html', {'form': form})


def verify_otp_view(request):
    """OTP verification view - FIXED with debug OTP support"""
    
    # Check if we have pending user ID (registration) or login email
    pending_user_id = request.session.get('pending_user_id')
    login_email = request.session.get('login_email')
    
    # Check for debug OTP from session
    debug_otp = request.session.get('debug_otp')
    
    if not pending_user_id and not login_email:
        messages.error(request, 'Session expired. Please try again.')
        return redirect('accounts:login')
    
    # Get user
    if pending_user_id:
        user = get_object_or_404(User, id=pending_user_id)
    else:
        user = get_object_or_404(User, email=login_email)
    
    if request.method == 'POST':
        form = OTPVerificationForm(request.POST)
        if form.is_valid():
            otp = form.cleaned_data['otp']
            
            # Check against debug OTP first (for Render demo mode)
            on_render = os.environ.get('RENDER_EXTERNAL_HOSTNAME', False)
            is_valid = user.verify_otp(otp)
            
            # If regular OTP fails but we have debug OTP, check that
            if not is_valid and on_render and debug_otp and otp == debug_otp:
                is_valid = True
            
            if is_valid:
                # Log the user in
                login(request, user)
                
                # Record login history
                ip_address = request.META.get('REMOTE_ADDR')
                user_agent = request.META.get('HTTP_USER_AGENT', '')
                
                # Get geolocation (with error handling)
                try:
                    geo_service = GeoLocationService()
                    location_data = geo_service.get_location_from_ip(ip_address)
                except Exception as e:
                    print(f"Geolocation error: {e}")
                    location_data = {'country': 'Unknown', 'city': 'Unknown', 'lat': None, 'lon': None}
                
                # Detect device (with error handling)
                try:
                    device_detector = DeviceDetector()
                    device_info = device_detector.detect_device(user_agent)
                except Exception as e:
                    print(f"Device detection error: {e}")
                    device_info = {
                        'device_type': 'unknown',
                        'os_type': 'unknown',
                        'browser': 'Unknown',
                        'browser_version': 'Unknown'
                    }
                
                # Create login history
                try:
                    UserLoginHistory.objects.create(
                        user=user,
                        session_key=request.session.session_key,
                        ip_address=ip_address,
                        user_agent=user_agent,
                        location_country=location_data.get('country', ''),
                        location_city=location_data.get('city', ''),
                        location_latitude=location_data.get('lat'),
                        location_longitude=location_data.get('lon'),
                        device_type=device_info.get('device_type', 'unknown'),
                        os_type=device_info.get('os_type', 'unknown'),
                        browser=device_info.get('browser', 'Unknown'),
                        browser_version=device_info.get('browser_version', 'Unknown'),
                    )
                except Exception as e:
                    print(f"Error saving login history: {e}")
                
                # Clear session data
                request.session.pop('pending_user_id', None)
                request.session.pop('login_email', None)
                request.session.pop('debug_otp', None)
                
                # Send welcome email for new registrations (with error handling)
                if pending_user_id:
                    try:
                        OTPHandler.send_welcome_email(user)
                    except Exception as e:
                        print(f"Error sending welcome email: {e}")
                
                messages.success(request, f'Welcome back, {user.full_name or user.email}!')
                
                # Redirect to appropriate dashboard
                return redirect(user.get_dashboard_url())
            else:
                if user.otp_attempts >= 5:
                    messages.error(request, 'Too many failed attempts. Please request a new OTP.')
                    return redirect('accounts:login')
                messages.error(request, 'Invalid OTP. Please try again.')
    else:
        form = OTPVerificationForm()
    
    # Show debug OTP info if available
    debug_message = None
    if debug_otp:
        debug_message = f"Debug OTP for testing: {debug_otp}"
    
    context = {
        'form': form,
        'email': user.email,
        'is_registration': bool(pending_user_id),
        'debug_otp': debug_otp,
        'debug_message': debug_message,
    }
    
    return render(request, 'accounts/verify_otp.html', context)


def resend_otp_view(request):
    """Resend OTP to user - FIXED for Render"""
    pending_user_id = request.session.get('pending_user_id')
    login_email = request.session.get('login_email')
    
    if pending_user_id:
        user = get_object_or_404(User, id=pending_user_id)
        purpose = 'registration'
    elif login_email:
        user = get_object_or_404(User, email=login_email)
        purpose = 'login'
    else:
        messages.error(request, 'Unable to resend OTP. Please try again.')
        return redirect('accounts:login')
    
    try:
        otp = user.generate_otp()
        
        # Try to send email, but handle failure gracefully
        email_sent = False
        try:
            email_sent = OTPHandler.send_otp_email(user, otp, purpose=purpose)
        except Exception as e:
            print(f"Email error on resend: {e}")
            email_sent = False
        
        # Handle Render email issues
        on_render = os.environ.get('RENDER_EXTERNAL_HOSTNAME', False)
        if on_render and not email_sent:
            request.session['debug_otp'] = otp
            messages.warning(request, f'[DEMO MODE] Your new OTP is: {otp}')
        else:
            messages.success(request, f'New OTP sent to {user.email}')
            
    except Exception as e:
        messages.error(request, f'Error sending OTP: {str(e)}')
    
    return redirect('accounts:verify_otp')


@login_required
def logout_view(request):
    """User logout view with logging"""
    # Update logout time in last login history
    if request.user.is_authenticated and request.session.session_key:
        try:
            last_history = UserLoginHistory.objects.filter(
                user=request.user,
                session_key=request.session.session_key,
                logout_time__isnull=True
            ).latest('login_time')
            last_history.logout_time = timezone.now()
            last_history.save()
        except UserLoginHistory.DoesNotExist:
            pass
        except Exception as e:
            print(f"Error updating logout time: {e}")
    
    logout(request)
    messages.success(request, 'You have been successfully logged out.')
    return redirect('home')


@login_required
def profile_view(request):
    """User profile view and update"""
    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('accounts:profile')
    else:
        form = ProfileUpdateForm(instance=request.user)
    
    # Get recent login history
    recent_logins = UserLoginHistory.objects.filter(
        user=request.user
    ).order_by('-login_time')[:10]
    
    return render(request, 'accounts/profile.html', {
        'form': form,
        'recent_logins': recent_logins
    })


@login_required
def apply_supplier_view(request):
    """Allow customer to apply as supplier"""
    if request.user.role not in ['customer', 'supplier']:
        messages.error(request, 'You are not eligible to apply as a supplier.')
        return redirect('dashboard:home')
    
    if request.user.role == 'supplier':
        messages.warning(request, 'You are already a supplier.')
        return redirect('dashboard:supplier')
    
    if request.method == 'POST':
        form = SupplierApplicationForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_approved_supplier = False  # Pending approval
            user.save()
            
            # Notify admins about new application
            from dashboard.utils.notifications import NotificationManager
            admins = User.objects.filter(role='admin')
            for admin in admins:
                try:
                    NotificationManager.send_notification(
                        user=admin,
                        title="New Supplier Application",
                        message=f"{user.email} has applied to become a supplier.",
                        notification_type='supplier',
                        priority='high',
                        link='/dashboard/admin/suppliers/'
                    )
                except Exception as e:
                    print(f"Error sending notification: {e}")
            
            messages.success(request, 'Your supplier application has been submitted. Admin will review it.')
            return redirect('accounts:profile')
    else:
        form = SupplierApplicationForm(instance=request.user)
    
    return render(request, 'accounts/apply_supplier.html', {'form': form})


@login_required
def login_history_view(request):
    """View user's login history with pagination"""
    if not request.user.is_authenticated:
        return redirect('accounts:login')
    
    # Get all login history with pagination
    login_history = UserLoginHistory.objects.filter(
        user=request.user
    ).order_by('-login_time')
    
    # Add pagination
    paginator = Paginator(login_history, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'accounts/login_history.html', {
        'login_history': page_obj
    })