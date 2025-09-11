import qrcode
import io
import json
from django.core.files.base import ContentFile
from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import QrIinForm

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

def iin_view(request):
    if request.method == 'POST':
        form = QrIinForm(request.POST)
        if form.is_valid():
            obj = form.save(commit=False)
            
            # Генерируем QR-код с JSON данными ИИН
            qr_data = json.dumps({"iin": int(obj.iin)})  # {"iin": "950118301007"}
            qr_buffer = generate_qr_code(qr_data)
            
            # Сохраняем QR-код как файл
            qr_filename = f"qr_{obj.iin}.png"
            obj.qr_code.save(qr_filename, ContentFile(qr_buffer.getvalue()), save=True)
            
            obj.save()
            
            messages.success(request, f"ИИН {obj.iin} успешно верифицирован.")
            return redirect('qr_success', pk=obj.pk)
        else:
            messages.error(request, "Исправьте ошибки в форме.")
    else:
        form = QrIinForm()
    return render(request, 'qr_event/qr.html', {'form': form})

def qr_success_view(request, pk):
    """Отображение успешной генерации QR-кода"""
    from .models import QrIin
    try:
        qr_record = QrIin.objects.get(pk=pk)
        return render(request, 'qr_event/success.html', {'qr_record': qr_record})
    except QrIin.DoesNotExist:
        messages.error(request, "Запись не найдена.")
        return redirect('iin_form')
