package com.nardech.videodownloader

import android.content.Context
import android.util.Log
import com.yausername.ffmpeg.FFmpeg
import com.yausername.youtubedl_android.YoutubeDL
import com.yausername.youtubedl_android.YoutubeDLRequest
import org.json.JSONObject
import java.io.File

/**
 * เอนจิน yt-dlp + ffmpeg จริงบน Android (ผ่านไลบรารี youtubedl-android)
 * รองรับลิงก์ทั่วไปหลายพันเว็บไซต์, HLS (.m3u8), DASH (.mpd รวมถึง video+audio
 * แยกไฟล์ที่ต้อง merge ด้วย ffmpeg) — ใช้พารามิเตอร์ชุดเดียวกับแอปเดสก์ท็อป
 */
object YtDlpEngine {

    private const val TAG = "YtDlpEngine"
    private const val PREFS = "engine_prefs"
    private const val KEY_UPDATED = "ytdlp_updated_once"

    @Volatile
    private var ready = false

    /** init ครั้งแรก (แตก Python/ffmpeg ออกจาก APK ใช้เวลาสักครู่) + อัปเดต yt-dlp ครั้งเดียวต่อการติดตั้ง */
    fun ensureInit(context: Context, onStatus: (String) -> Unit = {}) {
        if (ready) return
        synchronized(this) {
            if (ready) return
            onStatus(context.getString(R.string.engine_preparing))
            Log.i(TAG, "init engine (first use)")
            YoutubeDL.init(context)
            FFmpeg.init(context)
            val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            if (!prefs.getBoolean(KEY_UPDATED, false)) {
                // เวอร์ชัน yt-dlp ที่แพ็กมากับไลบรารีเก่ามาก — เว็บเปลี่ยนบ่อย ต้องอัปเดตก่อนใช้จริง
                try {
                    onStatus(context.getString(R.string.engine_updating))
                    Log.i(TAG, "updating yt-dlp to latest stable")
                    YoutubeDL.updateYoutubeDL(context, YoutubeDL.UpdateChannel.STABLE)
                    prefs.edit().putBoolean(KEY_UPDATED, true).apply()
                    Log.i(TAG, "yt-dlp updated, version=${YoutubeDL.version(context)}")
                } catch (e: Exception) {
                    // ไม่มีอินเทอร์เน็ตตอนนี้ก็ยังใช้เวอร์ชันที่แพ็กมาได้
                    Log.w(TAG, "yt-dlp update failed, continue with bundled version", e)
                }
            }
            ready = true
        }
    }

    /** โฟลเดอร์ทำงานชั่วคราว (ภายใน storage ของแอป ไม่ต้องขอสิทธิ์) */
    fun workDir(context: Context): File {
        val base = context.getExternalFilesDir(null) ?: context.filesDir
        return File(base, "work").apply { mkdirs() }
    }

    /**
     * ดึงข้อมูลเมทาดาทา (title/duration/คุณภาพ) โดยไม่ดาวน์โหลด — คืน null ถ้า yt-dlp จัดการไม่ได้
     * (เช่นหน้า player ที่ฝังด้วย JS → ให้ไปใช้ [PageScraper] แทน)
     */
    fun dumpJson(url: String): JSONObject? {
        return try {
            val req = YoutubeDLRequest(url).apply {
                addOption("--dump-json")
                addOption("--no-playlist")
                addOption("--no-warnings")
            }
            val resp = YoutubeDL.getInstance().execute(req)
            val line = resp.out.trim().lineSequence().lastOrNull { it.trim().startsWith("{") } ?: resp.out.trim()
            JSONObject(line)
        } catch (e: Exception) {
            Log.i(TAG, "dumpJson failed for $url: ${e.message}")
            null
        }
    }

    /**
     * ดาวน์โหลดด้วยเอนจิน yt-dlp คืนไฟล์ที่ได้ (อยู่ในโฟลเดอร์ชั่วคราวของแอป)
     * format เป็น yt-dlp format selector เช่น "bv*+ba/b", audioOnly จะแปลงเป็น mp3
     */
    fun download(
        context: Context,
        url: String,
        format: String,
        audioOnly: Boolean = false,
        referer: String? = null,
        onProgress: (pct: Float, etaSec: Long, line: String) -> Unit = { _, _, _ -> },
    ): File {
        val dir = workDir(context)
        dir.listFiles()?.forEach { if (it.isFile) it.delete() } // เคลียร์ของครั้งก่อน

        val req = YoutubeDLRequest(url).apply {
            addOption("-f", format)
            addOption("-o", File(dir, "%(title).100s-%(id).16s.%(ext)s").absolutePath)
            addOption("--no-playlist")
            addOption("--retries", 3)
            addOption("--fragment-retries", 5)
            addOption("--concurrent-fragments", 4)
            addOption("--newline")
            addOption("--progress")
            addOption("--print", "after_move:filepath")
            if (referer != null) addOption("--referer", referer) // กัน CDN ตรวจ hotlink
            if (audioOnly) {
                addOption("-x")
                addOption("--audio-format", "mp3")
                addOption("--audio-quality", "0")
            }
        }
        Log.i(TAG, "download: $url (format=$format, audioOnly=$audioOnly, referer=${referer ?: "-"})")
        val resp = YoutubeDL.getInstance().execute(req) { pct, eta, line ->
            onProgress(pct, eta, line)
        }
        // พาธไฟล์จริงมาจาก --print after_move:filepath (บรรทัดสุดท้ายที่ไม่ได้ขึ้นต้นด้วย "[")
        val printed = resp.out.lines()
            .lastOrNull { it.isNotBlank() && !it.trim().startsWith("[") }
            ?.trim()
        val file = printed?.let { File(it) }?.takeIf { it.exists() }
            ?: dir.listFiles()?.filter { it.isFile }?.maxByOrNull { it.lastModified() }
            ?: throw IllegalStateException("download finished but output file not found")
        Log.i(TAG, "downloaded: ${file.absolutePath} (${file.length()} bytes)")
        return file
    }
}
