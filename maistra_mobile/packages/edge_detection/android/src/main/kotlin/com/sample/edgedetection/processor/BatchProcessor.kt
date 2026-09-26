package com.sample.edgedetection.processor

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import android.media.ExifInterface
import android.util.Log
import org.opencv.android.OpenCVLoader
import org.opencv.android.Utils
import org.opencv.core.Mat
import java.io.File
import java.io.FileOutputStream

private const val MAX_LONG_SIDE = 2048

object BatchProcessor {

    fun processImages(inputPaths: List<String>, outputPaths: List<String>): List<Boolean> {
        if (!OpenCVLoader.initDebug()) {
            Log.e(TAG, "OpenCV init failed")
            return List(inputPaths.size) { false }
        }
        return inputPaths.mapIndexed { i, inputPath ->
            try {
                processOne(inputPath, outputPaths[i])
                true
            } catch (e: Exception) {
                Log.e(TAG, "Batch failed for $inputPath: ${e.message}")
                false
            }
        }
    }

    private fun processOne(inputPath: String, outputPath: String) {
        val bitmap = loadScaled(inputPath)
        val src = Mat()
        Utils.bitmapToMat(bitmap, src)
        bitmap.recycle()

        val corners: Corners? = processPicture(src)

        if (corners == null || corners.corners.any { it == null }) {
            src.release()
            Log.w(TAG, "No corners detected for $inputPath")
            throw IllegalStateException("No corners detected")
        }

        val pts = listOf(corners.corners[0]!!, corners.corners[1]!!, corners.corners[2]!!, corners.corners[3]!!)

        // Reject if detected region spans nearly the whole image — this means
        // edge detection latched onto the image border rather than the paper.
        val minX = pts.minOf { it.x }
        val maxX = pts.maxOf { it.x }
        val minY = pts.minOf { it.y }
        val maxY = pts.maxOf { it.y }
        val boundingFraction = (maxX - minX) * (maxY - minY) / (src.width().toDouble() * src.height())
        if (boundingFraction > 0.88) {
            src.release()
            Log.w(TAG, "Edge detection latched to image border (fraction=${"%.2f".format(boundingFraction)}) for $inputPath")
            throw IllegalStateException("No page corners detected")
        }

        val result = cropPicture(src, pts)

        val out = Bitmap.createBitmap(result.width(), result.height(), Bitmap.Config.ARGB_8888)
        Utils.matToBitmap(result, out, true)
        FileOutputStream(File(outputPath)).use { fos ->
            out.compress(Bitmap.CompressFormat.JPEG, 92, fos)
            fos.flush()
        }
        out.recycle()
        result.release()
        src.release()
    }

    fun loadScaled(path: String): Bitmap {
        // First pass: read dimensions only
        val opts = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeFile(path, opts)
        val longSide = maxOf(opts.outWidth, opts.outHeight)

        // Compute power-of-2 sample size to keep long side <= MAX_LONG_SIDE
        var sampleSize = 1
        while (longSide / (sampleSize * 2) >= MAX_LONG_SIDE) sampleSize *= 2

        val decodeOpts = BitmapFactory.Options().apply {
            inSampleSize = sampleSize
            inPreferredConfig = Bitmap.Config.ARGB_8888
        }
        val raw = BitmapFactory.decodeFile(path, decodeOpts)
            ?: throw IllegalStateException("Cannot decode: $path")

        // Correct EXIF rotation
        val exif = ExifInterface(path)
        val degrees = when (
            exif.getAttributeInt(ExifInterface.TAG_ORIENTATION, ExifInterface.ORIENTATION_NORMAL)
        ) {
            ExifInterface.ORIENTATION_ROTATE_90 -> 90f
            ExifInterface.ORIENTATION_ROTATE_180 -> 180f
            ExifInterface.ORIENTATION_ROTATE_270 -> 270f
            else -> 0f
        }
        if (degrees == 0f) return raw
        val matrix = Matrix().apply { postRotate(degrees) }
        val rotated = Bitmap.createBitmap(raw, 0, 0, raw.width, raw.height, matrix, true)
        raw.recycle()
        return rotated
    }
}
