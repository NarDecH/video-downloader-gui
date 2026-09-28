package com.nardech.videodownloader

import android.Manifest
import android.app.DownloadManager
import android.content.ContentValues
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Environment
import android.provider.MediaStore
import android.util.Log
import android.view.View
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.Spinner
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.schabi.newpipe.extractor.NewPipe
import org.schabi.newpipe.extractor.ServiceList
import org.schabi.newpipe.extractor.stream.StreamInfo
import org.schabi.newpipe.extractor.downloader.Downloader
import org.schabi.newpipe.extractor.downloader.Request
import org.schabi.newpipe.extractor.downloader.Response
import org.schabi.newpipe.extractor.exceptions.ReCaptchaException
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import java.io.File
import java.io.IOException
import java.util.concurrent.TimeUnit

class MainActivity : AppCompatActivity() {

    private lateinit var etUrl: TextView
    private lateinit var btnFetch: Button
    private lateinit var btnDownload: Button
    private lateinit var cardInfo: LinearLayout
    private lateinit var tvTitle: TextView
    private lateinit var tvMeta: TextView
    private lateinit var spQuality: Spinner
    private lateinit var progress: ProgressBar
    private lateinit var tvStatus: TextView

    private var streamInfo: StreamInfo? = null
    private var streamChoices: List<Pair<org.schabi.newpipe.extractor.stream.Stream, String>> = emptyList()
    private var currentDownloadId: Long = -1

    // ---------- โหมด "ลิงก์ทั่วไป" (เอนจิน yt-dlp + โหมดสำรองแยกสื่อจากหน้าเว็บ) ----------
    private enum class Mode { NEWPIPE, GENERIC_META, GENERIC_CANDIDATES }
    private var mode = Mode.NEWPIPE
    private var genericCandidates: List<String> = emptyList()
    private val genericFormats = listOf(
        Triple("คุณภาพดีที่สุด", "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b", false),
        Triple("1080p หรือต่ำกว่า", "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080][ext=mp4]/b", false),
        Triple("720p หรือต่ำกว่า", "bv*[height<=720][ext=mp4]+ba[ext=m4a]/b[height<=720][ext=mp4]/b", false),
        Triple("480p หรือต่ำกว่า", "bv*[height<=480][ext=mp4]+ba[ext=m4a]/b[height<=480][ext=mp4]/b", false),
        Triple("เสียงเท่านั้น (mp3)", "ba/b", true),
    )

