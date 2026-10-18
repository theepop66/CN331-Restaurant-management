from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import restaurant_owner_required
from accounts.transactions import restaurant_transaction

from .forms import (
    AvailabilityForm,
    MenuItemForm,
    RecipeItemFormSet,
    RecipeRevisionForm,
    RevisionForm,
)
from .models import MenuItem
from .services import EditConflict, read_menu, replace_recipe, set_availability, update_menu


@restaurant_owner_required
def menu_list(request, restaurant):
    """[US-03][UC-03] List only this owner's menus and recipe health."""
    menus = (
        MenuItem.objects.filter(restaurant=restaurant)
        .annotate(
            row_count=Count('recipe_items'),
            missing_count=Count('recipe_items', filter=Q(recipe_items__ingredient__isnull=True)),
        )
        .order_by('name', 'pk')
    )
    return render(
        request,
        'menus/menu_list.html',
        {
            'page': Paginator(menus, 20).get_page(request.GET.get('page')),
        },
    )


@restaurant_owner_required
def menu_create(request, restaurant):
    """[US-03][UC-03] Save an inactive draft and continue to its BOM."""
    form = MenuItemForm(
        request.POST if request.method == 'POST' else None,
        instance=MenuItem(restaurant=restaurant),
    )
    if request.method == 'POST' and form.is_valid():
        try:
            with restaurant_transaction(restaurant.pk):
                menu = form.save()
        except IntegrityError:
            form.add_error('name', 'มีเมนูชื่อนี้ในร้านแล้ว')
        else:
            messages.success(request, 'สร้างเมนูฉบับร่างแล้ว เพิ่มสูตรอาหารก่อนเปิดขาย')
            return redirect('menus:recipe', pk=menu.pk)
    return render(request, 'menus/menu_form.html', {'form': form})


@restaurant_owner_required
def menu_update(request, restaurant, pk):
    """[US-03][UC-03] Update metadata without overwriting another edit."""
    menu = get_object_or_404(MenuItem, pk=pk, restaurant=restaurant)
    form = MenuItemForm(request.POST if request.method == 'POST' else None, instance=menu)
    revision_form = RevisionForm(
        request.POST if request.method == 'POST' else None,
        initial={'expected_revision': menu.revision},
    )
    status = 200
    if request.method == 'POST' and form.is_valid() and revision_form.is_valid():
        try:
            update_menu(menu, revision_form.cleaned_data['expected_revision'], **form.cleaned_data)
        except EditConflict as error:
            form.add_error(None, error)
            status = 409
        except IntegrityError:
            form.add_error('name', 'มีเมนูชื่อนี้ในร้านแล้ว')
        else:
            messages.success(request, 'บันทึกข้อมูลเมนูแล้ว')
            return redirect('menus:list')
    return render(
        request,
        'menus/menu_form.html',
        {
            'form': form,
            'revision_form': revision_form,
            'menu': menu,
            'current': read_menu(menu),
        },
        status=status,
    )


@restaurant_owner_required
def recipe_builder_view(request, restaurant, pk):
    """[US-03][UC-03] Edit a complete per-serving BOM as one versioned save."""
    menu = get_object_or_404(MenuItem, pk=pk, restaurant=restaurant)
    data = request.POST if request.method == 'POST' else None
    formset = RecipeItemFormSet(
        data,
        instance=menu,
        prefix='items',
        form_kwargs={'restaurant': restaurant},
    )
    revision_form = RecipeRevisionForm(data, menu=menu)
    status = 200
    if request.method == 'POST':
        valid = formset.is_valid()
        version_valid = revision_form.is_valid()
        if version_valid and revision_form.cleaned_data['expected_revision'] != menu.revision:
            revision_form.add_error(None, EditConflict())
            status = 409
        elif version_valid and valid:
            entries = [
                (form.cleaned_data['ingredient'].pk, form.cleaned_data['quantity_used'])
                for form in formset.forms
                if form.cleaned_data and not form.cleaned_data.get('DELETE')
            ]
            try:
                replace_recipe(
                    menu,
                    revision_form.cleaned_data['expected_revision'],
                    entries,
                    revision_form.expected_units,
                )
            except ValidationError as error:
                revision_form.add_error(None, error)
                status = 409 if isinstance(error, EditConflict) else 200
            else:
                messages.success(request, 'บันทึกสูตรอาหารแล้ว')
                return redirect('menus:recipe', pk=menu.pk)
    return render(
        request,
        'menus/recipe_builder.html',
        {
            'menu': menu,
            'formset': formset,
            'revision_form': revision_form,
            'snapshot': read_menu(menu),
        },
        status=status,
    )


@restaurant_owner_required
def menu_availability_update(request, restaurant, pk):
    """[US-03][UC-03] Explicitly activate or retire a complete owner menu."""
    menu = get_object_or_404(MenuItem, pk=pk, restaurant=restaurant)
    if request.method != 'POST':
        from django.http import HttpResponseNotAllowed

        return HttpResponseNotAllowed(['POST'])
    form = AvailabilityForm(request.POST)
    status = 200
    if form.is_valid():
        try:
            set_availability(
                menu,
                form.cleaned_data['expected_revision'],
                form.cleaned_data['is_active'],
            )
        except ValidationError as error:
            form.add_error(None, error)
            status = 409 if isinstance(error, EditConflict) else 200
        else:
            messages.success(request, 'อัปเดตสถานะเมนูแล้ว')
            return redirect('menus:recipe', pk=menu.pk)
    return render(
        request,
        'menus/availability_error.html',
        {
            'form': form,
            'menu': menu,
            'snapshot': read_menu(menu),
        },
        status=status,
    )
