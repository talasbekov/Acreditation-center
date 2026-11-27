from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_safe


@never_cache
@login_required(login_url="/user_login/")
@require_http_methods(["GET", "HEAD", "POST"])
def iin_view(request):
    # Issuance stays closed until the scanner supports an approved private format.
    return render(request, "qr_event/qr.html", status=503)


@never_cache
@login_required(login_url="/user_login/")
@require_safe
def qr_success_view(request, pk):
    # Historical records refer to images containing the original identifier.
    # Return the same response even when the ID never existed.
    return render(request, "qr_event/success.html", status=404)