    private val downloaderImpl = object : Downloader() {
        private val client = okhttp3.OkHttpClient.Builder()
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .build()

        override fun execute(request: Request): Response {
            val body = request.dataToSend()
            val method = request.httpMethod()
            val rb = okhttp3.Request.Builder()
                .url(request.url())
                .method(
                    method,
                    if (body != null)
                        okhttp3.RequestBody.create(
                            "application/json".toMediaTypeOrNull(), body
                        )
                    else if (method.equals("POST", true) || method.equals("PUT", true) || method.equals("PATCH", true))
                        okhttp3.RequestBody.create(null, ByteArray(0))
                    else null
                )
            request.headers().forEach { (k, v) -> rb.header(k, v.joinToString(", ")) }
            client.newCall(rb.build()).execute().use { resp ->
                val b = resp.body?.string() ?: ""
                val latestUrl = resp.request.url.toString()
                return Response(resp.code, resp.message, resp.headers.toMultimap(), b, latestUrl)
            }
        }

        @Throws(ReCaptchaException::class)
        override fun get(url: String): Response = execute(Request.Builder().url(url).build())
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        etUrl = findViewById(R.id.etUrl)
        btnFetch = findViewById(R.id.btnFetch)
        btnDownload = findViewById(R.id.btnDownload)
        cardInfo = findViewById(R.id.cardInfo)
        tvTitle = findViewById(R.id.tvTitle)
        tvMeta = findViewById(R.id.tvMeta)
        spQuality = findViewById(R.id.spQuality)
        progress = findViewById(R.id.progress)
        tvStatus = findViewById(R.id.tvStatus)

        NewPipe.init(downloaderImpl)

        // รับลิงก์จากการแชร์ (ACTION_SEND)
        val shared = if (intent?.action == android.content.Intent.ACTION_SEND) {
            intent.getStringExtra(android.content.Intent.EXTRA_TEXT)
        } else null
        if (!shared.isNullOrBlank()) {
            etUrl.text = shared
            fetchInfo()
        }

        btnFetch.setOnClickListener { fetchInfo() }
        btnDownload.setOnClickListener { startDownload() }

        // ขอสิทธิ์ notification สำหรับ Android 13+
        if (Build.VERSION.SDK_INT >= 33) {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS)
                != PackageManager.PERMISSION_GRANTED
            ) {
                ActivityCompat.requestPermissions(this, arrayOf(Manifest.permission.POST_NOTIFICATIONS), 1)
            }
        }
    }

    private fun extractUrl(line: String): String {
        val m = Regex("""(?:https?://|www\.)[^\s<>"'`]+""", RegexOption.IGNORE_CASE).find(line) ?: return line.trim()
        var u = m.value
        if (u.startsWith("www.", true)) u = "https://$u"
        return u.trimEnd('.', ',', ';', ':', '!', '?', ')', ']', '>', '"', '\'')
    }

    private fun fetchInfo() {
        val raw = etUrl.text?.toString()?.trim().orEmpty()
        val url = extractUrl(raw)
        if (url.isEmpty()) {
            Toast.makeText(this, "กรุณาวางลิงก์วีดีโอ", Toast.LENGTH_SHORT).show()
            return
        }
        btnFetch.isEnabled = false
        tvStatus.text = getString(R.string.fetching)
        tvStatus.visibility = View.VISIBLE
        cardInfo.visibility = View.GONE
        btnDownload.visibility = View.GONE
        spQuality.visibility = View.GONE
        progress.visibility = View.GONE

        val known = listOf("youtube.com", "youtu.be", "soundcloud.com", "bandcamp.com")
            .any { url.contains(it, true) }

        CoroutineScope(Dispatchers.IO).launch {
            if (known) {
                try {
                    fetchWithNewPipe(url)
                    return@launch
                } catch (e: Exception) {
                    Log.w(TAG, "NewPipe failed, trying yt-dlp engine: ${e.message}")
                }
            }
            fetchGeneric(url)
        }
    }

    // ---------- โฟลว์เดิม: YouTube/SoundCloud/Bandcamp ผ่าน NewPipeExtractor ----------
    private suspend fun fetchWithNewPipe(url: String) {
        val service = when {
            url.contains("soundcloud.com", true) -> ServiceList.SoundCloud
            url.contains("bandcamp.com", true) -> ServiceList.Bandcamp
            else -> ServiceList.YouTube
        }
        val info = StreamInfo.getInfo(service, url)
        streamInfo = info
        val video = info.videoStreams.filter { it.url != null && !it.isVideoOnly }
            .sortedByDescending { it.height }
        val audio = info.audioStreams.filter { it.url != null }
            .sortedByDescending { it.averageBitrate }
            .take(2)
        // คู่ (สตรีม, ป้ายกำกับ) — เสียงต่อท้ายเป็นตัวเลือก "เสียงเท่านั้น"
        val choices: List<Pair<org.schabi.newpipe.extractor.stream.Stream, String>> =
            video.map { s ->
                val fps = if (s.fps > 45) "${s.fps}fps" else ""
                s to "${s.resolution} ${s.format?.name ?: ""} $fps".trim()
            } + audio.map { a ->
                a to "AUDIO ${a.averageBitrate}kbps ${a.format?.name ?: ""}".trim()
            }
        streamChoices = choices
        mode = Mode.NEWPIPE
        withContext(Dispatchers.Main) {
            tvTitle.text = info.name
            tvMeta.text = "${info.uploaderName} • ${info.duration / 60} นาที • รองรับ ${choices.size} คุณภาพ"
            cardInfo.visibility = View.VISIBLE
            if (choices.isNotEmpty()) {
                spQuality.adapter = ArrayAdapter(
                    this@MainActivity, android.R.layout.simple_spinner_dropdown_item,
                    choices.map { it.second }
                )
                spQuality.visibility = View.VISIBLE
                btnDownload.visibility = View.VISIBLE
            } else {
                tvStatus.text = "ไม่พบสตรีมวิดีโอที่ดาวน์โหลดได้"
                return@withContext
            }
            tvStatus.text = ""
        }
    }

    // ---------- โฟลว์ใหม่: ลิงก์ทั่วไป — เอนจิน yt-dlp ก่อน แล้วโหมดสำรองแยกสื่อจากหน้าเว็บ ----------
    private suspend fun fetchGeneric(url: String) {
        try {
            YtDlpEngine.ensureInit(applicationContext) { msg ->
                runOnUiThread { tvStatus.text = msg }
            }
        } catch (e: Exception) {
            Log.e(TAG, "engine init failed", e)
            withContext(Dispatchers.Main) {
                tvStatus.text = getString(R.string.error_generic, e.message ?: e.javaClass.simpleName)
                btnFetch.isEnabled = true
            }
            return
        }

        // 1) เอนจิน yt-dlp อ่านลิงก์ตรง (รองรับหลายพันเว็บ) → มีเมทาดาทา + เลือกคุณภาพได้
        val meta = runCatching { YtDlpEngine.dumpJson(url) }.getOrNull()
        if (meta != null) {
            mode = Mode.GENERIC_META
            withContext(Dispatchers.Main) {
                tvTitle.text = meta.optString("title").ifBlank { url }
                val mins = meta.optLong("duration", 0) / 60
                tvMeta.text = "เอนจิน yt-dlp • ${meta.optString("extractor_key")} • $mins นาที"
                cardInfo.visibility = View.VISIBLE
                spQuality.adapter = ArrayAdapter(
                    this@MainActivity, android.R.layout.simple_spinner_dropdown_item,
                    genericFormats.map { it.first }
                )
                spQuality.visibility = View.VISIBLE
                btnDownload.visibility = View.VISIBLE
                tvStatus.text = ""
                btnFetch.isEnabled = true
            }
            return
        }

        // 2) เคส player ที่ฝังด้วย JS (เช่นหน้า player.html ของบริการฝังวีดีโอ)
        //    → แยกสื่อจากเนื้อหาหน้าเว็บ: ไฟล์ตรง → manifest (.m3u8/.mpd) → iframe player
        val scraped = runCatching {
            if (!PageScraper.isDirectMedia(url)) PageScraper.extract(PageScraper.fetch(url), url) else null
        }.getOrNull()
        val candidates = scraped?.candidates.orEmpty()
        if (candidates.isEmpty()) {
            withContext(Dispatchers.Main) {
                tvStatus.text = getString(R.string.no_video_found)
                btnFetch.isEnabled = true
            }
            return
        }
        mode = Mode.GENERIC_CANDIDATES
        genericCandidates = candidates
        Log.i(TAG, "generic candidates: $candidates")
        withContext(Dispatchers.Main) {
            tvTitle.text = scraped?.title?.takeIf { it.isNotBlank() } ?: url
            tvMeta.text = "โหมดสำรอง: พบสื่อ ${candidates.size} แหล่ง — เลือกดาวน์โหลดอัตโนมัติ"
            cardInfo.visibility = View.VISIBLE
            spQuality.adapter = ArrayAdapter(
                this@MainActivity, android.R.layout.simple_spinner_dropdown_item,
                listOf(genericFormats.first().first)
            )
            spQuality.visibility = View.VISIBLE
            btnDownload.visibility = View.VISIBLE
            tvStatus.text = ""
            btnFetch.isEnabled = true
        }
    }

    private fun startDownload() {
        // Android 9 ลงไปต้องขอ WRITE_EXTERNAL_STORAGE ก่อนเขียนลง Downloads
        if (Build.VERSION.SDK_INT <= 28 &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.WRITE_EXTERNAL_STORAGE)
            != PackageManager.PERMISSION_GRANTED
        ) {
            ActivityCompat.requestPermissions(
                this, arrayOf(Manifest.permission.WRITE_EXTERNAL_STORAGE), 2
            )
            return
        }
        when (mode) {
            Mode.NEWPIPE -> startNewPipeDownload()
            Mode.GENERIC_META -> startEngineDownload(null)
            Mode.GENERIC_CANDIDATES -> startEngineDownload(genericCandidates)
        }
    }

    // ---------- ดาวน์โหลดเดิม: สตรีมตรงผ่าน DownloadManager ----------
    private fun startNewPipeDownload() {
        val stream = streamChoices.getOrNull(spQuality.selectedItemPosition)?.first ?: return
        val info = streamInfo ?: return
        btnDownload.isEnabled = false

        val safeName = info.name.replace(Regex("[\\\\/:*?\"<>|]+"), "_").take(120)
        val fileName = "$safeName.${stream.format?.suffix ?: "mp4"}"

        val request = DownloadManager.Request(Uri.parse(stream.url)).apply {
            setTitle(fileName)
            setDescription("Video Downloader GUI")
            setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
            setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, fileName)
            setAllowedOverMetered(true)
        }
        val dm = getSystemService(DOWNLOAD_SERVICE) as DownloadManager
        currentDownloadId = dm.enqueue(request)

        progress.visibility = View.VISIBLE
        tvStatus.text = getString(R.string.downloading)
        Toast.makeText(this, "เริ่มดาวน์โหลด: $fileName", Toast.LENGTH_SHORT).show()

        // ติดตามความคืบหน้า
        CoroutineScope(Dispatchers.IO).launch {
            while (currentDownloadId >= 0) {
                val q = dm.query(DownloadManager.Query().setFilterById(currentDownloadId))
                if (q.moveToFirst()) {
                    val done = q.getInt(q.getColumnIndexOrThrow(DownloadManager.COLUMN_BYTES_DOWNLOADED_SO_FAR))
                    val total = q.getInt(q.getColumnIndexOrThrow(DownloadManager.COLUMN_TOTAL_SIZE_BYTES))
                    val status = q.getInt(q.getColumnIndexOrThrow(DownloadManager.COLUMN_STATUS))
                    val pct = if (total > 0) done * 100 / total else 0
                    withContext(Dispatchers.Main) {
                        progress.progress = pct
                        when (status) {
                            DownloadManager.STATUS_SUCCESSFUL -> {
                                tvStatus.text = getString(R.string.done)
                                progress.visibility = View.GONE
                                btnDownload.isEnabled = true
                                currentDownloadId = -1
                            }
                            DownloadManager.STATUS_FAILED -> {
                                tvStatus.text = "ดาวน์โหลดล้มเหลว"
                                btnDownload.isEnabled = true
                                currentDownloadId = -1
                            }
                            else -> tvStatus.text = "กำลังดาวน์โหลด… $pct%"
                        }
                    }
                    if (status == DownloadManager.STATUS_SUCCESSFUL || status == DownloadManager.STATUS_FAILED) break
                }
                Thread.sleep(800)
            }
        }
    }

    // ---------- ดาวน์โหลดผ่านเอนจิน yt-dlp (แล้วย้ายเข้า Downloads ผ่าน MediaStore) ----------
    private fun startEngineDownload(candidates: List<String>?) {
        btnDownload.isEnabled = false
        val sel = if (mode == Mode.GENERIC_META) spQuality.selectedItemPosition.coerceAtLeast(0) else 0
        val (label, format, audioOnly) = genericFormats[sel.coerceAtMost(genericFormats.size - 1)]
        val pageUrl = etUrl.text?.toString()?.trim()

        progress.visibility = View.VISIBLE
        progress.progress = 0
        tvStatus.text = getString(R.string.downloading)

        CoroutineScope(Dispatchers.IO).launch {
            var lastError: Exception? = null
            val targets = candidates ?: listOf(etUrl.text?.toString()?.trim().orEmpty())
            for ((idx, target) in targets.withIndex()) {
                try {
                    withContext(Dispatchers.Main) {
                        if (targets.size > 1) tvStatus.text = "ลองแหล่งที่ $idx/${targets.size}…"
                    }
                    val file = YtDlpEngine.download(
                        applicationContext, target, format,
                        audioOnly = audioOnly,
                        referer = pageUrl?.takeIf { it != target },
                    ) { pct, eta, _ ->
                        runOnUiThread {
                            progress.progress = pct.toInt().coerceIn(0, 100)
                            val etaTxt = if (eta > 0) " • เหลือ ${eta}s" else ""
                            tvStatus.text = "กำลังดาวน์โหลด… ${pct.toInt()}%$etaTxt"
                        }
                    }
                    saveToDownloads(file)
                    file.delete()
                    withContext(Dispatchers.Main) {
                        progress.visibility = View.GONE
                        tvStatus.text = getString(R.string.done)
                        btnDownload.isEnabled = true
                        Toast.makeText(this@MainActivity, "เสร็จสิ้น ✓ ${file.name}", Toast.LENGTH_LONG).show()
                    }
                    return@launch
                } catch (e: Exception) {
                    Log.w(TAG, "engine download failed for $target: ${e.message}")
                    lastError = e
                }
            }
            withContext(Dispatchers.Main) {
                progress.visibility = View.GONE
                tvStatus.text = getString(R.string.generic_failed, lastError?.message ?: "unknown")
                btnDownload.isEnabled = true
            }
        }
    }

    /** ย้ายไฟล์จากโฟลเดอร์ชั่วคราวของแอปเข้าโฟลเดอร์ Downloads ของระบบอย่างถูกต้อง */
    private fun saveToDownloads(src: File) {
        if (Build.VERSION.SDK_INT >= 29) {
            val values = ContentValues().apply {
                put(MediaStore.MediaColumns.DISPLAY_NAME, src.name)
                put(MediaStore.MediaColumns.MIME_TYPE, mimeFor(src.extension))
                put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS)
            }
            val uri = contentResolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values)
                ?: throw IOException("MediaStore insert failed")
            contentResolver.openOutputStream(uri)?.use { out ->
                src.inputStream().use { it.copyTo(out) }
            } ?: throw IOException("openOutputStream failed")
        } else {
            val dir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS)
            dir.mkdirs()
            var dst = File(dir, src.name)
            var n = 1
            while (dst.exists()) {
                val dot = src.name.lastIndexOf('.')
                dst = if (dot > 0) File(dir, "${src.name.substring(0, dot)} ($n)${src.name.substring(dot)}")
                else File(dir, "${src.name} ($n)")
                n++
            }
            src.copyTo(dst)
        }
    }

    private fun mimeFor(ext: String): String = when (ext.lowercase()) {
        "mp4", "m4v" -> "video/mp4"
        "webm" -> "video/webm"
        "mkv" -> "video/x-matroska"
        "mov" -> "video/quicktime"
        "ts" -> "video/mp2t"
        "mp3" -> "audio/mpeg"
        "m4a" -> "audio/mp4"
        "ogg", "opus" -> "audio/ogg"
        "wav" -> "audio/wav"
        else -> "application/octet-stream"
    }

    companion object {
        private const val TAG = "MainActivity"
        const val IntentExtraShareKey = "shared_url"
    }
}
