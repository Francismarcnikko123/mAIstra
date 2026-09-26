package com.sample.edgedetection.scan
import android.app.Activity
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.BitmapFactory
import android.graphics.Point
import android.graphics.Rect
import android.graphics.YuvImage
import android.hardware.Camera
import android.hardware.camera2.CameraAccessException
import android.hardware.camera2.CameraCharacteristics
import android.hardware.camera2.CameraManager
import android.hardware.camera2.params.StreamConfigurationMap
import android.os.Bundle
import android.os.SystemClock
import android.util.Log
import android.view.Display
import android.view.SurfaceHolder
import android.widget.Toast
import com.sample.edgedetection.EdgeDetectionHandler
import com.sample.edgedetection.REQUEST_CODE
import com.sample.edgedetection.SourceManager
import com.sample.edgedetection.crop.CropActivity
import com.sample.edgedetection.processor.Corners
import com.sample.edgedetection.processor.processPicture
import io.reactivex.Observable
import io.reactivex.Scheduler
import io.reactivex.android.schedulers.AndroidSchedulers
import io.reactivex.schedulers.Schedulers
import org.opencv.android.Utils
import org.opencv.core.Core
import org.opencv.core.Core.ROTATE_90_CLOCKWISE
import org.opencv.core.CvType
import org.opencv.core.Mat
import org.opencv.core.Size
import org.opencv.imgcodecs.Imgcodecs
import org.opencv.imgproc.Imgproc
import java.io.ByteArrayOutputStream
import java.io.IOException
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import kotlin.math.max
import kotlin.math.min
import android.util.Size as SizeB

