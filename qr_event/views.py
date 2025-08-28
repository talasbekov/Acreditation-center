from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import QrIinForm

def iin_view(request):
    if request.method == 'POST':
        form = QrIinForm(request.POST)
        if form.is_valid():
            from django.utils import timezone
            print("UTC now:      ", timezone.now())
            print("Local Almaty: ", timezone.localtime())  # по TIME_ZONE

            obj = form.save()
            messages.success(request, f"ИИН {obj.iin} верифицирован.")
            return redirect('iin_form')  # используйте name в urls
        else:
            messages.error(request, "Исправьте ошибки в форме.")
    else:
        form = QrIinForm()
    return render(request, 'qr_event/qr.html', {'form': form})
