package com.sample.edgedetection.processor

import android.graphics.Bitmap
import android.util.Log
import org.opencv.android.Utils
import org.opencv.core.*
import org.opencv.imgproc.Imgproc
import kotlin.math.max
import kotlin.math.min
import kotlin.math.pow
import kotlin.math.sqrt

const val TAG: String = "PaperProcessor"

fun processPicture(previewFrame: Mat): Corners? {
    val contours = findContours(previewFrame)
    return getCorners(contours, previewFrame.size())
}

fun cropPicture(picture: Mat, pts: List<Point>): Mat {

    pts.forEach { Log.i(TAG, "point: $it") }
    val tl = pts[0]
    val tr = pts[1]
    val br = pts[2]
    val bl = pts[3]

    val widthA = sqrt((br.x - bl.x).pow(2.0) + (br.y - bl.y).pow(2.0))
    val widthB = sqrt((tr.x - tl.x).pow(2.0) + (tr.y - tl.y).pow(2.0))

    val dw = (widthA + widthB) / 2.0
    val maxWidth = java.lang.Double.valueOf(dw).toInt()

    val heightA = sqrt((tr.x - br.x).pow(2.0) + (tr.y - br.y).pow(2.0))
    val heightB = sqrt((tl.x - bl.x).pow(2.0) + (tl.y - bl.y).pow(2.0))

    // Compensate for height foreshortening caused by paper tilt toward camera.
    // When one width edge is closer (appears larger), both height edges are equally
    // compressed. The perspective ratio between the two width edges approximates
    // the correction factor needed for the height dimension.
    val wNear = max(widthA, widthB)
    val wFar = min(widthA, widthB).coerceAtLeast(1.0)
    val perspCorrection = sqrt(wNear / wFar)
    val dh = (heightA + heightB) / 2.0 * perspCorrection
    val maxHeight = java.lang.Double.valueOf(dh).toInt()

    val croppedPic = Mat(maxHeight, maxWidth, CvType.CV_8UC4)

    val srcMat = Mat(4, 1, CvType.CV_32FC2)
    val dstMat = Mat(4, 1, CvType.CV_32FC2)

    srcMat.put(0, 0, tl.x, tl.y, tr.x, tr.y, br.x, br.y, bl.x, bl.y)
    dstMat.put(0, 0, 0.0, 0.0, dw, 0.0, dw, dh, 0.0, dh)

    val m = Imgproc.getPerspectiveTransform(srcMat, dstMat)

    Imgproc.warpPerspective(picture, croppedPic, m, croppedPic.size())
    m.release()
    srcMat.release()
    dstMat.release()
    Log.i(TAG, "crop finish")
    return croppedPic
}

fun enhancePicture(src: Bitmap?): Bitmap {
    val srcMat = Mat()
    Utils.bitmapToMat(src, srcMat)
    Imgproc.cvtColor(srcMat, srcMat, Imgproc.COLOR_RGBA2GRAY)
    Imgproc.adaptiveThreshold(
        srcMat,
        srcMat,
        255.0,
        Imgproc.ADAPTIVE_THRESH_MEAN_C,
        Imgproc.THRESH_BINARY,
        15,
        15.0
    )
    val result = Bitmap.createBitmap(src?.width ?: 1080, src?.height ?: 1920, Bitmap.Config.RGB_565)
    Utils.matToBitmap(srcMat, result, true)
    srcMat.release()
    return result
}

