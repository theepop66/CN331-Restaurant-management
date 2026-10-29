from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.db import transaction
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .decorators import owner_required
from .forms import CustomUserCreationForm, LoginForm, RestaurantForm


def register_view(request):
    """[UC-01] Sign up a new restaurant owner and create their tenant."""
    if request.user.is_authenticated:
        return redirect('accounts:home')

    if request.method == 'POST':
        restaurant_form = RestaurantForm(request.POST)
        user_form = CustomUserCreationForm(request.POST)

        if restaurant_form.is_valid() and user_form.is_valid():
            with transaction.atomic():
                restaurant = restaurant_form.save()
                user = user_form.save(commit=False)
                user.restaurant = restaurant
                user.role = CustomUserCreationForm.Meta.model.Role.OWNER
                user.save()

            auth_login(request, user)
            messages.success(
                request,
                f'สร้างร้าน "{restaurant.name}" และบัญชีผู้ใช้สำเร็จ ยินดีต้อนรับ!',
            )
            return redirect('accounts:home')
    else:
        restaurant_form = RestaurantForm()
        user_form = CustomUserCreationForm()

    return render(
        request,
        'accounts/register.html',
        {
            'restaurant_form': restaurant_form,
            'user_form': user_form,
        },
    )


def login_view(request):
    """[UC-01] Authenticate an existing user."""
    if request.user.is_authenticated:
        return redirect('accounts:home')

    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            auth_login(request, form.get_user())
            messages.success(request, 'เข้าสู่ระบบสำเร็จ')
            next_url = request.POST.get('next') or request.GET.get('next')
            return redirect(next_url or 'accounts:home')
        messages.error(request, 'ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง')
    else:
        form = LoginForm(request)

    return render(request, 'accounts/login.html', {'form': form})


@require_POST
def logout_view(request):
    """
    [UC-01] Log the current user out.

    POST-only: logout is a state-changing action, so a plain GET link
    (which can be triggered by prefetching, crawlers, or CSRF) must not
    be able to log someone out. The navbar submits this via a small
    <form method="post">.
    """
    auth_logout(request)
    messages.success(request, 'ออกจากระบบเรียบร้อยแล้ว')
    return redirect('accounts:login')


@owner_required
def home_view(request):
    """
    [UC-01][US-03][UC-03] Owner landing page, including unassigned accounts.

    Deliberately named "home" (not "dashboard") to leave the
    `analytics:dashboard` route free for UC-06 later in the project.
    """
    return render(
        request,
        'accounts/home.html',
        {
            'restaurant': request.user.restaurant,
        },
    )
