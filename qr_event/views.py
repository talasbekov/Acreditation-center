import qrcode
import io
import json
import uuid
from django.core.files.base import ContentFile
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .forms import QrIinForm

# Ключ сессии со списком pk записей, созданных текущим пользователем
SESSION_QR_PKS = "qr_iin_created_pks"


def generate_qr_code(data):
    """Генерирует красивый QR-код из данных"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,  # Средний уровень коррекции
        box_size=10,  # Увеличиваем размер
        border=4,     # Больше отступов
    )
    qr.add_data(data)
    qr.make(fit=True)

    # Создаем изображение с фирменным синим цветом
    img = qr.make_image(fill_color="#1e40af", back_color="white")

    # Сохраняем в BytesIO
    buffer = io.BytesIO()
    img.save(buffer, format='PNG', optimize=True)
    buffer.seek(0)

    return buffer


@login_required(login_url="/user_login/")
def iin_view(request):
    if request.method == 'POST':
        form = QrIinForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)

            # Генерируем QR-код с JSON данными ИИН
            qr_data = json.dumps({"iin": int(obj.iin)})  # {"iin": "950118301007"}
            qr_buffer = generate_qr_code(qr_data)

            # Имя файла не должно содержать ИИН (файл доступен по MEDIA_URL)
            qr_filename = f"qr_{uuid.uuid4().hex}.png"
            obj.qr_code.save(qr_filename, ContentFile(qr_buffer.getvalue()), save=True)

            obj.save()

            # Страница успеха доступна только создателю записи в этой сессии
            created = request.session.get(SESSION_QR_PKS, [])
            created.append(obj.pk)
            request.session[SESSION_QR_PKS] = created

            messages.success(request, f"ИИН {obj.iin} успешно верифицирован.")
            return redirect('qr_success', pk=obj.pk)
        else:
            messages.error(request, "Исправьте ошибки в форме.")
    else:
        form = QrIinForm()
    return render(request, 'qr_event/qr.html', {'form': form})


@login_required(login_url="/user_login/")
def qr_success_view(request, pk):
    """Отображение успешной генерации QR-кода"""
    from .models import QrIin
    if pk not in request.session.get(SESSION_QR_PKS, []) and not request.user.is_superuser:
        messages.error(request, "Запись не найдена.")
        return redirect('iin_form')
    try:
        qr_record = QrIin.objects.get(pk=pk)
        return render(request, 'qr_event/success.html', {'qr_record': qr_record})
    except QrIin.DoesNotExist:
        messages.error(request, "Запись не найдена.")
        return redirect('iin_form')
