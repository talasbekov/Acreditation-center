// Form validation and enhancement script
document.addEventListener('DOMContentLoaded', function() {
    const iinInput = document.getElementById('iinInput');
    const submitBtn = document.getElementById('submitBtn');
    const form = document.querySelector('.iin-form');

    if (!iinInput) return;

    // Format ИИН input - only allow digits
    iinInput.addEventListener('input', function(e) {
        // Remove all non-digit characters
        let value = e.target.value.replace(/\D/g, '');

        // Limit to 12 digits
        if (value.length > 12) {
            value = value.slice(0, 12);
        }

        e.target.value = value;

        // Real-time validation feedback
        validateIINRealTime(value);
    });

    // Prevent non-numeric input
    iinInput.addEventListener('keypress', function(e) {
        // Allow backspace, delete, tab, escape, enter
        if ([8, 9, 27, 13, 46].indexOf(e.keyCode) !== -1 ||
            // Allow Ctrl+A, Ctrl+C, Ctrl+V, Ctrl+X
            (e.keyCode === 65 && e.ctrlKey === true) ||
            (e.keyCode === 67 && e.ctrlKey === true) ||
            (e.keyCode === 86 && e.ctrlKey === true) ||
            (e.keyCode === 88 && e.ctrlKey === true)) {
            return;
        }

        // Ensure that it is a number and stop the keypress
        if ((e.shiftKey || (e.keyCode < 48 || e.keyCode > 57)) && (e.keyCode < 96 || e.keyCode > 105)) {
            e.preventDefault();
        }
    });

    // Form submission with loading state
    if (form) {
        form.addEventListener('submit', function(e) {
            if (submitBtn) {
                submitBtn.classList.add('btn-loading');
                submitBtn.disabled = true;
            }
        });
    }

    // Real-time ИИН validation
    function validateIINRealTime(iin) {
        const inputGroup = iinInput.closest('.input-group');
        const feedbackDiv = document.querySelector('.invalid-feedback');

        // Remove existing validation classes
        iinInput.classList.remove('is-valid', 'is-invalid');

        if (iin.length === 0) {
            return; // Don't validate empty input
        }

        if (iin.length < 12) {
            iinInput.classList.add('is-invalid');
            showValidationMessage('ИИН должен содержать 12 цифр', 'error');
            return;
        }

        if (iin.length === 12) {
            if (validateIINChecksum(iin)) {
                iinInput.classList.add('is-valid');
                showValidationMessage('ИИН корректен', 'success');
            } else {
                iinInput.classList.add('is-invalid');
                showValidationMessage('Неверный формат ИИН', 'error');
                // Add shake animation
                inputGroup.classList.add('shake');
                setTimeout(() => inputGroup.classList.remove('shake'), 500);
            }
        }
    }

    // Show validation message
    function showValidationMessage(message, type) {
        let feedbackDiv = document.querySelector('.validation-feedback');

        if (!feedbackDiv) {
            feedbackDiv = document.createElement('div');
            feedbackDiv.className = 'validation-feedback';
            iinInput.parentNode.parentNode.appendChild(feedbackDiv);
        }

        feedbackDiv.className = type === 'success' ? 'valid-feedback d-block' : 'invalid-feedback d-block';
        feedbackDiv.innerHTML = `<i class="fas fa-${type === 'success' ? 'check-circle' : 'exclamation-circle'}"></i> ${message}`;
    }

    // ИИН checksum validation (Kazakhstan algorithm)
    function validateIINChecksum(iin) {
        if (iin.length !== 12) return false;

        // Extract date part and validate
        const year = parseInt(iin.substr(0, 2));
        const month = parseInt(iin.substr(2, 2));
        const day = parseInt(iin.substr(4, 2));

        // Basic date validation
        if (month < 1 || month > 12) return false;
        if (day < 1 || day > 31) return false;

        // Validate checksum
        const weights1 = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11];
        const weights2 = [3, 4, 5, 6, 7, 8, 9, 10, 11, 1, 2];

        // Calculate first checksum
        let sum1 = 0;
        for (let i = 0; i < 11; i++) {
            sum1 += parseInt(iin[i]) * weights1[i];
        }

        let checksum1 = sum1 % 11;

        if (checksum1 < 10) {
            return parseInt(iin[11]) === checksum1;
        } else {
            // Calculate second checksum
            let sum2 = 0;
            for (let i = 0; i < 11; i++) {
                sum2 += parseInt(iin[i]) * weights2[i];
            }

            let checksum2 = sum2 % 11;
            if (checksum2 < 10) {
                return parseInt(iin[11]) === checksum2;
            }
        }

        return false;
    }

    // Auto-dismiss alerts
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(function(alert) {
        setTimeout(function() {
            if (alert && alert.classList.contains('show')) {
                const bsAlert = new bootstrap.Alert(alert);
                bsAlert.close();
            }
        }, 5000);
    });

    // Add smooth transitions to form elements
    const formElements = document.querySelectorAll('.form-control, .btn');
    formElements.forEach(function(element) {
        element.style.transition = 'all 0.3s ease';
    });

    // Enhance button interactions
    const buttons = document.querySelectorAll('.btn');
    buttons.forEach(function(button) {
        button.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-2px)';
        });

        button.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0)';
        });
    });

    // Add focus enhancement to inputs
    const inputs = document.querySelectorAll('.form-control');
    inputs.forEach(function(input) {
        input.addEventListener('focus', function() {
            this.closest('.input-group').style.transform = 'translateY(-2px)';
        });

        input.addEventListener('blur', function() {
            this.closest('.input-group').style.transform = 'translateY(0)';
        });
    });
});