private fun findContours(src: Mat): List<MatOfPoint> {
    val size = Size(src.size().width, src.size().height)
    val grayImage = Mat(size, CvType.CV_8UC1)
    val cannedImage = Mat(size, CvType.CV_8UC1)
    val dilate = Mat(size, CvType.CV_8UC1)
    val hsvImage = Mat()
    val satCanny = Mat(size, CvType.CV_8UC1)

    // Grayscale path — strong contrast on white paper vs. background.
    // 15x15 blur suppresses printed/ruled lines before edge detection.
    Imgproc.cvtColor(src, grayImage, Imgproc.COLOR_BGR2GRAY)
    Imgproc.GaussianBlur(grayImage, grayImage, Size(15.0, 15.0), 0.0)
    Imgproc.Canny(grayImage, cannedImage, 40.0, 120.0)

    // Saturation path — yellow and green paper have high color-saturation contrast
    // vs background even when luminance contrast is low.
    // Input must be BGR (converted in onPreviewFrame) for correct HSV mapping.
    Imgproc.cvtColor(src, hsvImage, Imgproc.COLOR_BGR2HSV)
    val channels = ArrayList<Mat>()
    Core.split(hsvImage, channels)
    Imgproc.GaussianBlur(channels[1], channels[1], Size(15.0, 15.0), 0.0)
    Imgproc.Canny(channels[1], satCanny, 15.0, 45.0)

    // Merge: grayscale covers white paper, saturation covers coloured paper
    Core.bitwise_or(cannedImage, satCanny, cannedImage)

    // Dilate edges, then morphological close to seal the full paper outline.
    // Closing fills gaps left by faint corners or torn edges.
    val dilateKernel = Imgproc.getStructuringElement(Imgproc.MORPH_RECT, Size(11.0, 11.0))
    val closeKernel  = Imgproc.getStructuringElement(Imgproc.MORPH_RECT, Size(15.0, 15.0))
    Imgproc.dilate(cannedImage, dilate, dilateKernel)
    Imgproc.morphologyEx(dilate, dilate, Imgproc.MORPH_CLOSE, closeKernel)

    val contours = ArrayList<MatOfPoint>()
    val hierarchy = Mat()
    Imgproc.findContours(
        dilate,
        contours,
        hierarchy,
        Imgproc.RETR_TREE,
        Imgproc.CHAIN_APPROX_SIMPLE
    )

    // Require 10–85 % of frame area: filters line contours (too small)
    // and desk/background contours that span the whole frame (too large).
    val minArea = size.width * size.height * 0.10
    val maxArea = size.width * size.height * 0.85
    val filteredContours = contours
        .filter { p: MatOfPoint ->
            val a = Imgproc.contourArea(p)
            a > minArea && a < maxArea
        }
        .sortedByDescending { p: MatOfPoint -> Imgproc.contourArea(p) }
        .take(5)

    hierarchy.release()
    grayImage.release()
    cannedImage.release()
    dilate.release()
    dilateKernel.release()
    closeKernel.release()
    hsvImage.release()
    satCanny.release()
    channels.forEach { it.release() }

    return filteredContours
}

private fun getCorners(contours: List<MatOfPoint>, size: Size): Corners? {
    val indexTo: Int = when (contours.size) {
        in 0..5 -> contours.size - 1
        else -> 4
    }
    for (index in 0..contours.size) {
        if (index in 0..indexTo) {
            val c2f = MatOfPoint2f(*contours[index].toArray())
            val peri = Imgproc.arcLength(c2f, true)
            val approx = MatOfPoint2f()
            Imgproc.approxPolyDP(c2f, approx, 0.03 * peri, true)
            val points = approx.toArray().asList()
            val convex = MatOfPoint()
            approx.convertTo(convex, CvType.CV_32S)
            // select biggest 4 angles polygon with paper-like aspect ratio
            if (points.size == 4 && Imgproc.isContourConvex(convex)) {
                val foundPoints = sortPoints(points)
                val w = max(
                    sqrt((foundPoints[1].x - foundPoints[0].x).pow(2) + (foundPoints[1].y - foundPoints[0].y).pow(2)),
                    sqrt((foundPoints[2].x - foundPoints[3].x).pow(2) + (foundPoints[2].y - foundPoints[3].y).pow(2))
                )
                val h = max(
                    sqrt((foundPoints[3].x - foundPoints[0].x).pow(2) + (foundPoints[3].y - foundPoints[0].y).pow(2)),
                    sqrt((foundPoints[2].x - foundPoints[1].x).pow(2) + (foundPoints[2].y - foundPoints[1].y).pow(2))
                )
                // Reject extreme aspect ratios — paper ranges from ~0.5 (A4 landscape) to ~2.0 (A4 portrait)
                // Anything outside 0.2–5.0 is a table edge or background artifact, not paper
                val ratio = if (h > 0) w / h else 0.0
                if (ratio < 0.2 || ratio > 5.0) continue
                return Corners(foundPoints, size)
            }
        } else {
            return null
        }
    }

    return null
}
private fun sortPoints(points: List<Point>): List<Point> {
    val p0 = points.minByOrNull { point -> point.x + point.y } ?: Point()
    val p1 = points.minByOrNull { point: Point -> point.y - point.x } ?: Point()
    val p2 = points.maxByOrNull { point: Point -> point.x + point.y } ?: Point()
    val p3 = points.maxByOrNull { point: Point -> point.y - point.x } ?: Point()
    return listOf(p0, p1, p2, p3)
}
