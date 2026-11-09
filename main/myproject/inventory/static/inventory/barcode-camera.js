(() => {
    const form = document.getElementById('inventory-scan-form');
    const barcode = form.elements.namedItem('barcode');
    const openButton = document.getElementById('barcode-camera-open');
    const closeButton = document.getElementById('barcode-camera-close');
    const preview = document.getElementById('barcode-camera-preview');
    const status = document.getElementById('barcode-camera-status');
    const video = preview.querySelector('video');
    const cameraOptions = {
        video: {
            facingMode: { ideal: 'environment' },
            width: { ideal: 1280 },
            height: { ideal: 720 },
            advanced: [{ focusMode: 'continuous' }],
        },
        audio: false,
    };
    const cameraErrors = {
        NotAllowedError: 'กรุณาอนุญาตให้เว็บไซต์ใช้กล้องในเบราว์เซอร์',
        NotFoundError: 'ไม่พบกล้องบนอุปกรณ์นี้',
        NotReadableError: 'เปิดกล้องไม่ได้ ลองปิดแอปอื่นที่กำลังใช้กล้อง',
    };
    let active = false;
    let opening = false;
    let controls;
    let stream;

    function stopCamera() {
        active = false;
        preview.hidden = true;
        if (controls) {
            controls.stop();
            controls = undefined;
        } else {
            stream?.getTracks().forEach(track => track.stop());
        }
        stream = undefined;
        openButton.disabled = opening;
    }

    openButton.hidden = false;
    openButton.addEventListener('click', async () => {
        if (!navigator.mediaDevices?.getUserMedia || !window.ZXingBrowser) {
            status.textContent = 'เปิดตัวสแกนกล้องไม่ได้ กรุณาพิมพ์รหัสหรือใช้เครื่องสแกนภายนอก';
            return;
        }

        active = true;
        opening = true;
        openButton.disabled = true;
        preview.hidden = false;
        closeButton.focus();
        status.textContent = 'กำลังเปิดกล้อง…';
        try {
            const cameraStream = await navigator.mediaDevices.getUserMedia(cameraOptions);
            if (!active) {
                cameraStream.getTracks().forEach(track => track.stop());
                return;
            }
            stream = cameraStream;
            const reader = new window.ZXingBrowser.BrowserMultiFormatReader();
            const scanner = await reader.decodeFromStream(stream, video, result => {
                if (!active || !result) return;
                const code = result.getText().trim();
                if (!code || code.length > barcode.maxLength) return;
                stopCamera();
                barcode.value = code;
                form.requestSubmit();
            });
            if (active) {
                controls = scanner;
                status.textContent = 'วางบาร์โค้ดทั้งอันในกรอบ ให้เส้นแดงตัดผ่านแท่งบาร์โค้ด แล้วขยับจนภาพคมชัด';
            } else {
                scanner.stop();
            }
        } catch (error) {
            if (active) {
                stopCamera();
                status.textContent = cameraErrors[error.name] || 'เปิดกล้องไม่ได้ กรุณาลองอีกครั้ง';
                barcode.focus();
            }
        } finally {
            opening = false;
            openButton.disabled = active;
        }
    });

    closeButton.addEventListener('click', () => {
        stopCamera();
        status.textContent = '';
        barcode.focus();
    });
    form.addEventListener('submit', stopCamera);
    window.addEventListener('pagehide', stopCamera);
})();
