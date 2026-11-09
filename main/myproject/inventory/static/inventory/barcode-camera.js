(() => {
    const form = document.getElementById('inventory-scan-form');
    const barcode = form.elements.namedItem('barcode');
    const photoButton = document.getElementById('barcode-photo-open');
    const photoInput = document.getElementById('barcode-photo');
    const openButton = document.getElementById('barcode-camera-open');
    const closeButton = document.getElementById('barcode-camera-close');
    const preview = document.getElementById('barcode-camera-preview');
    const status = document.getElementById('barcode-camera-status');
    const instruction = document.getElementById('barcode-camera-instruction');
    const video = preview.querySelector('video');
    const guide = preview.querySelector('.barcode-camera-guide');
    const scanCanvas = document.createElement('canvas');
    const scanContext = scanCanvas.getContext('2d', { willReadFrequently: true });
    const cameraOptions = {
        video: {
            facingMode: { ideal: 'environment' },
            width: { ideal: 1920 },
            height: { ideal: 1080 },
            advanced: [{ focusMode: 'continuous' }],
        },
        audio: false,
    };
    const cameraErrors = {
        NotAllowedError: 'กรุณาอนุญาตให้เว็บไซต์ใช้กล้องในเบราว์เซอร์',
        NotFoundError: 'ไม่พบกล้องบนอุปกรณ์นี้',
        NotReadableError: 'เปิดกล้องไม่ได้ ลองปิดแอปอื่นที่กำลังใช้กล้อง',
    };
    let opening = false;
    let stream;
    let scanTimer;

    function stopCamera() {
        clearTimeout(scanTimer);
        if (stream) {
            stream.getTracks().forEach(track => track.stop());
            video.pause();
            video.srcObject = null;
            stream = undefined;
        }
        if (preview.open) preview.close();
        openButton.disabled = opening || photoButton.disabled;
    }

    function readBarcodeInGuide(reader) {
        const sourceWidth = video.videoWidth;
        const sourceHeight = video.videoHeight;
        // The centered cover preview can crop the sides of the camera image.
        const scale = Math.max(video.clientWidth / sourceWidth, video.clientHeight / sourceHeight);
        const width = Math.round(guide.clientWidth / scale);
        const height = Math.round(guide.clientHeight / scale);
        if (width < 1 || height < 1) return;

        if (scanCanvas.width !== width || scanCanvas.height !== height) {
            scanCanvas.width = width;
            scanCanvas.height = height;
        }
        const x = (sourceWidth - width) / 2;
        const y = (sourceHeight - height) / 2;
        scanContext.drawImage(video, x, y, width, height, 0, 0, width, height);
        try {
            return reader.decodeFromCanvas(scanCanvas).getText().trim();
        } catch {
            // Keep scanning until the barcode is clear enough to decode.
        }
    }

    function scanFrame(reader) {
        if (!preview.open) return;
        if (video.readyState >= 2 && video.videoWidth && video.videoHeight) {
            const code = readBarcodeInGuide(reader);
            if (code && code.length <= barcode.maxLength) {
                stopCamera();
                barcode.value = code;
                form.requestSubmit();
                return;
            }
        }
        scanTimer = setTimeout(() => scanFrame(reader), 180);
    }

    photoButton.hidden = !window.ZXingBrowser;
    photoButton.addEventListener('click', () => {
        stopCamera();
        status.textContent = '';
        photoInput.click();
    });
    photoInput.addEventListener('change', async () => {
        const photo = photoInput.files[0];
        photoInput.value = '';
        if (!photo) return;

        photoButton.disabled = true;
        openButton.disabled = true;
        status.textContent = 'กำลังอ่านบาร์โค้ดจากรูป…';
        const photoUrl = URL.createObjectURL(photo);
        try {
            const image = new Image();
            image.src = photoUrl;
            await image.decode();
            const reader = new window.ZXingBrowser.BrowserMultiFormatReader();
            const result = await reader.decodeFromImageElement(image);
            const code = result.getText().trim();
            if (!code || code.length > barcode.maxLength) {
                status.textContent = 'รหัสจากรูปใช้ไม่ได้ กรุณาถ่ายใหม่หรือพิมพ์รหัส';
                return;
            }
            barcode.value = code;
            status.textContent = 'อ่านรหัสแล้ว ตรวจสอบรหัสและกดสแกน';
        } catch {
            status.textContent = 'อ่านบาร์โค้ดจากรูปไม่ได้ ลองถ่ายให้เห็นทั้งรหัสและให้แท่งบาร์โค้ดคมชัด';
        } finally {
            URL.revokeObjectURL(photoUrl);
            photoButton.disabled = false;
            openButton.disabled = opening;
        }
    });

    openButton.hidden = false;
    openButton.addEventListener('click', async () => {
        if (!navigator.mediaDevices?.getUserMedia || !window.ZXingBrowser || !preview.showModal || !scanContext) {
            status.textContent = 'เปิดตัวสแกนกล้องไม่ได้ กรุณาพิมพ์รหัสหรือใช้เครื่องสแกนภายนอก';
            return;
        }

        opening = true;
        openButton.disabled = true;
        status.textContent = '';
        instruction.textContent = 'กำลังเปิดกล้อง…';
        try {
            preview.showModal();
            const cameraStream = await navigator.mediaDevices.getUserMedia(cameraOptions);
            if (!preview.open) {
                cameraStream.getTracks().forEach(track => track.stop());
                return;
            }
            stream = cameraStream;
            video.srcObject = stream;
            await video.play();
            if (!preview.open) return;
            instruction.textContent = 'วางบาร์โค้ดทั้งอันในกรอบ ให้เส้นแดงพาดผ่านกลางรหัส ถ้าภาพเบลอให้ถอยมือถือออกช้า ๆ';
            scanFrame(new window.ZXingBrowser.BrowserMultiFormatReader());
        } catch (error) {
            if (preview.open) {
                stopCamera();
                status.textContent = cameraErrors[error.name] || 'เปิดกล้องไม่ได้ กรุณาลองอีกครั้ง';
                barcode.focus();
            }
        } finally {
            opening = false;
            openButton.disabled = preview.open || photoButton.disabled;
        }
    });

    closeButton.addEventListener('click', stopCamera);
    preview.addEventListener('cancel', event => {
        event.preventDefault();
        stopCamera();
    });
    form.addEventListener('submit', stopCamera);
    window.addEventListener('pagehide', stopCamera);
})();
