// ─────────────────────────────────────────
//  FACE DETECTION & VERIFICATION
//  Uses face-api.js
// ─────────────────────────────────────────

const MODELS_URL = './models';
const FACE_MATCH_THRESHOLD = 0.5; // Lower = stricter match

let videoStream = null;
let detectionInterval = null;
let capturedDescriptor = null;
let registeredDescriptor = null;
let faceApiLoaded = false;

// Load face-api.js models
async function loadFaceModels() {
    try {
        await Promise.all([
            faceapi.nets.tinyFaceDetector.loadFromUri(MODELS_URL),
            faceapi.nets.faceLandmark68Net.loadFromUri(MODELS_URL),
            faceapi.nets.faceRecognitionNet.loadFromUri(MODELS_URL),
        ]);
        faceApiLoaded = true;
        console.log('Face models loaded ✅');
        return true;
    } catch (err) {
        console.error('Face model load error:', err);
        return false;
    }
}

// Start webcam
async function startCamera() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            video: { width: 320, height: 240, facingMode: 'user' }
        });
        const video = document.getElementById('video');
        video.srcObject = stream;
        videoStream = stream;
        return new Promise(resolve => {
            video.onloadedmetadata = () => resolve(true);
        });
    } catch (err) {
        console.error('Camera error:', err);
        return false;
    }
}

// Stop webcam
function stopCamera() {
    if (videoStream) {
        videoStream.getTracks().forEach(t => t.stop());
        videoStream = null;
    }
    if (detectionInterval) {
        clearInterval(detectionInterval);
        detectionInterval = null;
    }
}

// Detect face and get descriptor
async function detectFace() {
    const video = document.getElementById('video');
    const overlay = document.getElementById('overlay');
    const statusEl = document.getElementById('faceStatus');

    if (!video || !faceApiLoaded) return null;

    // Match canvas size to video
    overlay.width = video.videoWidth;
    overlay.height = video.videoHeight;
    const ctx = overlay.getContext('2d');

    const detection = await faceapi
        .detectSingleFace(video, new faceapi.TinyFaceDetectorOptions())
        .withFaceLandmarks()
        .withFaceDescriptor();

    ctx.clearRect(0, 0, overlay.width, overlay.height);

    if (detection) {
        // Draw detection box
        const { x, y, width, height } = detection.detection.box;
        ctx.strokeStyle = '#4f46e5';
        ctx.lineWidth = 3;
        ctx.strokeRect(x, y, width, height);

        // Draw landmarks
        faceapi.draw.drawFaceLandmarks(overlay, detection);

        return detection.descriptor;
    }

    return null;
}

// Start live face detection loop
async function startFaceDetection(onFaceDetected, onNoFace) {
    if (!faceApiLoaded) {
        const loaded = await loadFaceModels();
        if (!loaded) {
            onNoFace('Face model load nahi hua. Internet check karein.');
            return;
        }
    }

    const cameraStarted = await startCamera();
    if (!cameraStarted) {
        onNoFace('Camera access nahi mila. Permission dein.');
        return;
    }

    // Wait a bit for video to stabilize
    await new Promise(r => setTimeout(r, 1000));

    let consecutiveDetections = 0;
    const REQUIRED_DETECTIONS = 3; // Face 3 consecutive frames mein ho

    detectionInterval = setInterval(async () => {
        const descriptor = await detectFace();

        if (descriptor) {
            consecutiveDetections++;
            if (consecutiveDetections >= REQUIRED_DETECTIONS) {
                capturedDescriptor = descriptor;
                onFaceDetected(descriptor);
            }
        } else {
            consecutiveDetections = 0;
            onNoFace(null);
        }
    }, 500);
}

// Compare two face descriptors
function compareFaces(descriptor1, descriptor2) {
    if (!descriptor1 || !descriptor2) return { matched: false, distance: 999 };

    const desc1 = descriptor1 instanceof Float32Array
        ? descriptor1
        : new Float32Array(Object.values(descriptor1));
    const desc2 = descriptor2 instanceof Float32Array
        ? descriptor2
        : new Float32Array(Object.values(descriptor2));

    const distance = faceapi.euclideanDistance(desc1, desc2);
    const matched = distance <= FACE_MATCH_THRESHOLD;

    return { matched, distance: parseFloat(distance.toFixed(4)) };
}

// Convert Float32Array to plain array for JSON
function descriptorToArray(descriptor) {
    return Array.from(descriptor);
}

// Convert plain array back to Float32Array
function arrayToDescriptor(arr) {
    return new Float32Array(arr);
}
