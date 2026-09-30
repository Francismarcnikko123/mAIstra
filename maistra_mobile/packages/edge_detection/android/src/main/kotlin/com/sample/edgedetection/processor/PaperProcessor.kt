package com.sample.edgedetection.processor

import android.graphics.Bitmap
import android.util.Log
import org.opencv.android.Utils
import org.opencv.core.*
import org.opencv.imgproc.Imgproc
import kotlin.math.abs
import kotlin.math.max
import kotlin.math.min
import kotlin.math.pow
import kotlin.math.roundToInt
import kotlin.math.sqrt

const val TAG: String = "PaperProcessor"

// Width the live preview detects at (1080p frame rotated, then halved). The
// blur, dilate and close sizes in findContours are in pixels and tuned for it.
private const val DETECT_WIDTH = 540.0

fun processPicture(previewFrame: Mat): Corners? {
    // A captured photo is ~2300 px wide. At that size the 15 px close can't
    // join the paper outline, no contour reaches the 10 % area minimum, and
    // the crop screen fell back to a default 10-90 % box although the
    // preview had found the paper. Detect on a preview-sized copy and scale
    // the corners back; the crop itself still uses the full photo.
    val scale = DETECT_WIDTH / previewFrame.width()
    if (scale >= 1.0) {
        // Live preview: one attempt per frame keeps the frame rate.
        return detect(previewFrame, tryEachChannel = false)
    }
    val small = Mat()
    Imgproc.resize(
        previewFrame, small,
        Size(DETECT_WIDTH, previewFrame.height() * scale),
        0.0, 0.0, Imgproc.INTER_AREA
    )
    val found = detect(small, tryEachChannel = true)
    small.release()
    return found?.let { c ->
        Corners(c.corners.map { p -> p?.let { Point(it.x / scale, it.y / scale) } }, previewFrame.size())
    }
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

// Finds the page on a detection-sized image (~540 px wide) from the combined
// grayscale + saturation edges. In dim light the saturation channel picks up
// noise from a dark desk that can break the page outline or bend it into a
// wrong shape, and which one happens flips on tiny image differences. So for a
// captured photo the grayscale and saturation edges are also tried on their
// own, and the box whose sides lie best on real edges is kept; the combined
// box stays unless another is clearly better supported.
private fun detect(src: Mat, tryEachChannel: Boolean): Corners? {
    val (grayEdges, satEdges) = cannyEdges(src)
    val bothEdges = Mat()
    Core.bitwise_or(grayEdges, satEdges, bothEdges)

    val attempts = if (tryEachChannel) listOf(bothEdges, grayEdges, satEdges) else listOf(bothEdges)
    val boxes = attempts.map { edges ->
        getCorners(findContours(edges, src.size()), src.size())
            ?.takeUnless { coversWholeImage(it, src.size()) }
            ?.let { snapToEdges(it, bothEdges) }
    }

    val chosen = if (!tryEachChannel) boxes[0] else {
        val nearEdges = Mat()
        Imgproc.dilate(bothEdges, nearEdges, Imgproc.getStructuringElement(Imgproc.MORPH_RECT, Size(3.0, 3.0)))
        val scored = boxes.filterNotNull().map { it to edgeSupport(it, nearEdges) }
        nearEdges.release()
        val combined = scored.firstOrNull { it.first === boxes[0] }
        val best = scored.maxByOrNull { it.second }
        if (combined != null && best != null && best.second - combined.second < MIN_SUPPORT_GAIN) combined.first
        else best?.first
    }

    grayEdges.release()
    satEdges.release()
    bothEdges.release()
    return chosen
}

// Another channel's box replaces the combined one only when this much more
// of its outline lies on edges.
private const val MIN_SUPPORT_GAIN = 0.05

// Share of points along the box's sides (corners excluded) that lie on an edge.
// A box following the page scores ~0.9-1.0; one bent onto desk noise or the
// photo border scores far lower (0.3-0.7 on the test photos).
private fun edgeSupport(c: Corners, nearEdges: Mat): Double {
    val pts = c.corners.map { it ?: return 0.0 }
    var hit = 0
    var total = 0
    for (i in 0..3) {
        val p = pts[i]
        val r = pts[(i + 1) % 4]
        val len = sqrt((r.x - p.x).pow(2) + (r.y - p.y).pow(2))
        val n = max(2, (len / 2).toInt())
        for (k in 0 until n) {
            val t = 0.1 + 0.8 * k / (n - 1)
            val x = (p.x + t * (r.x - p.x)).roundToInt()
            val y = (p.y + t * (r.y - p.y)).roundToInt()
            total++
            if (x in 0 until nearEdges.cols() && y in 0 until nearEdges.rows() && nearEdges.get(y, x)[0] > 0) hit++
        }
    }
    return if (total == 0) 0.0 else hit.toDouble() / total
}

// A box spanning nearly the whole image traced desk noise, not the page (the
// same 88 % rule BatchProcessor applies); treating it as not found lets the
// next channel try.
private fun coversWholeImage(c: Corners, size: Size): Boolean {
    val pts = c.corners.filterNotNull()
    if (pts.size < 4) return false
    val box = (pts.maxOf { it.x } - pts.minOf { it.x }) * (pts.maxOf { it.y } - pts.minOf { it.y })
    return box > 0.88 * size.width * size.height
}

// Thin Canny edges of the grayscale and saturation channels.
private fun cannyEdges(src: Mat): Pair<Mat, Mat> {
    val grayImage = Mat()
    val cannedImage = Mat()
    val hsvImage = Mat()
    val satCanny = Mat()

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

    grayImage.release()
    hsvImage.release()
    channels.forEach { it.release() }
    return Pair(cannedImage, satCanny)
}

// Width of the band searched on each side of a detected edge, in pixels at
// DETECT_WIDTH. The dilate + close below make the outline ~11-15 px thick.
private const val SNAP_BAND = 14

// The contour runs along the outer or inner border of the thickened outline,
// so the box sits half a band outside the page (desk strip) or inside it (cutting
// text written near the edge). Moves each side to the offset within
// ±SNAP_BAND where the thin edges line up most, keeping its angle, and
// intersects the four sides again.
private fun snapToEdges(found: Corners, edges: Mat): Corners {
    val pts = found.corners.map { it ?: return found }
    val nonZero = MatOfPoint()
    Core.findNonZero(edges, nonZero)
    val edgePoints = nonZero.toArray()
    nonZero.release()

    val cx = pts.sumOf { it.x } / 4
    val cy = pts.sumOf { it.y } / 4
    val sides = ArrayList<DoubleArray>(4) // x, y, dx, dy of each side's line
    for (i in 0..3) {
        val p = pts[i]
        val r = pts[(i + 1) % 4]
        val len = sqrt((r.x - p.x).pow(2) + (r.y - p.y).pow(2))
        if (len < 1.0) return found
        val dx = (r.x - p.x) / len
        val dy = (r.y - p.y) / len
        var nx = -dy
        var ny = dx
        if ((cx - p.x) * nx + (cy - p.y) * ny > 0) { nx = -nx; ny = -ny } // point outward

        // Count edge pixels by their distance from the side, ignoring the
        // corners where two sides meet.
        val counts = IntArray(2 * SNAP_BAND + 1)
        var inBand = 0
        for (q in edgePoints) {
            val rx = q.x - p.x
            val ry = q.y - p.y
            val along = rx * dx + ry * dy
            if (along < 0.1 * len || along > 0.9 * len) continue
            val off = rx * nx + ry * ny
            if (abs(off) > SNAP_BAND) continue
            counts[(off + SNAP_BAND).roundToInt()]++
            inBand++
        }
        var shift = 0.0
        if (inBand > 0.3 * len) {
            var best = -1
            var bestCount = 0
            for (k in counts.indices) {
                val c = counts[k] + (if (k > 0) counts[k - 1] else 0) + (if (k < counts.size - 1) counts[k + 1] else 0)
                if (c > bestCount) { bestCount = c; best = k }
            }
            if (bestCount > 0.25 * len) shift = (best - SNAP_BAND).toDouble()
        }
        sides.add(doubleArrayOf(p.x + shift * nx, p.y + shift * ny, dx, dy))
    }

    val snapped = (0..3).map { i -> intersect(sides[(i + 3) % 4], sides[i]) ?: pts[i] }
    return Corners(snapped, found.size)
}

private fun intersect(a: DoubleArray, b: DoubleArray): Point? {
    val cross = a[2] * b[3] - a[3] * b[2]
    if (abs(cross) < 1e-6) return null
    val t = ((b[0] - a[0]) * b[3] - (b[1] - a[1]) * b[2]) / cross
    return Point(a[0] + t * a[2], a[1] + t * a[3])
}

private fun findContours(edges: Mat, size: Size): List<MatOfPoint> {
    val dilate = Mat()

    // Dilate edges, then morphological close to seal the full paper outline.
    // Closing fills gaps left by faint corners or torn edges.
    val dilateKernel = Imgproc.getStructuringElement(Imgproc.MORPH_RECT, Size(11.0, 11.0))
    val closeKernel  = Imgproc.getStructuringElement(Imgproc.MORPH_RECT, Size(15.0, 15.0))
    Imgproc.dilate(edges, dilate, dilateKernel)
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
    dilate.release()
    dilateKernel.release()
    closeKernel.release()

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
