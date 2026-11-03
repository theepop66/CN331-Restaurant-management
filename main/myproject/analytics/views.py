from django.shortcuts import render

from accounts.decorators import restaurant_owner_required

from .services import build_dashboard_data, get_ai_insights


@restaurant_owner_required
def dashboard(request, restaurant):
    data = build_dashboard_data(restaurant)
    insights, ai_provider = get_ai_insights(restaurant, data)
    return render(
        request,
        'analytics/dashboard.html',
        {
            **data,
            'ai_insights': insights,
            'ai_provider': ai_provider,
        },
    )