class ScanPresenter constructor(
    private val context: Context,
    private val iView: IScanView.Proxy,
    private val initialBundle: Bundle
) :
    SurfaceHolder.Callback, Camera.PictureCallback, Camera.PreviewCallback {
    private val TAG: String = "ScanPresenter"
    private var mCamera: Camera? = null
    private val mSurfaceHolder: SurfaceHolder = iView.getSurfaceView().holder
    private val executor: ExecutorService
    private val proxySchedule: Scheduler
    private var busy: Boolean = false
    private var mCameraLensFacing: String? = null
    private var flashEnabled: Boolean = false

    private var mLastClickTime = 0L
    private var shutted: Boolean = true
    private var lastLightingCheckTime = 0L
    private val lightingCheckIntervalMs = 500L
    private var noDetectionStartTime = 0L  // tracks how long no paper has been found
    private val mainHandler = android.os.Handler(android.os.Looper.getMainLooper())
    @Volatile private var paperDetected = false

    init {
        mSurfaceHolder.addCallback(this)
        executor = Executors.newSingleThreadExecutor()
        proxySchedule = Schedulers.from(executor)
    }

    // Analyses only the center 60% of the NV21 Y-plane to avoid dark background bias.
    // Uses a 3x3 grid to detect shadows (uneven lighting) across the paper.
    private fun checkLighting(yPlane: ByteArray, width: Int, height: Int): String? {
        val step = 8
        val xStart = width / 5
        val xEnd = width * 4 / 5
        val yStart = height / 5
        val yEnd = height * 4 / 5
        val regionW = ((xEnd - xStart) / 3).coerceAtLeast(1)
        val regionH = ((yEnd - yStart) / 3).coerceAtLeast(1)
        val gridSums = FloatArray(9)
        val gridCounts = IntArray(9)
        var darkCount = 0
        var brightCount = 0
        var total = 0

        for (y in yStart until yEnd step step) {
            for (x in xStart until xEnd step step) {
                val luma = yPlane[y * width + x].toInt() and 0xFF
                total++
                if (luma < 60) darkCount++
                if (luma > 220) brightCount++
                val col = minOf((x - xStart) / regionW, 2)
                val row = minOf((y - yStart) / regionH, 2)
                gridSums[row * 3 + col] += luma
                gridCounts[row * 3 + col]++
            }
        }

        if (total == 0) return null
        val darkFraction = darkCount.toFloat() / total
        val brightFraction = brightCount.toFloat() / total
        val avgs = (0 until 9).map { i ->
            if (gridCounts[i] > 0) gridSums[i] / gridCounts[i] else 0f
        }
        val spread = (avgs.maxOrNull() ?: 0f) - (avgs.minOrNull() ?: 0f)

        return when {
            darkFraction > 0.40f -> "⚠ Too dark — move to a brighter area"
            brightFraction > 0.40f -> "⚠ Too bright — reduce lighting or move away"
            else -> null
        }
    }

    fun focusOnPoint(x: Float, y: Float, viewWidth: Int, viewHeight: Int) {
        val camera = mCamera ?: return
        val params = camera.parameters ?: return
        // Camera1 focus areas use a -1000..+1000 coordinate space
        // The camera is rotated 90°, so x/y axes are swapped
        val focusSize = 150
        val cx = ((y / viewHeight) * 2000 - 1000).toInt().coerceIn(-1000, 1000)
        val cy = ((x / viewWidth) * 2000 - 1000).toInt().coerceIn(-1000, 1000)
        val focusRect = Rect(
            (cx - focusSize).coerceIn(-1000, 1000),
            (cy - focusSize).coerceIn(-1000, 1000),
            (cx + focusSize).coerceIn(-1000, 1000),
            (cy + focusSize).coerceIn(-1000, 1000)
        )
        val area = Camera.Area(focusRect, 1000)
        if (params.maxNumFocusAreas > 0) params.focusAreas = listOf(area)
        if (params.maxNumMeteringAreas > 0) params.meteringAreas = listOf(area)
        params.focusMode = Camera.Parameters.FOCUS_MODE_AUTO
        try {
            camera.parameters = params
            camera.autoFocus { _, _ ->
                // Return to continuous focus after tap-focus settles
                val p = camera.parameters ?: return@autoFocus
                if (p.supportedFocusModes.contains(Camera.Parameters.FOCUS_MODE_CONTINUOUS_PICTURE)) {
                    p.focusMode = Camera.Parameters.FOCUS_MODE_CONTINUOUS_PICTURE
                    camera.parameters = p
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "tap-to-focus failed: ${e.message}")
        }
    }

    private fun isOpenRecently(): Boolean {
        if (SystemClock.elapsedRealtime() - mLastClickTime < 3000) {
            return true
        }
        mLastClickTime = SystemClock.elapsedRealtime()
        return false
    }

    fun start() {
        mCamera?.startPreview() ?:
        Log.i(TAG, "mCamera startPreview")
    }

    fun stop() {
        mCamera?.stopPreview() ?:
        Log.i(TAG, "mCamera stopPreview")
    }

    val canShut: Boolean get() = shutted

    fun shut() {
        if (isOpenRecently()) {
            Log.i(TAG, "NOT Taking click")
            return
        }
        busy = true
        shutted = false
        Log.i(TAG, "try to focus")

        mCamera?.autoFocus { b, _ ->
            Log.i(TAG, "focus result: $b")
            // Lock AE and AWB so the bright paper doesn't get overexposed
            val params = mCamera?.parameters
            if (params?.isAutoExposureLockSupported == true) {
                params.autoExposureLock = true
            }
            if (params?.isAutoWhiteBalanceLockSupported == true) {
                params.autoWhiteBalanceLock = true
            }
            mCamera?.parameters = params
            mCamera?.enableShutterSound(false)
            mCamera?.takePicture(null, null, this)
        }

    }

    fun toggleFlash() {
        try {
            flashEnabled = !flashEnabled
            val parameters = mCamera?.parameters
            parameters?.flashMode =
                if (flashEnabled) Camera.Parameters.FLASH_MODE_TORCH else Camera.Parameters.FLASH_MODE_OFF
            mCamera?.parameters = parameters
            mCamera?.startPreview()
        } catch (e: CameraAccessException) {
            e.printStackTrace()
        }
    }

    private fun updateCamera() {
        if (null == mCamera) {
            return
        }
        mCamera?.stopPreview()
        try {
            mCamera?.setPreviewDisplay(mSurfaceHolder)
        } catch (e: IOException) {
            e.printStackTrace()
            return
        }
        mCamera?.setPreviewCallback(this)
        mCamera?.startPreview()
    }

    private val cameraManager = context.getSystemService(Context.CAMERA_SERVICE) as CameraManager

    private fun getCameraCharacteristics(id: String): CameraCharacteristics {
        return cameraManager.getCameraCharacteristics(id)
    }

    private fun getBackFacingCameraId(): String? {
        for (camID in cameraManager.cameraIdList) {
            val lensFacing =
                getCameraCharacteristics(camID)?.get(CameraCharacteristics.LENS_FACING)!!
            if (lensFacing == CameraCharacteristics.LENS_FACING_BACK) {
                mCameraLensFacing = camID
                break
            }
        }
        return mCameraLensFacing
    }

    private fun initCamera() {

        try {
            mCamera = Camera.open(Camera.CameraInfo.CAMERA_FACING_BACK)
        } catch (e: RuntimeException) {
            e.stackTrace
            Toast.makeText(context, "cannot open camera, please grant camera", Toast.LENGTH_SHORT)
                .show()
            return
        }

        val cameraCharacteristics =
            cameraManager.getCameraCharacteristics(getBackFacingCameraId()!!)

        val size = iView.getCurrentDisplay()?.let {
            getPreviewOutputSize(
                it, cameraCharacteristics, SurfaceHolder::class.java
            )
        }

        Log.i(TAG, "Selected preview size: ${size?.width}${size?.height}")

        size?.width?.toString()?.let { Log.i(TAG, it) }
        val param = mCamera?.parameters
        param?.setPreviewSize(size?.width ?: 1920, size?.height ?: 1080)
        val display = iView.getCurrentDisplay()
        val point = Point()

        display?.getRealSize(point)

        val displayWidth = minOf(point.x, point.y)
        val displayHeight = maxOf(point.x, point.y)
        val displayRatio = displayWidth.div(displayHeight.toFloat())
        val previewRatio = size?.height?.toFloat()?.div(size.width.toFloat()) ?: displayRatio
        if (displayRatio > previewRatio) {
            val surfaceParams = iView.getSurfaceView().layoutParams
            surfaceParams.height = (displayHeight / displayRatio * previewRatio).toInt()
            iView.getSurfaceView().layoutParams = surfaceParams
        }

        val supportPicSize = mCamera?.parameters?.supportedPictureSizes
        supportPicSize?.sortByDescending { it.width.times(it.height) }
        var pictureSize = supportPicSize?.find {
            it.height.toFloat().div(it.width.toFloat()) - previewRatio < 0.01
        }

        if (null == pictureSize) {
            pictureSize = supportPicSize?.get(0)
        }

        if (null == pictureSize) {
            Log.e(TAG, "can not get picture size")
        } else {
            param?.setPictureSize(pictureSize.width, pictureSize.height)
        }
        val pm = context.packageManager
        if (pm.hasSystemFeature(PackageManager.FEATURE_CAMERA_AUTOFOCUS) && mCamera!!.parameters.supportedFocusModes.contains(Camera.Parameters.FOCUS_MODE_CONTINUOUS_PICTURE))
        {
            param?.focusMode = Camera.Parameters.FOCUS_MODE_CONTINUOUS_PICTURE
            Log.i(TAG, "enabling autofocus")
        } else {
            Log.i(TAG, "autofocus not available")
        }

        param?.flashMode = Camera.Parameters.FLASH_MODE_OFF

        mCamera?.parameters = param
        mCamera?.setDisplayOrientation(90)
        mCamera?.enableShutterSound(false)
    }

    private fun matrixResizer(sourceMatrix: Mat): Mat {
        val sourceSize: Size = sourceMatrix.size()
        var copied = Mat()
        if (sourceSize.height < sourceSize.width) {
            Core.rotate(sourceMatrix, copied, ROTATE_90_CLOCKWISE)
        } else {
            copied = sourceMatrix
        }
        val copiedSize: Size = copied.size()
        return if (copiedSize.width > ScanConstants.MAX_SIZE.width || copiedSize.height > ScanConstants.MAX_SIZE.height) {
            var useRatio = 0.0
            val widthRatio: Double = ScanConstants.MAX_SIZE.width / copiedSize.width
            val heightRatio: Double = ScanConstants.MAX_SIZE.height / copiedSize.height
            useRatio = if(widthRatio > heightRatio)  widthRatio else heightRatio
            val resizedImage = Mat()
            val newSize = Size(copiedSize.width * useRatio, copiedSize.height * useRatio)
            Imgproc.resize(copied, resizedImage, newSize)
            resizedImage
        } else {
            copied
        }
    }
    fun detectEdge(pic: Mat) {
        Log.i("height", pic.size().height.toString())
        Log.i("width", pic.size().width.toString())
        val resizedMat = matrixResizer(pic)
        SourceManager.corners = processPicture(resizedMat)
        Imgproc.cvtColor(resizedMat, resizedMat, Imgproc.COLOR_RGB2BGRA)
        SourceManager.pic = resizedMat
        val cropIntent = Intent(context, CropActivity::class.java)
        cropIntent.putExtra(EdgeDetectionHandler.INITIAL_BUNDLE, this.initialBundle)
        (context as Activity).startActivityForResult(cropIntent, REQUEST_CODE)
    }

    override fun surfaceCreated(p0: SurfaceHolder) {
        initCamera()
    }

    override fun surfaceChanged(p0: SurfaceHolder, p1: Int, p2: Int, p3: Int) {
        updateCamera()
    }

    override fun surfaceDestroyed(p0: SurfaceHolder) {
        synchronized(this) {
            mCamera?.stopPreview()
            mCamera?.setPreviewCallback(null)
            mCamera?.release()
            mCamera = null
        }
    }

    override fun onPictureTaken(p0: ByteArray?, p1: Camera?) {
        Log.i(TAG, "on picture taken")
        Observable.just(p0)
            .subscribeOn(proxySchedule)
            .subscribe {
                val pictureSize = p1?.parameters?.pictureSize
                Log.i(TAG, "picture size: " + pictureSize.toString())
                val mat = Mat(
                    Size(
                        pictureSize?.width?.toDouble() ?: 1920.toDouble(),
                        pictureSize?.height?.toDouble() ?: 1080.toDouble()
                    ), CvType.CV_8U
                )
                mat.put(0, 0, p0)
                val pic = Imgcodecs.imdecode(mat, Imgcodecs.CV_LOAD_IMAGE_UNCHANGED)
                Core.rotate(pic, pic, Core.ROTATE_90_CLOCKWISE)
                mat.release()
                detectEdge(pic)
                shutted = true
                busy = false
                // Unlock AE/AWB so the next capture can re-calibrate
                mainHandler.post {
                    val params = mCamera?.parameters
                    if (params?.isAutoExposureLockSupported == true) params.autoExposureLock = false
                    if (params?.isAutoWhiteBalanceLockSupported == true) params.autoWhiteBalanceLock = false
                    mCamera?.parameters = params
                }
            }
    }

    override fun onPreviewFrame(p0: ByteArray?, p1: Camera?) {
        // Lighting check: only run and show when a paper is currently detected
        val now = SystemClock.elapsedRealtime()
        if (p0 != null && paperDetected && now - lastLightingCheckTime >= lightingCheckIntervalMs) {
            lastLightingCheckTime = now
            val w = p1?.parameters?.previewSize?.width ?: 1080
            val h = p1?.parameters?.previewSize?.height ?: 1920
            val msg = checkLighting(p0, w, h)
            mainHandler.post { iView.updateLightingFeedback(msg) }
        }

        if (busy) {
            return
        }
        busy = true
        try {
            Observable.just(p0)
                .observeOn(proxySchedule)
                .doOnError {}
                .subscribe({
                    val parameters = p1?.parameters
                    val width = parameters?.previewSize?.width
                    val height = parameters?.previewSize?.height
                    val yuv = YuvImage(
                        p0, parameters?.previewFormat ?: 0, width ?: 1080, height
                            ?: 1920, null
                    )
                    val out = ByteArrayOutputStream()
                    // Quality 20 encodes ~4x faster than 50 — edge detection needs
                    // shape, not detail, so low quality is fine for preview.
                    yuv.compressToJpeg(Rect(0, 0, width ?: 1080, height ?: 1920), 20, out)
                    val bytes = out.toByteArray()
                    val bitmap = BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
                    val img = Mat()
                    Utils.bitmapToMat(bitmap, img)
                    bitmap.recycle()
                    Core.rotate(img, img, Core.ROTATE_90_CLOCKWISE)
                    // bitmapToMat produces RGBA; convert to BGR so processPicture
                    // always receives BGR — fixes HSV saturation for yellow/green paper.
                    Imgproc.cvtColor(img, img, Imgproc.COLOR_RGBA2BGR)
                    // Downscale to 50% — all subsequent ops are 4x cheaper.
                    Imgproc.resize(img, img, Size(img.width() * 0.5, img.height() * 0.5))
                    try {
                        out.close()
                    } catch (e: IOException) {
                        e.printStackTrace()
                    }

                    Observable.create<Corners> {
                        val corner = processPicture(img)
                        busy = false
                        if (null != corner && corner.corners.size == 4) {
                            it.onNext(corner)
                        } else {
                            it.onError(Throwable("paper not detected"))
                        }
                    }.observeOn(AndroidSchedulers.mainThread())
                        .subscribe({
                            noDetectionStartTime = 0L  // document found — reset hint timer
                            paperDetected = true
                            iView.getPaperRect().onCornersDetected(it)
                        }, {
                            if (paperDetected) {
                                paperDetected = false
                                iView.updateLightingFeedback(null)
                            }
                            // After 2 s of no detection, nudge user to use a darker surface
                            val t = SystemClock.elapsedRealtime()
                            if (noDetectionStartTime == 0L) noDetectionStartTime = t
                            if (t - noDetectionStartTime >= 2000L) {
                                iView.updateLightingFeedback("Place document on a dark flat surface")
                            }
                            iView.getPaperRect().onCornersNotDetected()
                        })
                }, { throwable -> Log.e(TAG, throwable.message!!) })
        } catch (e: Exception) {
            print(e.message)
        }

    }

    /** [CameraCharacteristics] corresponding to the provided Camera ID */

    class SmartSize(width: Int, height: Int) {
        var size = SizeB(width, height)
        var long = max(size.width, size.height)
        var short = min(size.width, size.height)
        override fun toString() = "SmartSize(${long}x${short})"
    }

    /** Standard High Definition size for pictures and video */
    private val SIZE_1080P: SmartSize = SmartSize(1920, 1080)

    /** Returns a [SmartSize] object for the given [Display] */
    private fun getDisplaySmartSize(display: Display): SmartSize {
        val outPoint = Point()
        display.getRealSize(outPoint)
        return SmartSize(outPoint.x, outPoint.y)
    }

    /**
     * Returns the largest available PREVIEW size. For more information, see:
     * https://d.android.com/reference/android/hardware/camera2/CameraDevice and
     * https://developer.android.com/reference/android/hardware/camera2/params/StreamConfigurationMap
     */
    private fun <T> getPreviewOutputSize(
        display: Display,
        characteristics: CameraCharacteristics,
        targetClass: Class<T>,
        format: Int? = null
    ): SizeB {

        // Find which is smaller: screen or 1080p
        val screenSize = getDisplaySmartSize(display)
        val hdScreen = screenSize.long >= SIZE_1080P.long || screenSize.short >= SIZE_1080P.short
        val maxSize = if (hdScreen) SIZE_1080P else screenSize

        // If image format is provided, use it to determine supported sizes; else use target class
        val config = characteristics.get(
            CameraCharacteristics.SCALER_STREAM_CONFIGURATION_MAP
        )!!
        if (format == null)
            assert(StreamConfigurationMap.isOutputSupportedFor(targetClass))
        else
            assert(config.isOutputSupportedFor(format))
        val allSizes = if (format == null)
            config.getOutputSizes(targetClass) else config.getOutputSizes(format)

        // Get available sizes and sort them by area from largest to smallest
        val validSizes = allSizes
            .sortedWith(compareBy { it.height * it.width })
            .map { SmartSize(it.width, it.height) }.reversed()

        // Then, get the largest output size that is smaller or equal than our max size
        return validSizes.first { it.long <= maxSize.long && it.short <= maxSize.short }.size
    }
}
